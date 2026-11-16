"""Configuracao central do SOFA SD. Apenas fontes gratuitas."""
import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
DB_PATH = DATA / "sofasd.sqlite"
MODEL_PATH = DATA / "models.pkl"
METRICS_PATH = DATA / "metrics.json"
KEYS_PATH = DATA / "keys.json"

# Ligas cobertas: intersecao entre historico aberto, openfootball e plano gratis do football-data.org
LEAGUES = {
    "BRA": dict(name="Brasileirão Série A", country="Brasil", of="br.1", fd="BSA", af=71, calendar_year=True),
    "E0":  dict(name="Premier League", country="Inglaterra", of="en.1", fd="PL", af=39),
    "E1":  dict(name="Championship", country="Inglaterra", of="en.2", fd="ELC", af=40),
    "SP1": dict(name="La Liga", country="Espanha", of="es.1", fd="PD", af=140),
    "I1":  dict(name="Serie A", country="Itália", of="it.1", fd="SA", af=135),
    "D1":  dict(name="Bundesliga", country="Alemanha", of="de.1", fd="BL1", af=78),
    "F1":  dict(name="Ligue 1", country="França", of="fr.1", fd="FL1", af=61),
    "N1":  dict(name="Eredivisie", country="Holanda", of="nl.1", fd="DED", af=88),
    "P1":  dict(name="Primeira Liga", country="Portugal", of="pt.1", fd="PPL", af=94),
}
FD_TO_LEAGUE = {v["fd"]: k for k, v in LEAGUES.items()}
AF_TO_LEAGUE = {v["af"]: k for k, v in LEAGUES.items()}

SOURCES = {
    "historico": dict(label="Base histórica aberta (football-data.co.uk via GitHub xgabora/Club-Football-Match-Data-2000-2025)",
                      url="https://raw.githubusercontent.com/xgabora/Club-Football-Match-Data-2000-2025/main/data/Matches.csv",
                      per_min=30, per_day=None),
    "couk": dict(label="football-data.co.uk (CSV da temporada atual)", url="https://www.football-data.co.uk", per_min=20, per_day=None),
    "openfootball": dict(label="openfootball/football.json (domínio público)",
                         url="https://raw.githubusercontent.com/openfootball/football.json/master", per_min=60, per_day=None),
    # limites oficiais do plano gratuito, verificados em nov/2026
    "fdorg": dict(label="football-data.org (plano gratuito)", url="https://api.football-data.org/v4", per_min=10, per_day=None),
    "apifootball": dict(label="API-Football (plano gratuito)", url="https://v3.football.api-sports.io", per_min=10, per_day=100),
}
AF_DAILY_RESERVE = 5  # nunca gastar as ultimas requisicoes do dia


def country_of(div: str) -> str:
    """Prefixo de pais de um codigo de divisao (E0,E1 -> E; SP1 -> SP)."""
    return div.rstrip("0123456789") if div not in ("EC",) else "E"


def season_start(league: str, today):
    import datetime as dt
    if LEAGUES.get(league, {}).get("calendar_year"):
        return dt.date(today.year, 1, 1)
    y = today.year if today.month >= 7 else today.year - 1
    return dt.date(y, 7, 1)


def keys() -> dict:
    k = {}
    if KEYS_PATH.exists():
        try:
            k = json.loads(KEYS_PATH.read_text())
        except Exception:
            k = {}
    return {
        "fdorg": os.environ.get("FOOTBALL_DATA_ORG_KEY") or k.get("fdorg") or "",
        "apifootball": os.environ.get("API_FOOTBALL_KEY") or k.get("apifootball") or "",
    }


def save_keys(fdorg=None, apifootball=None):
    k = {}
    if KEYS_PATH.exists():
        try:
            k = json.loads(KEYS_PATH.read_text())
        except Exception:
            k = {}
    if fdorg is not None:
        k["fdorg"] = fdorg.strip()
    if apifootball is not None:
        k["apifootball"] = apifootball.strip()
    KEYS_PATH.write_text(json.dumps(k))
