"""SQLite: cache HTTP, uso de API, calendario, apelidos de times e resultados."""
import sqlite3, time
from contextlib import contextmanager
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache(key TEXT PRIMARY KEY, body BLOB, fetched_at REAL);
CREATE TABLE IF NOT EXISTS api_usage(source TEXT, ts REAL, ok INTEGER);
CREATE INDEX IF NOT EXISTS ix_usage ON api_usage(source, ts);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS team_alias(country TEXT, src_name TEXT, canon TEXT, method TEXT, PRIMARY KEY(country, src_name));
CREATE TABLE IF NOT EXISTS fixtures(
  id TEXT PRIMARY KEY, provider TEXT, league TEXT, date TEXT, time TEXT, utc TEXT, status TEXT, minute INTEGER,
  home_src TEXT, away_src TEXT, home TEXT, away TEXT, hg INTEGER, ag INTEGER, hthg INTEGER, htag INTEGER,
  round TEXT, extra TEXT, updated_at REAL);
CREATE INDEX IF NOT EXISTS ix_fx ON fixtures(provider, league, date);
CREATE TABLE IF NOT EXISTS results(
  league TEXT, date TEXT, home TEXT, away TEXT, hg INTEGER, ag INTEGER, hthg REAL, htag REAL,
  hs REAL, as_ REAL, hst REAL, ast REAL, hc REAL, ac REAL, hy REAL, ay REAL, hr REAL, ar REAL,
  odd_h REAL, odd_d REAL, odd_a REAL, source TEXT, PRIMARY KEY(league, date, home, away));
CREATE INDEX IF NOT EXISTS ix_res ON results(league, date);
"""


@contextmanager
def con():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with con() as c:
        c.executescript(SCHEMA)


def set_meta(key, value):
    with con() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES(?,?,?)", (key, str(value), time.time()))


def get_meta(key):
    with con() as c:
        r = c.execute("SELECT value, updated_at FROM meta WHERE key=?", (key,)).fetchone()
    return (r["value"], r["updated_at"]) if r else (None, None)
