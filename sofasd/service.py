"""Orquestra fontes, banco, modelos e monta as respostas da interface."""
import json, pickle, threading, time, datetime as dt
import numpy as np
from . import db, aliases, predict
from .config import LEAGUES, SOURCES, FD_TO_LEAGUE, AF_TO_LEAGUE, MODEL_PATH, METRICS_PATH, keys, season_start, country_of
from .db import con
from .http import usage
from .sources import historical, openfootball, fdorg, apifootball
from .train import STATE_PATH

LIVE = ("IN_PLAY", "PAUSED", "LIVE")
STAT_COLS = ["hs", "as_", "hst", "ast", "hc", "ac", "hy", "ay", "hr", "ar"]


def _iso(ts):
    return dt.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds") if ts else None


class Service:
    def __init__(self):
        db.init()
        self.lock = threading.RLock()
        self.bundle = self.state = None
        self.pred_cache = {}
        self.last_refresh = 0
        self.last_errors = {}
        self.training = False
        self.load_models()

    # ---------------- modelos / estado ----------------
    def load_models(self):
        if MODEL_PATH.exists() and STATE_PATH.exists():
            self.bundle = pickle.load(open(MODEL_PATH, "rb")); self.state = pickle.load(open(STATE_PATH, "rb"))
            self.sync_state()

    def sync_state(self):
        """Aplica ao estado dos times os resultados reais que chegaram depois do treino."""
        if not self.state:
            return 0
        with self.lock, con() as c:
            rows = c.execute("SELECT * FROM results WHERE date>=? ORDER BY date",
                             ((dt.date.today() - dt.timedelta(days=900)).isoformat(),)).fetchall()
            n = 0
            for r in rows:
                if not self.state.is_dup(r["league"], r["home"], r["away"], r["date"]):
                    self.state.update(r["league"], r["home"], r["away"], r["date"], r["hg"], r["ag"], *[r[k] for k in STAT_COLS]); n += 1
            if n:
                self.pred_cache.clear()
            return n

    def retrain(self):
        if self.training:
            return False
        def run():
            self.training = True
            try:
                from .train import train
                train(log=lambda *_: None)
                with self.lock:
                    self.load_models(); self.pred_cache.clear()
            except Exception as e:
                self.last_errors["treino"] = str(e)
            finally:
                self.training = False
        threading.Thread(target=run, daemon=True).start()
        return True

    # ---------------- ingestao ----------------
    def _add_result(self, c, league, date, home, away, hg, ag, hthg, htag, source):
        if not home or not away or hg is None:
            return
        if c.execute("SELECT 1 FROM results WHERE league=? AND home=? AND away=? AND ABS(julianday(date)-julianday(?))<=3",
                     (league, home, away, date)).fetchone():
            return
        c.execute("INSERT OR IGNORE INTO results(league,date,home,away,hg,ag,hthg,htag,source) VALUES(?,?,?,?,?,?,?,?,?)",
                  (league, date, home, away, hg, ag, hthg, htag, source))

    def _upsert_fixtures(self, provider, items):
        maps = {}
        with con() as c:
            for m in items:
                lg = m["league"]; amap = maps.setdefault(lg, aliases.get_map(country_of(lg)))
                h, a = amap.get(m["home_src"]), amap.get(m["away_src"])
                c.execute("INSERT OR REPLACE INTO fixtures VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (m["id"], provider, lg, m["date"], m.get("time"), m.get("utc"), m["status"], m.get("minute"),
                           m["home_src"], m["away_src"], h, a, m.get("hg"), m.get("ag"), m.get("hthg"), m.get("htag"),
                           m.get("round"), json.dumps(m.get("extra") or {}), m["fetched_at"]))
                if m["status"] == "FINISHED":
                    self._add_result(c, lg, m["date"], h, a, m.get("hg"), m.get("ag"), m.get("hthg"), m.get("htag"), provider)

    def refresh_openfootball(self):
        for lg in LEAGUES:
            names = openfootball.season_names(lg, back=1)
            for i, s in enumerate(names):
                r, ms = openfootball.season(lg, s)
                if not r["ok"]:
                    self.last_errors["openfootball"] = r["error"]
                    if "conexão" in (r["error"] or ""):
                        return
                    continue
                aliases.learn(lg, ms)
                if i == len(names) - 1:  # temporada atual vira calendario
                    for m in ms:
                        m.update(id=f"of|{lg}|{m['date']}|{m['home_src']}|{m['away_src']}", fetched_at=r["fetched_at"],
                                 status="FINISHED" if m["hg"] is not None else "SCHEDULED")
                    self._upsert_fixtures("openfootball", ms)
                    self.last_errors.pop("openfootball", None)

    def refresh_fdorg(self, ttl=120):
        if not keys()["fdorg"]:
            return
        today = dt.date.today()
        r = fdorg.matches((today - dt.timedelta(days=3)).isoformat(), (today + dt.timedelta(days=10)).isoformat(), ttl)
        if r["error"]:
            self.last_errors["fdorg"] = r["error"]
        else:
            self.last_errors.pop("fdorg", None)
        if not r["ok"]:
            return
        by_lg = {}
        for m in r["data"].get("matches", []):
            lg = FD_TO_LEAGUE.get((m.get("competition") or {}).get("code"))
            if not lg or not m.get("utcDate"):
                continue
            loc = dt.datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).astimezone()
            sc = m.get("score") or {}; ft = sc.get("fullTime") or {}; ht = sc.get("halfTime") or {}
            by_lg.setdefault(lg, []).append(dict(
                id=f"fd|{m['id']}", league=lg, date=loc.date().isoformat(), time=loc.strftime("%H:%M"), utc=m["utcDate"],
                status=m.get("status") or "SCHEDULED", minute=m.get("minute"),
                home_src=(m.get("homeTeam") or {}).get("name"), away_src=(m.get("awayTeam") or {}).get("name"),
                hg=ft.get("home"), ag=ft.get("away"), hthg=ht.get("home"), htag=ht.get("away"),
                round=f"Rodada {m.get('matchday')}" if m.get("matchday") else None,
                extra=dict(fd_id=m["id"], crest_h=(m.get("homeTeam") or {}).get("crest"), crest_a=(m.get("awayTeam") or {}).get("crest")),
                fetched_at=r["fetched_at"]))
        for lg, ms in by_lg.items():
            aliases.learn(lg, [x for x in ms if x["status"] == "FINISHED"] + [dict(x, hg=None) for x in ms if x["status"] != "FINISHED"])
            self._upsert_fixtures("fdorg", ms)

    def refresh(self, force=False):
        with self.lock:
            has_fd = bool(keys()["fdorg"])
            if not force and time.time() - self.last_refresh < (55 if has_fd else 900):
                return
            self.last_refresh = time.time()
            try:
                res = historical.refresh_couk()
                bad = [v["error"] for v in res.values() if not v.get("ok")]
                if bad: self.last_errors["couk"] = bad[0]
                else: self.last_errors.pop("couk", None)
                self.refresh_openfootball()
                self.refresh_fdorg()
            except Exception as e:  # nunca derruba a interface
                self.last_errors["geral"] = f"{type(e).__name__}: {e}"
            self.sync_state()

    # ---------------- consultas ----------------
    def provider(self):
        if keys()["fdorg"]:
            with con() as c:
                if c.execute("SELECT 1 FROM fixtures WHERE provider='fdorg' LIMIT 1").fetchone():
                    return "fdorg"
        return "openfootball"

    def _pred(self, fid, league, home, away, date):
        if not self.bundle or not home or not away:
            return dict(available=False, reason="modelos ainda não treinados" if not self.bundle else
                        "time ainda não ligado ao histórico (sem partidas reais em comum para confirmar a identidade)")
        k = (fid, self.state.n_updates)
        if k not in self.pred_cache:
            with self.lock:
                self.pred_cache[k] = predict.prematch(self.bundle, self.state, league, home, away, date)
        return self.pred_cache[k]

    def _decorate(self, r, results_idx=None, full=False):
        lg = r["league"]; today = dt.date.today().isoformat()
        m = dict(id=r["id"], league=lg, league_name=LEAGUES[lg]["name"], date=r["date"], time=r["time"], utc=r["utc"],
                 status=r["status"], minute=r["minute"], home=r["home_src"], away=r["away_src"], home_canon=r["home"], away_canon=r["away"],
                 hg=r["hg"], ag=r["ag"], hthg=r["hthg"], htag=r["htag"], round=r["round"], extra=json.loads(r["extra"] or "{}"),
                 source=SOURCES[r["provider"]]["label"], updated_at=_iso(r["updated_at"]),
                 time_note=None if r["utc"] else "horário local da liga, conforme a fonte")
        if r["provider"] == "openfootball" and r["hg"] is None and r["date"] < today:
            hit = (results_idx or {}).get((lg, r["home"], r["away"]))
            if hit and abs((dt.date.fromisoformat(hit["date"]) - dt.date.fromisoformat(r["date"])).days) <= 3:
                m.update(status="FINISHED", hg=hit["hg"], ag=hit["ag"], source=SOURCES["couk"]["label"])
            else:
                m["status"] = "NO_SCORE"
        if m["status"] in ("SCHEDULED", "TIMED") or m["status"] in LIVE or full:
            p = self._pred(r["id"], lg, r["home"], r["away"], r["date"])
            m["pred"] = p if full else ({k: p.get(k) for k in ("available", "reason", "p_home", "p_draw", "p_away")})
        return m

    def _results_idx(self):
        idx = {}
        with con() as c:
            for lg in LEAGUES:
                for x in c.execute("SELECT * FROM results WHERE league=? AND date>=?", (lg, season_start(lg, dt.date.today()).isoformat())):
                    idx[(lg, x["home"], x["away"])] = dict(x)
        return idx

    def matches(self, scope, league=None):
        self.refresh()
        prov = self.provider(); today = dt.date.today().isoformat()
        note = None
        q = "SELECT * FROM fixtures WHERE provider=?"; a = [prov]
        if league: q += " AND league=?"; a.append(league)
        if scope == "today": q += " AND date=? ORDER BY COALESCE(utc, date||time)"; a.append(today)
        elif scope == "live":
            if prov != "fdorg":
                if keys()["fdorg"]:
                    return dict(matches=[], provider=prov, unavailable="Não foi possível obter os jogos ao vivo do football-data.org: "
                                + str(self.last_errors.get("fdorg") or "sem resposta da fonte") + ".")
                return dict(matches=[], provider=prov, unavailable="Partidas ao vivo exigem a chave gratuita do football-data.org. "
                            "As fontes sem chave (openfootball, football-data.co.uk) não publicam placar em tempo real.")
            q += " AND status IN ('IN_PLAY','PAUSED') ORDER BY utc"
            note = "No plano gratuito do football-data.org o placar ao vivo chega com atraso."
        elif scope == "upcoming":
            q += " AND date>=? AND date<=? AND status IN ('SCHEDULED','TIMED') ORDER BY date, COALESCE(utc, time) LIMIT 150"
            a += [today, (dt.date.today() + dt.timedelta(days=14)).isoformat()]
        with con() as c:
            rows = c.execute(q, a).fetchall()
        idx = self._results_idx() if prov == "openfootball" else None
        return dict(matches=[self._decorate(r, idx) for r in rows], provider=prov, provider_label=SOURCES[prov]["label"], note=note)

    def results(self, league=None, limit=80):
        self.refresh()
        q = "SELECT * FROM results WHERE league IN (%s)" % ",".join("?" * len(LEAGUES)); a = list(LEAGUES)
        if league: q = "SELECT * FROM results WHERE league=?"; a = [league]
        with con() as c:
            rows = c.execute(q + " ORDER BY date DESC LIMIT ?", a + [limit]).fetchall()
        return dict(matches=[dict(id=f"r|{r['league']}|{r['date']}|{r['home']}|{r['away']}", league=r["league"], league_name=LEAGUES[r["league"]]["name"],
                                  date=r["date"], home=r["home"], away=r["away"], hg=r["hg"], ag=r["ag"], status="FINISHED",
                                  source=SOURCES.get(r["source"], SOURCES["historico"])["label"]) for r in rows])

    def _form(self, c, league, team, n=6):
        ctry = aliases.divisions(country_of(league))
        rows = c.execute(f"SELECT * FROM results WHERE (home=? OR away=?) AND league IN ({','.join('?'*len(ctry))}) ORDER BY date DESC LIMIT ?",
                         [team, team] + ctry + [n]).fetchall()
        out = []
        for r in rows:
            home = r["home"] == team; gf, ga = (r["hg"], r["ag"]) if home else (r["ag"], r["hg"])
            out.append(dict(date=r["date"], opponent=r["away"] if home else r["home"], venue="C" if home else "F", gf=gf, ga=ga,
                            res="V" if gf > ga else "E" if gf == ga else "D", league=r["league"]))
        return out

    def _h2h(self, c, league, h, a, n=10):
        dv = aliases.divisions(country_of(league))
        rows = c.execute(f"SELECT * FROM results WHERE ((home=? AND away=?) OR (home=? AND away=?)) AND league IN ({','.join('?'*len(dv))}) ORDER BY date DESC LIMIT ?",
                         [h, a, a, h] + dv + [n]).fetchall()
        ms = [dict(date=r["date"], home=r["home"], away=r["away"], hg=r["hg"], ag=r["ag"], league=r["league"]) for r in rows]
        w = sum(1 for m in ms if (m["hg"] > m["ag"]) == (m["home"] == h) and m["hg"] != m["ag"])
        d = sum(1 for m in ms if m["hg"] == m["ag"])
        return dict(matches=ms, summary=dict(n=len(ms), home_wins=w, draws=d, away_wins=len(ms) - w - d) if ms else None)

    def _live_extra(self, m):
        """Eventos e estatisticas reais da API-Football, se houver chave e cota."""
        out = dict(available=False)
        if not keys()["apifootball"]:
            out["reason"] = "Eventos e estatísticas ao vivo exigem a chave gratuita da API-Football (100 requisições/dia)."
            return out
        r = apifootball.live()
        if not r["ok"]:
            out["reason"] = r["error"]; return out
        tgt = (aliases.norm(m["home"]), aliases.norm(m["away"]))
        import difflib
        for fx in r["data"].get("response", []):
            if AF_TO_LEAGUE.get((fx.get("league") or {}).get("id")) != m["league"]:
                continue
            hn = aliases.norm(fx["teams"]["home"]["name"]); an = aliases.norm(fx["teams"]["away"]["name"])
            if difflib.SequenceMatcher(None, hn, tgt[0]).ratio() + difflib.SequenceMatcher(None, an, tgt[1]).ratio() < 1.3:
                continue
            ev = fx.get("events") or []
            hid = fx["teams"]["home"]["id"]
            def red(side):
                return sum(1 for e in ev if e.get("type") == "Card"
                           and ("Red" in (e.get("detail") or "") or "Second Yellow" in (e.get("detail") or ""))
                           and (((e.get("team") or {}).get("id") == hid) == (side == "h")))
            out.update(available=True, source=SOURCES["apifootball"]["label"], updated_at=_iso(r["fetched_at"]), stale=r["stale"],
                       minute=(fx["fixture"]["status"] or {}).get("elapsed"), hg=fx["goals"]["home"], ag=fx["goals"]["away"],
                       red_h=red("h"), red_a=red("a"),
                       events=[dict(minute=(e.get("time") or {}).get("elapsed"), team=(e.get("team") or {}).get("name"),
                                    player=(e.get("player") or {}).get("name"), type=e.get("type"), detail=e.get("detail")) for e in ev])
            s = apifootball.statistics(fx["fixture"]["id"])
            if s["ok"] and len(s["data"].get("response", [])) == 2:
                st = {}
                for side, blk in zip("ha", s["data"]["response"]):
                    for it in blk.get("statistics", []):
                        st.setdefault(it["type"], {})[side] = it["value"]
                out["statistics"] = st; out["statistics_updated_at"] = _iso(s["fetched_at"])
            else:
                out["statistics_unavailable"] = s["error"] or "a fonte não enviou estatísticas para esta partida"
            lu = apifootball.lineups(fx["fixture"]["id"])
            if lu["ok"] and len(lu["data"].get("response", [])) == 2:
                out["lineups"] = [dict(team=(b.get("team") or {}).get("name"), formation=b.get("formation"), coach=(b.get("coach") or {}).get("name"),
                                       start=[dict(name=(x.get("player") or {}).get("name"), number=(x.get("player") or {}).get("number"),
                                                   pos=(x.get("player") or {}).get("pos")) for x in b.get("startXI") or []],
                                       bench=[(x.get("player") or {}).get("name") for x in b.get("substitutes") or []]) for b in lu["data"]["response"]]
                out["lineups_updated_at"] = _iso(lu["fetched_at"])
            else:
                out["lineups_unavailable"] = lu["error"] or "a fonte não enviou as escalações desta partida"
            return out
        out["reason"] = "A API-Football não lista esta partida entre os jogos ao vivo agora."
        return out

    def match(self, mid):
        if mid.startswith("r|"):
            _, lg, date, h, a = mid.split("|", 4)
            with con() as c:
                r = c.execute("SELECT * FROM results WHERE league=? AND date=? AND home=? AND away=?", (lg, date, h, a)).fetchone()
                if not r: return None
                m = dict(id=mid, league=lg, league_name=LEAGUES[lg]["name"], date=date, home=h, away=a, home_canon=h, away_canon=a,
                         hg=r["hg"], ag=r["ag"], hthg=r["hthg"], htag=r["htag"], status="FINISHED",
                         source=SOURCES.get(r["source"], SOURCES["historico"])["label"],
                         stats={k: r[k] for k in STAT_COLS} if r["hs"] is not None or r["hc"] is not None else None,
                         stats_unavailable=None if (r["hs"] is not None or r["hc"] is not None) else "A fonte não publica estatísticas desta partida.")
                m["h2h"] = self._h2h(c, lg, h, a); m["form"] = dict(home=self._form(c, lg, h), away=self._form(c, lg, a))
                m["season"] = dict(home=self._season_avgs(c, lg, h), away=self._season_avgs(c, lg, a))
            return m
        with con() as c:
            r = c.execute("SELECT * FROM fixtures WHERE id=?", (mid,)).fetchone()
            if not r: return None
            m = self._decorate(r, self._results_idx() if r["provider"] == "openfootball" else None, full=True)
            h, a = r["home"], r["away"]
            if h and a:
                m["h2h"] = self._h2h(c, r["league"], h, a); m["form"] = dict(home=self._form(c, r["league"], h), away=self._form(c, r["league"], a))
                m["season"] = dict(home=self._season_avgs(c, r["league"], h), away=self._season_avgs(c, r["league"], a))
            else:
                m["h2h"] = m["form"] = None
        if m["status"] in LIVE:
            live = self._live_extra(m); m["live_extra"] = live
            pre = m.get("pred") or {}
            if pre.get("available") and m["hg"] is not None:
                minute, est = m["minute"], False
                if live.get("available") and live.get("minute") is not None:
                    minute = live["minute"]
                if minute is None:
                    if m["status"] == "PAUSED": minute = 45
                    elif m["utc"]:
                        el = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(m["utc"].replace("Z", "+00:00"))).total_seconds() / 60
                        minute = int(max(1, min(90, el if el <= 47 else max(46, el - 17)))); est = True
                if minute is not None:
                    sot = (live.get("statistics") or {}).get("Shots on Goal") or {}
                    ok_sot = isinstance(sot.get("h"), (int, float)) and isinstance(sot.get("a"), (int, float))
                    m["inplay"] = predict.inplay(self.bundle, pre, minute, m["hg"], m["ag"], live.get("red_h", 0) or 0, live.get("red_a", 0) or 0,
                                                 sot["h"] if ok_sot else None, sot["a"] if ok_sot else None)
                    m["inplay"]["minute_estimated"] = est
                    m["inplay"]["missing"] = [x for x, ok in (("chutes no gol", ok_sot), ("cartões vermelhos", live.get("available"))) if not ok]
            elif not pre.get("available"):
                m["inplay_unavailable"] = pre.get("reason")
        return m

    def standings(self, league):
        if keys()["fdorg"]:
            r = fdorg.standings(LEAGUES[league]["fd"])
            if r["ok"]:
                tb = next((s for s in r["data"].get("standings", []) if s.get("type") == "TOTAL"), None)
                if tb:
                    amap = aliases.get_map(country_of(league))
                    return dict(source=SOURCES["fdorg"]["label"] + " (tabela oficial)", updated_at=_iso(r["fetched_at"]), stale=r["stale"], error=r["error"],
                                rows=[dict(pos=t["position"], team=t["team"]["name"], canon=amap.get(t["team"]["name"]), p=t["playedGames"], w=t["won"], d=t["draw"],
                                           l=t["lost"], gf=t["goalsFor"], ga=t["goalsAgainst"], gd=t["goalDifference"], pts=t["points"]) for t in tb["table"]])
        self.refresh()
        start = season_start(league, dt.date.today()).isoformat(); T = {}
        with con() as c:
            rows = c.execute("SELECT * FROM results WHERE league=? AND date>=?", (league, start)).fetchall()
        for r in rows:
            for team, gf, ga in ((r["home"], r["hg"], r["ag"]), (r["away"], r["ag"], r["hg"])):
                t = T.setdefault(team, dict(team=team, canon=team, p=0, w=0, d=0, l=0, gf=0, ga=0, pts=0))
                t["p"] += 1; t["gf"] += gf; t["ga"] += ga
                if gf > ga: t["w"] += 1; t["pts"] += 3
                elif gf == ga: t["d"] += 1; t["pts"] += 1
                else: t["l"] += 1
        tab = sorted(T.values(), key=lambda t: (-t["pts"], -(t["gf"] - t["ga"]), -t["gf"], t["team"]))
        for i, t in enumerate(tab): t["pos"] = i + 1; t["gd"] = t["gf"] - t["ga"]
        with con() as c:
            miss = [r[0] for r in c.execute("SELECT DISTINCT home_src FROM fixtures WHERE league=? AND home IS NULL AND provider=?", (league, self.provider()))]
        warn = ("Tabela incompleta: faltam jogos de times ainda não ligados ao histórico (" + ", ".join(miss) + "). "
                "Isso se resolve quando o football-data.co.uk responder ou com a chave do football-data.org.") if miss else None
        return dict(source="Calculada pelo SOFA SD a partir dos resultados reais (football-data.co.uk / openfootball). "
                           "Sem punições ou critérios de desempate oficiais.",
                    data_until=max((r["date"] for r in rows), default=None), rows=tab, error=warn,
                    unavailable=None if tab else "Nenhum resultado da temporada atual disponível nas fontes gratuitas para esta liga.")

    def _season_avgs(self, c, league, canon):
        start = season_start(league, dt.date.today()).isoformat()
        rows = c.execute("SELECT * FROM results WHERE league=? AND date>=? AND (home=? OR away=?)", (league, start, canon, canon)).fetchall()
        def avg(v):
            v = [x for x in v if x is not None]
            return dict(value=round(float(np.mean(v)), 2), n=len(v)) if v else None
        own = lambda r, h, a: r[h] if r["home"] == canon else r[a]
        return dict(played=len(rows), goals_for=avg([own(r, "hg", "ag") for r in rows]), goals_against=avg([own(r, "ag", "hg") for r in rows]),
                    shots=avg([own(r, "hs", "as_") for r in rows]), shots_on_target=avg([own(r, "hst", "ast") for r in rows]),
                    corners=avg([own(r, "hc", "ac") for r in rows]), yellow=avg([own(r, "hy", "ay") for r in rows]))

    def highlights(self):
        """Destaques calculados so com resultados reais da temporada atual."""
        self.refresh(); today = dt.date.today(); teams = []; lg_avg = []; until = None
        with con() as c:
            for lg in LEAGUES:
                rows = c.execute("SELECT * FROM results WHERE league=? AND date>=?", (lg, season_start(lg, today).isoformat())).fetchall()
                if not rows: continue
                until = max(until or "", max(r["date"] for r in rows))
                lg_avg.append(dict(league=lg, name=LEAGUES[lg]["name"], matches=len(rows), goals=round(sum(r["hg"] + r["ag"] for r in rows) / len(rows), 2)))
                T = {}
                for r in rows:
                    for t, gf, ga in ((r["home"], r["hg"], r["ag"]), (r["away"], r["ag"], r["hg"])):
                        x = T.setdefault(t, [0, 0, 0]); x[0] += 1; x[1] += gf; x[2] += ga
                teams += [dict(team=t, league=lg, league_name=LEAGUES[lg]["name"], p=v[0], gf=round(v[1] / v[0], 2), ga=round(v[2] / v[0], 2)) for t, v in T.items() if v[0] >= 4]
            big = c.execute(f"SELECT * FROM results WHERE league IN ({','.join('?'*len(LEAGUES))}) AND date>=? ORDER BY ABS(hg-ag) DESC, hg+ag DESC LIMIT 1",
                            list(LEAGUES) + [(dt.date.fromisoformat(until) - dt.timedelta(days=30)).isoformat() if until else "9999"]).fetchone()
        elo = []
        if self.state:
            act = {(country_of(t["league"]), t["team"]): t for t in teams}
            elo = sorted([dict(team=k[1], league=v["league"], league_name=v["league_name"], elo=round(self.state.t[k]["elo"])) for k, v in act.items() if k in self.state.t],
                         key=lambda x: -x["elo"])[:5]
        return dict(data_until=until, source="Calculado pelo SOFA SD a partir de football-data.co.uk / openfootball",
                    best_attack=max(teams, key=lambda t: t["gf"], default=None), best_defense=min(teams, key=lambda t: t["ga"], default=None),
                    biggest_win=dict(id=f"r|{big['league']}|{big['date']}|{big['home']}|{big['away']}", league_name=LEAGUES[big["league"]]["name"], date=big["date"],
                                     home=big["home"], away=big["away"], hg=big["hg"], ag=big["ag"]) if big else None,
                    top_elo=elo, league_goals=sorted(lg_avg, key=lambda x: -x["goals"]))

    def intelligence(self):
        """SOFA Intelligence: leituras do modelo sobre os proximos jogos reais."""
        self.refresh(); today = dt.date.today()
        with con() as c:
            rows = c.execute("SELECT * FROM fixtures WHERE provider=? AND date>=? AND date<=? AND status IN ('SCHEDULED','TIMED') ORDER BY date",
                             (self.provider(), today.isoformat(), (today + dt.timedelta(days=10)).isoformat())).fetchall()
        ms = []
        for r in rows:
            p = self._pred(r["id"], r["league"], r["home"], r["away"], r["date"])
            if p.get("available"):
                ms.append(dict(id=r["id"], league_name=LEAGUES[r["league"]]["name"], date=r["date"], home=r["home_src"], away=r["away_src"],
                               p_home=p["p_home"], p_draw=p["p_draw"], p_away=p["p_away"], over25=p["over25"], btts=p["btts"],
                               exp_goals=p["exp_home"] + p["exp_away"], stale=bool(p.get("stale_warning"))))
        fav = sorted(ms, key=lambda m: -max(m["p_home"], m["p_away"]))[:4]
        goals = sorted(ms, key=lambda m: -m["over25"])[:4]
        tight = sorted(ms, key=lambda m: abs(m["p_home"] - m["p_away"]))[:4]
        return dict(n_analyzed=len(ms), n_fixtures=len(rows), favorites=fav, goals=goals, balanced=tight,
                    model_trained_at=self.bundle["trained_at"] if self.bundle else None, data_until=self.state.max_date if self.state else None,
                    any_stale=any(m["stale"] for m in ms),
                    unavailable=None if ms else ("Modelos ainda não treinados." if not self.bundle else "Nenhum jogo dos próximos 10 dias tem dados suficientes para previsão."))

    def team(self, league, canon):
        start = season_start(league, dt.date.today()).isoformat()
        with con() as c:
            form = self._form(c, league, canon, 10)
            rows = c.execute("SELECT * FROM results WHERE league=? AND date>=? AND (home=? OR away=?)", (league, start, canon, canon)).fetchall()
            nxt = c.execute("SELECT * FROM fixtures WHERE provider=? AND (home=? OR away=?) AND date>=? AND status IN ('SCHEDULED','TIMED') ORDER BY date LIMIT 5",
                            (self.provider(), canon, canon, dt.date.today().isoformat())).fetchall()
        def avg(pairs):
            v = [x for x in pairs if x is not None]
            return dict(value=round(float(np.mean(v)), 2), n=len(v)) if v else None
        own = lambda r, h, a: r[h] if r["home"] == canon else r[a]
        season = dict(played=len(rows),
                      goals_for=avg([own(r, "hg", "ag") for r in rows]), goals_against=avg([own(r, "ag", "hg") for r in rows]),
                      shots=avg([own(r, "hs", "as_") for r in rows]), shots_on_target=avg([own(r, "hst", "ast") for r in rows]),
                      corners=avg([own(r, "hc", "ac") for r in rows]), yellow=avg([own(r, "hy", "ay") for r in rows]))
        T = self.state.t.get((country_of(league), canon)) if self.state else None
        out = dict(team=canon, league=league, league_name=LEAGUES[league]["name"], form=form, season=season,
                   elo=round(T["elo"]) if T else None, matches_in_history=T["n"] if T else 0,
                   next=[dict(id=r["id"], date=r["date"], time=r["time"], home=r["home_src"], away=r["away_src"]) for r in nxt],
                   source="football-data.co.uk / base histórica aberta; Elo calculado pelo SOFA SD", data_until=self.state.max_date if self.state else None)
        sq = dict(available=False, reason="Elenco exige a chave gratuita do football-data.org.")
        if keys()["fdorg"]:
            r = fdorg.teams(LEAGUES[league]["fd"])
            if r["ok"]:
                amap = aliases.get_map(country_of(league))
                t = next((t for t in r["data"].get("teams", []) if amap.get(t.get("name")) == canon), None)
                if t and t.get("squad"):
                    sq = dict(available=True, source=SOURCES["fdorg"]["label"], updated_at=_iso(r["fetched_at"]), coach=(t.get("coach") or {}).get("name"),
                              players=[dict(name=p.get("name"), position=p.get("position"), nationality=p.get("nationality"), born=p.get("dateOfBirth")) for p in t["squad"]])
                else:
                    sq["reason"] = "A fonte não enviou o elenco deste time no plano gratuito."
            else:
                sq["reason"] = r["error"]
        out["squad"] = sq
        return out

    def crests(self):
        """Escudos enviados pelo football-data.org (precisa da chave gratuita). Chave: nome na fonte e nome no historico."""
        out = {}
        if not keys()["fdorg"]:
            return out
        for lg, cfg in LEAGUES.items():
            r = fdorg.teams(cfg["fd"])
            if not r["ok"]:
                continue
            amap = aliases.get_map(country_of(lg))
            for t in r["data"].get("teams", []):
                c = t.get("crest")
                if not c:
                    continue
                for n in (t.get("name"), t.get("shortName"), amap.get(t.get("name"))):
                    if n:
                        out.setdefault(n, c)
        return out

    def scorers(self, league):
        if not keys()["fdorg"]:
            return dict(available=False, reason="Artilharia e dados de jogadores exigem a chave gratuita do football-data.org. "
                        "As bases históricas abertas não têm dados por jogador.")
        r = fdorg.scorers(LEAGUES[league]["fd"])
        if not r["ok"]:
            return dict(available=False, reason=r["error"])
        return dict(available=True, source=SOURCES["fdorg"]["label"], updated_at=_iso(r["fetched_at"]), stale=r["stale"],
                    rows=[dict(player=(s.get("player") or {}).get("name"), team=(s.get("team") or {}).get("name"), goals=s.get("goals"),
                               assists=s.get("assists"), penalties=s.get("penalties"), played=s.get("playedMatches")) for s in r["data"].get("scorers", [])])

    def status(self):
        k = keys(); src = []
        for s, cfg in SOURCES.items():
            u = usage(s)
            if s == "historico":
                u["last_success"] = db.get_meta("historico_rows")[1]
            src.append(dict(id=s, label=cfg["label"], needs_key=s in ("fdorg", "apifootball"), key_set=bool(k.get(s)) if s in k else None,
                            used_minute=u["used_minute"], limit_minute=u["limit_minute"], used_day=u["used_day"], limit_day=u["limit_day"],
                            last_success=_iso(u["last_success"]), error=self.last_errors.get(s)))
        with con() as c:
            cov = [dict(league=lg, name=LEAGUES[lg]["name"], **dict(c.execute(
                "SELECT COUNT(*) matches, MIN(date) first, MAX(date) last, SUM(hc IS NOT NULL) with_corners FROM results WHERE league=?", (lg,)).fetchone()))
                for lg in LEAGUES]
            total = c.execute("SELECT COUNT(*) n FROM results").fetchone()["n"]
            unmapped = [dict(league=r["league"], name=r["n"]) for r in c.execute(
                "SELECT DISTINCT league, home_src n FROM fixtures WHERE home IS NULL AND provider=?", (self.provider(),))]
        return dict(now=_iso(time.time()), provider=self.provider(), sources=src, coverage=cov, total_matches=total, unmapped_teams=unmapped,
                    models_ready=self.bundle is not None, training=self.training, state_until=self.state.max_date if self.state else None,
                    metrics=json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else None, errors=self.last_errors, cost="R$ 0,00: somente fontes gratuitas")
