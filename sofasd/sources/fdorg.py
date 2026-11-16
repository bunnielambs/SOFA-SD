"""football-data.org v4, plano gratuito: 12 competicoes, 10 req/min, placar com atraso."""
from ..config import SOURCES, keys
from ..http import fetch

BASE = SOURCES["fdorg"]["url"]


def _get(path, params=None, ttl=600):
    k = keys()["fdorg"]
    if not k:
        return dict(ok=False, data=None, fetched_at=None, stale=False, from_cache=False, source="fdorg",
                    error="sem chave do football-data.org (gratuita) configurada")
    return fetch("fdorg", BASE + path, params=params, headers={"X-Auth-Token": k}, ttl=ttl)


def matches(date_from, date_to, ttl=120):
    return _get("/matches", {"dateFrom": date_from, "dateTo": date_to}, ttl)

def standings(code, ttl=900):
    return _get(f"/competitions/{code}/standings", None, ttl)

def scorers(code, ttl=3600):
    return _get(f"/competitions/{code}/scorers", {"limit": 20}, ttl)

def teams(code, ttl=24 * 3600):
    return _get(f"/competitions/{code}/teams", None, ttl)

def match(mid, ttl=60):
    return _get(f"/matches/{mid}", None, ttl)

def head2head(mid, ttl=3600):
    return _get(f"/matches/{mid}/head2head", {"limit": 10}, ttl)
