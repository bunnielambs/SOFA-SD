"""Probabilidades pre-jogo e ao vivo. Sao estimativas estatisticas, nunca certezas."""
import numpy as np
from scipy.stats import poisson, nbinom

MIN_MATCHES = 8      # historico minimo por time para liberar previsao
MIN_STAT = 5         # partidas recentes com escanteios/cartoes para liberar essas estimativas
RED_OWN, RED_OPP = 2 / 3, 1.2   # hipotese de literatura (Vecer, Kopriva & Ichiba, 2009), nao estimada aqui
PRIOR_WEIGHT = 1.0   # peso (em jogos) da previsao pre-jogo ao combinar com finalizacoes ao vivo


def score_matrix(lh, la, rho=0.0, n=11):
    P = np.outer(poisson.pmf(np.arange(n), lh), poisson.pmf(np.arange(n), la))
    if rho:
        P[0, 0] *= max(1 - lh * la * rho, 1e-6); P[0, 1] *= max(1 + lh * rho, 1e-6)
        P[1, 0] *= max(1 + la * rho, 1e-6); P[1, 1] *= max(1 - rho, 1e-6)
    return P / P.sum()


def markets(P, bh=0, ba=0):
    """P[i,j] = prob. de mais i gols do mandante e j do visitante sobre o placar base."""
    n = P.shape[0]
    i, j = np.meshgrid(np.arange(n) + bh, np.arange(n) + ba, indexing="ij")
    tot = i + j
    top = sorted(((float(P[a, b]), a + bh, b + ba) for a in range(n) for b in range(n)), reverse=True)[:5]
    return dict(
        p_home=float(P[i > j].sum()), p_draw=float(P[i == j].sum()), p_away=float(P[i < j].sum()),
        btts=float(P[(i > 0) & (j > 0)].sum()),
        over15=float(P[tot > 1.5].sum()), over25=float(P[tot > 2.5].sum()), over35=float(P[tot > 3.5].sum()),
        exp_home=float((P * i).sum()), exp_away=float((P * j).sum()),
        top_scores=[dict(score=f"{a}-{b}", p=p) for p, a, b in top])


def _over(mu, alpha, line):
    k = int(np.floor(line))
    if alpha and alpha > 1e-6:
        r = 1.0 / alpha
        return float(nbinom.sf(k, r, r / (r + mu)))
    return float(poisson.sf(k, mu))


def prematch(bundle, state, league, home, away, date):
    f, info = state.features(league, home, away, date)
    out = dict(available=False, info=info, model_trained_at=bundle["trained_at"], data_until=state.max_date)
    if info["n_h"] < MIN_MATCHES or info["n_a"] < MIN_MATCHES:
        out["reason"] = (f"dados insuficientes: {home} tem {info['n_h']} e {away} tem {info['n_a']} partidas no histórico "
                         f"(mínimo {MIN_MATCHES})")
        return out
    import datetime as _dt
    old = [t for t, d in ((home, info["last_h"]), (away, info["last_a"])) if d and (_dt.date.fromisoformat(date[:10]) - _dt.date.fromisoformat(d)).days > 21]
    if old:
        out["stale_warning"] = ("O último resultado conhecido de " + " e ".join(old) + " tem mais de 21 dias. "
                                "A forma recente usada no cálculo pode estar desatualizada.")
    X = np.array([f], dtype=float)
    lh = float(bundle["m_hg"].predict(X)[0]); la = float(bundle["m_ag"].predict(X)[0])
    P = score_matrix(lh, la, bundle["rho"])
    mk = markets(P)
    pc = bundle["m_1x2"].predict_proba(X)[0]  # classes ordenadas: 0=casa,1=empate,2=fora
    w = bundle["w_blend"]
    p = w * np.array([mk["p_home"], mk["p_draw"], mk["p_away"]]) + (1 - w) * pc
    p = p / p.sum()
    mk.update(p_home=float(p[0]), p_draw=float(p[1]), p_away=float(p[2]))
    out.update(available=True, lambda_home=lh, lambda_away=la, **mk)
    # escanteios e cartoes: so com dado suficiente
    for name, mkey, ckey, lines in (("corners", "m_cor", "cor", (8.5, 9.5, 10.5)), ("cards", "m_card", "card", (3.5, 4.5, 5.5))):
        if bundle.get(mkey) is None or min(info[ckey + "_h"], info[ckey + "_a"]) < MIN_STAT:
            out[name] = dict(available=False, reason="a fonte histórica gratuita não traz esse dado para este confronto/liga "
                             f"(mínimo {MIN_STAT} partidas recentes por time)")
        else:
            mu = float(bundle[mkey].predict(X)[0]); a = bundle["alpha_" + ckey]
            out[name] = dict(available=True, expected=mu, overs={str(l): _over(mu, a, l) for l in lines})
    return out


def remaining_share(minute, p1):
    """Fracao dos gols esperados que ainda falta, usando a divisao real 1o/2o tempo do historico."""
    m = max(0, min(int(minute), 90))
    r = (1 - p1) + p1 * (45 - m) / 45 if m <= 45 else (1 - p1) * (90 - m) / 45
    return max(r, 0.03)  # acrescimos: sempre resta algum tempo enquanto o jogo esta em andamento


def inplay(bundle, pre, minute, hg, ag, red_h=0, red_a=0, sot_h=None, sot_a=None):
    """Atualiza as probabilidades com minuto, placar e (se a fonte fornecer) cartoes vermelhos e chutes no gol reais."""
    r = remaining_share(minute, bundle["p_first_half"])
    lh, la = pre["lambda_home"], pre["lambda_away"]
    used = ["minuto", "placar"]
    if sot_h is not None and sot_a is not None:
        e = 1 - r
        lh = (lh * PRIOR_WEIGHT + sot_h * bundle["sot_conv"]) / (PRIOR_WEIGHT + e)
        la = (la * PRIOR_WEIGHT + sot_a * bundle["sot_conv"]) / (PRIOR_WEIGHT + e)
        used.append("chutes no gol")
    if red_h or red_a:
        lh *= RED_OWN ** red_h * RED_OPP ** red_a
        la *= RED_OWN ** red_a * RED_OPP ** red_h
        used.append("cartões vermelhos")
    mk = markets(score_matrix(lh * r, la * r, 0.0), hg, ag)
    mk.update(minute=int(minute), remaining_share=r, inputs_used=used)
    return mk
