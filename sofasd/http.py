"""Cliente HTTP com cache em disco, controle de limite por fonte e tratamento de falhas.

Toda resposta volta com: ok, data, fetched_at (quando o dado foi realmente buscado),
from_cache, stale (cache vencido usado por falha/limite) e error (mensagem legivel).
"""
import json, os, time, hashlib
import requests
from .config import SOURCES, AF_DAILY_RESERVE
from .db import con

UA = {"User-Agent": "SOFA-SD/1.0 (uso pessoal)"}


def usage(source):
    now = time.time()
    day0 = now - (now % 86400)  # API-Football zera 00:00 UTC
    with con() as c:
        m = c.execute("SELECT COUNT(*) n FROM api_usage WHERE source=? AND ts>?", (source, now - 60)).fetchone()["n"]
        d = c.execute("SELECT COUNT(*) n FROM api_usage WHERE source=? AND ts>?", (source, day0)).fetchone()["n"]
        last = c.execute("SELECT MAX(ts) t FROM api_usage WHERE source=? AND ok=1", (source,)).fetchone()["t"]
    cfg = SOURCES[source]
    return dict(used_minute=m, limit_minute=cfg["per_min"], used_day=d, limit_day=cfg["per_day"], last_success=last)


def _allowed(source):
    u = usage(source)
    if u["used_minute"] >= u["limit_minute"]:
        return False, f"limite de {u['limit_minute']} requisições/min atingido; aguardando"
    if u["limit_day"] and u["used_day"] >= u["limit_day"] - AF_DAILY_RESERVE:
        return False, f"cota diária gratuita ({u['limit_day']}/dia) praticamente esgotada; volta 00:00 UTC"
    return True, None


def _log(source, ok):
    with con() as c:
        c.execute("INSERT INTO api_usage VALUES(?,?,?)", (source, time.time(), 1 if ok else 0))
        c.execute("DELETE FROM api_usage WHERE ts<?", (time.time() - 3 * 86400,))


def fetch(source, url, params=None, headers=None, ttl=600, kind="json", timeout=25):
    key = hashlib.sha1((url + "?" + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    with con() as c:
        row = c.execute("SELECT body, fetched_at FROM http_cache WHERE key=?", (key,)).fetchone()

    def decode(b):
        if kind == "json":
            return json.loads(b)
        if kind == "text":
            return b.decode("utf-8-sig", errors="replace")
        return b

    def cached(error=None, stale=False):
        if row is None:
            return dict(ok=False, data=None, fetched_at=None, from_cache=False, stale=False, error=error, source=source)
        return dict(ok=True, data=decode(row["body"]), fetched_at=row["fetched_at"], from_cache=True, stale=stale, error=error, source=source)

    if row is not None and time.time() - row["fetched_at"] < ttl:
        return cached()
    ok, why = _allowed(source)
    # na exportacao automatica (GitHub Actions) espera o limite por minuto liberar em vez de desistir
    waited = 0
    while not ok and os.environ.get("SOFA_WAIT_RATE") and "min" in (why or "") and waited < 130:
        time.sleep(7); waited += 7; ok, why = _allowed(source)
    if not ok:
        return cached(error=why, stale=True)
    err = None
    for attempt in range(2):
        try:
            r = requests.get(url, params=params, headers={**UA, **(headers or {})}, timeout=timeout)
            if r.status_code == 200:
                body = r.content
                if kind == "json":
                    j = json.loads(body)
                    # API-Football devolve 200 com campo "errors" preenchido (ex.: plano sem acesso)
                    if isinstance(j, dict) and j.get("errors"):
                        e = j["errors"]
                        _log(source, False)
                        return cached(error="API recusou: " + (json.dumps(e, ensure_ascii=False) if not isinstance(e, str) else e), stale=True)
                _log(source, True)
                with con() as c:
                    c.execute("INSERT OR REPLACE INTO http_cache VALUES(?,?,?)", (key, body, time.time()))
                return dict(ok=True, data=decode(body), fetched_at=time.time(), from_cache=False, stale=False, error=None, source=source)
            _log(source, False)
            if r.status_code == 429:
                err = "limite de requisições da fonte atingido (HTTP 429)"
                break
            if r.status_code in (401, 403):
                err = f"acesso negado pela fonte (HTTP {r.status_code}): chave inválida ou dado fora do plano gratuito"
                break
            if r.status_code == 404:
                err = "recurso não encontrado na fonte (HTTP 404)"
                break
            err = f"erro da fonte (HTTP {r.status_code})"
        except requests.RequestException as e:
            err = f"falha de conexão: {type(e).__name__}"
        if attempt == 0:
            time.sleep(1.0)
    return cached(error=err, stale=True)
