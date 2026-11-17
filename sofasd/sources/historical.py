"""Resultados reais: base historica aberta (carga inicial) + CSVs atuais do football-data.co.uk."""
import io, time, datetime as dt
import numpy as np, pandas as pd, requests
from ..config import SOURCES, LEAGUES, DATA
from ..db import con, set_meta
from ..http import fetch, UA

COLS = ["league", "date", "home", "away", "hg", "ag", "hthg", "htag", "hs", "as_", "hst", "ast",
        "hc", "ac", "hy", "ay", "hr", "ar", "odd_h", "odd_d", "odd_a", "source"]


def _upsert(df):
    df = df.dropna(subset=["league", "date", "home", "away", "hg", "ag"]).copy()
    df["hg"] = df["hg"].astype(int); df["ag"] = df["ag"].astype(int)
    rows = [tuple(None if (isinstance(v, float) and np.isnan(v)) else v for v in r)
            for r in df[COLS].itertuples(index=False, name=None)]
    with con() as c:
        if len(rows) < 20000:  # atualizacao: remove duplicatas vindas de fontes so-placar (data pode diferir em 1 dia)
            c.executemany("DELETE FROM results WHERE league=? AND home=? AND away=? AND source NOT IN ('historico','couk') "
                          "AND ABS(julianday(date)-julianday(?))<=3", [(r[0], r[2], r[3], r[1]) for r in rows])
        c.executemany(f"INSERT OR REPLACE INTO results VALUES({','.join('?'*len(COLS))})", rows)
    return len(rows)


def load_bulk(force=False):
    """Baixa ~239 mil partidas reais (2000 em diante). Uma vez so."""
    path = DATA / "Matches.csv"
    if force or not path.exists():
        r = requests.get(SOURCES["historico"]["url"], headers=UA, timeout=300, stream=True)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    x = pd.read_csv(path, low_memory=False)
    m = {"Division": "league", "MatchDate": "date", "HomeTeam": "home", "AwayTeam": "away", "FTHome": "hg", "FTAway": "ag",
         "HTHome": "hthg", "HTAway": "htag", "HomeShots": "hs", "AwayShots": "as_", "HomeTarget": "hst", "AwayTarget": "ast",
         "HomeCorners": "hc", "AwayCorners": "ac", "HomeYellow": "hy", "AwayYellow": "ay", "HomeRed": "hr", "AwayRed": "ar",
         "OddHome": "odd_h", "OddDraw": "odd_d", "OddAway": "odd_a"}
    d = x.rename(columns=m)[list(m.values())]
    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    d["source"] = "historico"
    n = _upsert(d)
    set_meta("historico_rows", n); set_meta("historico_max_date", d["date"].max())
    return n


def _season_code(today):
    y = today.year if today.month >= 7 else today.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def refresh_couk(ttl=6 * 3600):
    """Atualiza a temporada atual direto do football-data.co.uk (gratis, sem chave)."""
    today = dt.date.today()
    out = {}
    for lg, cfg in LEAGUES.items():
        url = (f"{SOURCES['couk']['url']}/new/BRA.csv" if lg == "BRA"
               else f"{SOURCES['couk']['url']}/mmz4281/{_season_code(today)}/{lg}.csv")
        r = fetch("couk", url, ttl=ttl, kind="text")
        if not r["ok"]:
            out[lg] = dict(ok=False, error=r["error"])
            if "conexão" in (r["error"] or ""):
                break  # fonte fora do ar: nao insiste nas outras ligas
            continue
        try:
            x = pd.read_csv(io.StringIO(r["data"]))
            x = x.dropna(how="all")
            if lg == "BRA":
                x = x.rename(columns={"Home": "HomeTeam", "Away": "AwayTeam", "HG": "FTHG", "AG": "FTAG",
                                      "AvgCH": "oh", "AvgCD": "od", "AvgCA": "oa"})
            else:
                x = x.rename(columns={"AvgH": "oh", "AvgD": "od", "AvgA": "oa"})
            d = pd.DataFrame({"league": lg,
                              "date": pd.to_datetime(x["Date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d"),
                              "home": x["HomeTeam"].astype(str).str.strip(), "away": x["AwayTeam"].astype(str).str.strip(),
                              "hg": pd.to_numeric(x["FTHG"], errors="coerce"), "ag": pd.to_numeric(x["FTAG"], errors="coerce")})
            for a, b in [("hthg", "HTHG"), ("htag", "HTAG"), ("hs", "HS"), ("as_", "AS"), ("hst", "HST"), ("ast", "AST"),
                         ("hc", "HC"), ("ac", "AC"), ("hy", "HY"), ("ay", "AY"), ("hr", "HR"), ("ar", "AR"),
                         ("odd_h", "oh"), ("odd_d", "od"), ("odd_a", "oa")]:
                d[a] = pd.to_numeric(x[b], errors="coerce") if b in x.columns else np.nan
            d["source"] = "couk"
            if lg == "BRA" and d["date"].notna().sum() > 3000:
                # A base historica aberta troca dia e mes em parte dos jogos do Brasileirao (ex.: 02/06 vira 06/02),
                # o que duplica partidas. O CSV oficial do football-data.co.uk cobre 2012 em diante com datas certas.
                with con() as c:
                    c.execute("DELETE FROM results WHERE league='BRA' AND source='historico'")
            n = _upsert(d)
            out[lg] = dict(ok=True, rows=n, max_date=d["date"].max(), fetched_at=r["fetched_at"], stale=r["stale"], error=r["error"])
        except Exception as e:  # formato inesperado: nao derruba o app
            out[lg] = dict(ok=False, error=f"CSV em formato inesperado: {e}")
    set_meta("couk_refresh", time.time())
    return out
