"""Calendario e placares do openfootball (dominio publico, sem chave)."""
import datetime as dt
from ..config import SOURCES, LEAGUES
from ..http import fetch


def season_names(league, today=None, back=2):
    today = today or dt.date.today()
    if LEAGUES[league].get("calendar_year"):
        return [str(today.year - i) for i in range(back, -1, -1)]
    y = today.year if today.month >= 7 else today.year - 1
    return [f"{y - i}-{(y - i + 1) % 100:02d}" for i in range(back, -1, -1)]


def season(league, name, ttl=6 * 3600):
    url = f"{SOURCES['openfootball']['url']}/{name}/{LEAGUES[league]['of']}.json"
    r = fetch("openfootball", url, ttl=ttl)
    ms = []
    if r["ok"]:
        for m in r["data"].get("matches", []):
            sc = m.get("score") or {}
            ft = sc.get("ft") if isinstance(sc, dict) else None
            ht = sc.get("ht") if isinstance(sc, dict) else None
            ms.append(dict(league=league, season=name, date=m.get("date"), time=m.get("time"), round=m.get("round"),
                           home_src=m.get("team1"), away_src=m.get("team2"),
                           hg=ft[0] if ft else None, ag=ft[1] if ft else None,
                           hthg=ht[0] if ht else None, htag=ht[1] if ht else None))
    return r, ms
