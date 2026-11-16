"""API-Football v3, plano gratuito: 100 req/dia e 10 req/min. Usada so para detalhes ao vivo."""
from ..config import SOURCES, keys
from ..http import fetch

BASE = SOURCES["apifootball"]["url"]


def _get(path, params=None, ttl=90):
    k = keys()["apifootball"]
    if not k:
        return dict(ok=False, data=None, fetched_at=None, stale=False, from_cache=False, source="apifootball",
                    error="sem chave da API-Football (gratuita) configurada")
    return fetch("apifootball", BASE + path, params=params, headers={"x-apisports-key": k}, ttl=ttl)


def live(ttl=90):
    """Uma unica chamada traz todos os jogos ao vivo, com eventos."""
    return _get("/fixtures", {"live": "all"}, ttl)

def statistics(fixture_id, ttl=120):
    return _get("/fixtures/statistics", {"fixture": fixture_id}, ttl)

def status(ttl=300):
    return _get("/status", None, ttl)

def lineups(fixture_id, ttl=900):
    return _get("/fixtures/lineups", {"fixture": fixture_id}, ttl)
