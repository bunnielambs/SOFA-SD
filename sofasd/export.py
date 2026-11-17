"""Gera a versao estatica dos dados reais para o site hospedado (Netlify).

Roda no GitHub Actions: atualiza as fontes, treina os modelos quando preciso e grava JSON em --out.
O site le esses arquivos; o ao vivo vem das funcoes do Netlify.
Uso: python -m sofasd.export --out pasta [--treinar]
"""
import argparse, json, os, re, shutil, sys, time, unicodedata, datetime as dt
from pathlib import Path


def slug(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def clean(o):
    import math
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else round(o, 5)
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item"):
        return clean(o.item())
    return o


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--treinar", action="store_true")
    a = ap.parse_args()
    os.environ.setdefault("SOFA_WAIT_RATE", "1")
    from . import db
    from .config import MODEL_PATH, LEAGUES
    from .train import STATE_PATH, train
    from .sources import historical
    db.init()
    t0 = time.time()
    if not (Path(MODEL_PATH).parent / "Matches.csv").exists():
        print("baixando base histórica:", historical.load_bulk())
    print("football-data.co.uk:", {k: (v.get("max_date") if v.get("ok") else v.get("error")) for k, v in historical.refresh_couk(ttl=0).items()})
    age = (time.time() - MODEL_PATH.stat().st_mtime) / 86400 if MODEL_PATH.exists() else 999
    if a.treinar or age > 6.5 or not STATE_PATH.exists():
        m = train(log=print); print("treino: log loss", m["r1x2"]["logloss_modelo"])
    from .service import Service
    svc = Service()
    svc.refresh(force=True)
    svc.refresh = lambda force=False: None  # uma atualizacao por execucao; evita gastar o limite das fontes
    out = Path(a.out)
    if out.exists(): shutil.rmtree(out)
    for d in ("match", "standings", "scorers", "team"): (out / d).mkdir(parents=True, exist_ok=True)
    W = lambda path, obj: (out / path).parent.mkdir(parents=True, exist_ok=True) or (out / path).write_text(json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":")))

    today = dt.date.today()
    from .db import con
    prov = svc.provider()
    with con() as c:
        rows = c.execute("SELECT * FROM fixtures WHERE provider=? AND date>=? AND date<=? ORDER BY date, COALESCE(utc, time)",
                         (prov, (today - dt.timedelta(days=4)).isoformat(), (today + dt.timedelta(days=21)).isoformat())).fetchall()
    idx = svc._results_idx() if prov == "openfootball" else None
    fixtures, teams, n_match = [], set(), 0
    for r in rows:
        m = svc._decorate(r, idx, full=True)
        full = svc.match(r["id"]) or m
        W(f"match/{slug(r['id'])}.json", full); n_match += 1
        p = m.get("pred") or {}
        m["pred"] = {k: p.get(k) for k in ("available", "reason", "p_home", "p_draw", "p_away")} if p else None
        fixtures.append(m)
        for k in ("home_canon", "away_canon"):
            if m.get(k): teams.add((m["league"], m[k]))
    res = svc.results(None, limit=500)["matches"]
    for x in res:
        d = svc.match(x["id"])
        if d: W(f"match/{slug(x['id'])}.json", d); n_match += 1
    for lg in LEAGUES:
        st = svc.standings(lg); W(f"standings/{lg}.json", st)
        teams |= {(lg, t["canon"]) for t in st.get("rows", []) if t.get("canon")}
        W(f"scorers/{lg}.json", svc.scorers(lg))
    hi = svc.highlights(); W("highlights.json", hi)
    for t in [hi.get("best_attack"), hi.get("best_defense")] + (hi.get("top_elo") or []):
        if t: teams.add((t["league"], t["team"]))
    W("intelligence.json", svc.intelligence())
    cr = svc.crests(); W("crests.json", cr); print("escudos:", len(cr))
    for lg, t in sorted(teams):
        W(f"team/{lg}/{slug(t)}.json", svc.team(lg, t))
    W("leagues.json", [dict(code=k, name=v["name"], country=v["country"]) for k, v in LEAGUES.items()])
    W("fixtures.json", dict(provider=prov, provider_label=__import__("sofasd.config", fromlist=["SOURCES"]).SOURCES[prov]["label"], matches=fixtures))
    W("results.json", dict(matches=res))
    st = svc.status(); b = svc.bundle
    st.update(generated_at=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
              model_params=dict(p_first_half=b["p_first_half"], sot_conv=b["sot_conv"], red_own=2 / 3, red_opp=1.2, prior_weight=1.0))
    st["sources"] = [x for x in st["sources"] if x["id"] != "apifootball"]
    W("status.json", st)
    print(f"exportado: {len(fixtures)} jogos no calendário, {len(res)} resultados, {n_match} páginas de partida, {len(teams)} times, "
          f"provedor {prov}, em {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
