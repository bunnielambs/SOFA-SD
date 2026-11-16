"""Estado dos times (Elo, forma, medias) e vetor de atributos pre-jogo.

Regra de ouro: os atributos de uma partida usam somente partidas ANTERIORES a ela.
"""
import datetime as dt
from collections import deque
import numpy as np
from .config import country_of

TEAM_F = ["gf5", "ga5", "pts5", "gf12", "ga12", "pts12", "sh", "sha", "sot", "sota", "cor", "cora", "card", "carda",
          "v_gf", "v_ga", "v_pts", "rest", "n"]
FEATS = ["elo_h", "elo_a", "elo_diff"] + ["h_" + f for f in TEAM_F] + ["a_" + f for f in TEAM_F] + \
        ["lg_hg", "lg_ag", "lg_cor", "lg_card", "h2h_n", "h2h_gd", "h2h_goals"]
HFA, K = 65.0, 20.0
NAN = float("nan")


def _nm(x):
    x = x[~np.isnan(x)]
    return float(x.mean()) if x.size else NAN


def _ord(d):
    return dt.date.fromisoformat(d[:10]).toordinal()


class State:
    def __init__(self):
        self.t, self.lg, self.h2h, self.seen = {}, {}, {}, {}
        self.max_date = None
        self.n_updates = 0

    def _team(self, key):
        T = self.t.get(key)
        if T is None:
            T = self.t[key] = dict(elo=1500.0, h=deque(maxlen=12), hv=deque(maxlen=6), av=deque(maxlen=6), n=0)
        return T

    def _tf(self, T, at_home, d):
        if not T["h"]:
            return [NAN] * (len(TEAM_F) - 1) + [0.0]
        a = np.array(T["h"], dtype=float)
        l5 = a[-5:]
        out = [l5[:, 2].mean(), l5[:, 3].mean(), l5[:, 4].mean(), a[:, 2].mean(), a[:, 3].mean(), a[:, 4].mean()]
        out += [_nm(a[:, k]) for k in range(5, 13)]
        v = T["hv"] if at_home else T["av"]
        if v:
            va = np.array(v, dtype=float)
            out += [va[:, 2].mean(), va[:, 3].mean(), va[:, 4].mean()]
        else:
            out += [NAN, NAN, NAN]
        out += [float(min(d - a[-1, 0], 30)), float(min(T["n"], 60))]
        return out

    def features(self, league, home, away, date):
        c, d = country_of(league), _ord(date)
        H, A = self._team((c, home)), self._team((c, away))
        f = [H["elo"], A["elo"], H["elo"] - A["elo"]] + self._tf(H, True, d) + self._tf(A, False, d)
        L = self.lg.get(league)
        if L:
            la = np.array(L, dtype=float)
            f += [la[:, 0].mean(), la[:, 1].mean(), _nm(la[:, 2]), _nm(la[:, 3])]
        else:
            f += [NAN] * 4
        hh = self.h2h.get((c, frozenset((home, away))))
        if hh:
            gd = [(x[1] - x[2]) if x[0] == home else (x[2] - x[1]) for x in hh]
            f += [float(len(hh)), float(np.mean(gd)), float(np.mean([x[1] + x[2] for x in hh]))]
        else:
            f += [0.0, NAN, NAN]

        def cnt(T, k):
            return int(sum(1 for r in T["h"] if not np.isnan(r[k])))
        info = dict(n_h=H["n"], n_a=A["n"], cor_h=cnt(H, 9), cor_a=cnt(A, 9), card_h=cnt(H, 11), card_a=cnt(A, 11),
                    elo_h=round(H["elo"]), elo_a=round(A["elo"]),
                    last_h=dt.date.fromordinal(int(H["h"][-1][0])).isoformat() if H["h"] else None,
                    last_a=dt.date.fromordinal(int(A["h"][-1][0])).isoformat() if A["h"] else None)
        return f, info

    def is_dup(self, league, home, away, date):
        last = self.seen.get((league, home, away))
        return last is not None and abs(_ord(date) - last) <= 5

    def update(self, league, home, away, date, hg, ag, hs=NAN, as_=NAN, hst=NAN, ast=NAN, hc=NAN, ac=NAN, hy=NAN, ay=NAN, hr=NAN, ar=NAN):
        c, d = country_of(league), _ord(date)
        f = lambda v: NAN if v is None else float(v)
        hs, as_, hst, ast, hc, ac, hy, ay, hr, ar = map(f, (hs, as_, hst, ast, hc, ac, hy, ay, hr, ar))
        H, A = self._team((c, home)), self._team((c, away))
        exp = 1.0 / (1.0 + 10 ** (-(H["elo"] + HFA - A["elo"]) / 400.0))
        res = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        g = abs(hg - ag)
        mult = 1.0 if g <= 1 else 1.5 if g == 2 else (11 + g) / 8.0
        delta = K * mult * (res - exp)
        H["elo"] += delta; A["elo"] -= delta
        hcard, acard = hy + hr, ay + ar
        hp, ap = (3, 0) if hg > ag else (1, 1) if hg == ag else (0, 3)
        rh = (d, 1, hg, ag, hp, hs, as_, hst, ast, hc, ac, hcard, acard)
        ra = (d, 0, ag, hg, ap, as_, hs, ast, hst, ac, hc, acard, hcard)
        H["h"].append(rh); H["hv"].append(rh); H["n"] += 1
        A["h"].append(ra); A["av"].append(ra); A["n"] += 1
        self.lg.setdefault(league, deque(maxlen=300)).append((hg, ag, hc + ac, hcard + acard))
        self.h2h.setdefault((c, frozenset((home, away))), deque(maxlen=6)).append((home, hg, ag))
        self.seen[(league, home, away)] = d
        if self.max_date is None or date > self.max_date:
            self.max_date = date
        self.n_updates += 1
