"""Liga os nomes de times de cada fonte ao nome canonico do historico.

Metodo principal: cruzar partidas reais. Se a fonte X diz "Manchester United FC 2x1 ..." em uma data
e o historico tem "Man United 2x1 ..." na mesma data e liga, os nomes sao o mesmo time.
Reserva: semelhanca de texto. Sem correspondencia confiavel -> None (previsao fica indisponivel).
"""
import difflib, re, unicodedata, datetime as dt
from collections import Counter, defaultdict
from .config import country_of
from .db import con

STOP = {"fc", "cf", "afc", "sc", "ac", "ec", "ca", "cd", "ud", "rc", "fk", "sv", "vfl", "vfb", "tsg", "as", "ss", "us", "ssc", "og",
        "club", "clube", "de", "do", "da", "futebol", "football", "calcio", "1", "04", "05", "1846", "1899", "1909", "1913", "bsc", "cr", "se", "sk"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    toks = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in STOP]
    return " ".join(toks)


# Excecoes conhecidas em que nem o texto ajuda (o cruzamento por resultados continua tendo prioridade)
SEED = {("BRA", "CA Mineiro"): "Atletico-MG", ("BRA", "Clube Atlético Mineiro"): "Atletico-MG",
        ("BRA", "CA Paranaense"): "Athletico-PR", ("BRA", "Club Athletico Paranaense"): "Athletico-PR"}
_DIV = {}


def divisions(country):
    """Todas as divisoes do historico que pertencem ao mesmo pais (times sobem e descem)."""
    if country not in _DIV:
        with con() as c:
            _DIV[country] = [r[0] for r in c.execute("SELECT DISTINCT league FROM results") if country_of(r[0]) == country] or [country]
    return _DIV[country]


def get_map(country):
    with con() as c:
        return {r["src_name"]: r["canon"] for r in c.execute("SELECT src_name, canon FROM team_alias WHERE country=?", (country,))}


def learn(league, finished):
    """finished: lista de dicts com date, home_src, away_src, hg, ag (partidas reais encerradas)."""
    country = country_of(league)
    with con() as c:
        divs = divisions(country); ph = ",".join("?" * len(divs))
        rows = c.execute(f"SELECT date, home, away, hg, ag FROM results WHERE league IN ({ph}) AND source IN ('historico','couk')", divs).fetchall()
        canon_all = [r["canon"] for r in c.execute(
            f"SELECT DISTINCT home canon FROM results WHERE league IN ({ph}) AND source IN ('historico','couk') AND date>=?",
            divs + [(dt.date.today() - dt.timedelta(days=1500)).isoformat()])]
    idx = defaultdict(list)
    for r in rows:
        idx[(r["date"], r["hg"], r["ag"])].append((r["home"], r["away"]))
    votes = defaultdict(Counter)
    for m in finished:
        if m.get("hg") is None or not m.get("date"):
            continue
        d0 = dt.date.fromisoformat(m["date"][:10])
        cands = []
        for off in (0, -1, 1):
            cands += idx.get(((d0 + dt.timedelta(days=off)).isoformat(), m["hg"], m["ag"]), [])
        if len(cands) == 1:  # so vota quando nao ha ambiguidade
            votes[m["home_src"]][cands[0][0]] += 1
            votes[m["away_src"]][cands[0][1]] += 1
    known = get_map(country)
    new = {}
    for src, cnt in votes.items():
        (best, n), tot = cnt.most_common(1)[0], sum(cnt.values())
        if n >= 2 and n / tot >= 0.6:
            new[src] = (best, "resultados")
    names = {m[k] for m in finished for k in ("home_src", "away_src")}
    taken = {v[0] for v in new.values()} | set(known.values())
    for src in names:
        if src in new or src in known:
            continue
        if src in canon_all:
            new[src] = (src, "igual"); continue
        if (country, src) in SEED and SEED[(country, src)] in canon_all:
            new[src] = (SEED[(country, src)], "tabela"); continue
        pool = {norm(cn): cn for cn in canon_all if cn not in taken and norm(cn)}
        ns = norm(src); st = set(ns.split())
        hit = difflib.get_close_matches(ns, list(pool), n=1, cutoff=0.82)
        if hit:
            new[src] = (pool[hit[0]], "texto"); continue
        sub = [cn for k, cn in pool.items() if st and (set(k.split()) <= st or st <= set(k.split()))]
        if len(sub) == 1:  # ex.: "Hull City AFC" -> "Hull"; so aceita se for o unico candidato
            new[src] = (sub[0], "texto")
    with con() as c:
        for src, (canon, how) in new.items():
            c.execute("INSERT OR REPLACE INTO team_alias VALUES(?,?,?,?)", (country, src, canon, how))
    return len(new)


def resolve(league, name, amap=None):
    amap = amap if amap is not None else get_map(country_of(league))
    return amap.get(name)
