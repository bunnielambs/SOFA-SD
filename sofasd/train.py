"""Treino e avaliacao dos modelos com partidas reais. Divisao temporal: nunca se avalia no passado."""
import json, pickle, time, datetime as dt
import numpy as np, pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.metrics import log_loss, brier_score_loss, mean_absolute_error
from .config import MODEL_PATH, METRICS_PATH, DATA
from .db import con
from .features import State, FEATS
from .predict import score_matrix, markets, remaining_share, _over

VALID_FROM, TEST_FROM = "2024-07-01", "2025-07-01"
STATE_PATH = DATA / "state.pkl"


def load_results():
    with con() as c:
        df = pd.read_sql_query("SELECT * FROM results ORDER BY date, league, home", c)
    return df


def build(df, log=print):
    st = State(); X = []; info = []
    t0 = time.time()
    for r in df.itertuples(index=False):
        f, i = st.features(r.league, r.home, r.away, r.date)
        X.append(f); info.append((i["n_h"], i["n_a"], i["cor_h"], i["cor_a"], i["card_h"], i["card_a"]))
        st.update(r.league, r.home, r.away, r.date, r.hg, r.ag, r.hs, r.as_, r.hst, r.ast, r.hc, r.ac, r.hy, r.ay, r.hr, r.ar)
    log(f"  atributos de {len(df)} partidas em {time.time()-t0:.0f}s")
    X = np.array(X, dtype=float)
    I = pd.DataFrame(info, columns=["n_h", "n_a", "cor_h", "cor_a", "card_h", "card_a"])
    return st, X, I


def _reg(it=400):
    return HistGradientBoostingRegressor(loss="poisson", learning_rate=0.05, max_iter=it, max_leaf_nodes=15,
                                         min_samples_leaf=80, l2_regularization=1.0, early_stopping=(it == 400),
                                         validation_fraction=0.1, n_iter_no_change=25, random_state=7)

def _clf(it=400):
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=it, max_leaf_nodes=15, min_samples_leaf=80,
                                          l2_regularization=1.0, early_stopping=(it == 400), validation_fraction=0.1,
                                          n_iter_no_change=25, random_state=7)


def _mk_all(lh, la, rho):
    rows = [markets(score_matrix(a, b, rho)) for a, b in zip(lh, la)]
    return pd.DataFrame(rows)


def train(log=print):
    df = load_results()
    log(f"partidas reais no banco: {len(df)} ({df.date.min()} a {df.date.max()})")
    st, X, I = build(df, log)
    y1x2 = np.where(df.hg > df.ag, 0, np.where(df.hg == df.ag, 1, 2))
    warm = ((I.n_h >= 5) & (I.n_a >= 5)).values
    tr = warm & (df.date < VALID_FROM).values
    va = warm & ((df.date >= VALID_FROM) & (df.date < TEST_FROM)).values
    te = warm & (df.date >= TEST_FROM).values
    cor = (df.hc + df.ac).values; card = (df.hy + df.ay + df.hr.fillna(0) + df.ar.fillna(0)).values
    cor_ok = ~np.isnan(cor) & (I.cor_h >= 5).values & (I.cor_a >= 5).values
    card_ok = ~np.isnan(card) & (I.card_h >= 5).values & (I.card_a >= 5).values

    m_hg = _reg().fit(X[tr], df.hg.values[tr]); m_ag = _reg().fit(X[tr], df.ag.values[tr])
    m_c = _clf().fit(X[tr], y1x2[tr])
    m_cor = _reg().fit(X[tr & cor_ok], cor[tr & cor_ok]); m_card = _reg().fit(X[tr & card_ok], card[tr & card_ok])
    its = dict(hg=m_hg.n_iter_, ag=m_ag.n_iter_, c=m_c.n_iter_, cor=m_cor.n_iter_, card=m_card.n_iter_)
    log(f"  iterações: {its}")

    # --- validacao: correcao de placares baixos (Dixon-Coles), mistura 1X2 e dispersao ---
    lhv, lav = m_hg.predict(X[va]), m_ag.predict(X[va]); hv, av = df.hg.values[va], df.ag.values[va]

    def nll(rho):
        s = 0.0
        for a, b, x, y in zip(lhv, lav, hv, av):
            if x <= 1 and y <= 1:
                tau = (1 - a * b * rho) if (x, y) == (0, 0) else (1 + a * rho) if (x, y) == (0, 1) else (1 + b * rho) if (x, y) == (1, 0) else (1 - rho)
                s -= np.log(max(tau, 1e-9))
        return s
    rho = float(minimize_scalar(nll, bounds=(-0.2, 0.2), method="bounded").x)
    mv = _mk_all(lhv, lav, rho); pm = mv[["p_home", "p_draw", "p_away"]].values; pc = m_c.predict_proba(X[va])
    ws = np.linspace(0, 1, 21)
    w = float(ws[int(np.argmin([log_loss(y1x2[va], x * pm + (1 - x) * pc, labels=[0, 1, 2]) for x in ws]))])

    def alpha(model, y, ok):
        mu = model.predict(X[va & ok]); yy = y[va & ok]
        return float(max(0.0, ((yy - mu) ** 2 - mu).sum() / (mu ** 2).sum()))
    a_cor, a_card = alpha(m_cor, cor, cor_ok), alpha(m_card, card, card_ok)
    ht_ok = df.hthg.notna().values
    p1 = float((df.hthg[tr & ht_ok] + df.htag[tr & ht_ok]).sum() / (df.hg[tr & ht_ok] + df.ag[tr & ht_ok]).sum())
    sot_ok = df.hst.notna().values & tr
    sot_conv = float((df.hg[sot_ok] + df.ag[sot_ok]).sum() / (df.hst[sot_ok] + df.ast[sot_ok]).sum())

    # --- teste fora da amostra ---
    lht, lat = m_hg.predict(X[te]), m_ag.predict(X[te]); ht_, at_ = df.hg.values[te], df.ag.values[te]
    mt = _mk_all(lht, lat, rho)
    p = w * mt[["p_home", "p_draw", "p_away"]].values + (1 - w) * m_c.predict_proba(X[te]); p /= p.sum(1, keepdims=True)
    base = np.bincount(y1x2[tr], minlength=3) / tr.sum()
    odds = df.loc[te, ["odd_h", "odd_d", "odd_a"]].values; ook = ~np.isnan(odds).any(1) & (odds > 1).all(1)
    imp = 1 / odds[ook]; imp /= imp.sum(1, keepdims=True)
    tot = ht_ + at_

    def calib(prob, y, bins=(0, .2, .35, .5, .65, .8, 1.0001)):
        out = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            k = (prob >= lo) & (prob < hi)
            if k.sum() >= 30:
                out.append(dict(faixa=f"{int(lo*100)}-{int(min(hi,1)*100)}%", previsto=float(prob[k].mean()), observado=float(y[k].mean()), n=int(k.sum())))
        return out
    metrics = dict(
        treinado_em=dt.datetime.now().isoformat(timespec="seconds"), dados_ate=str(df.date.max()),
        partidas=dict(total=int(len(df)), treino=int(tr.sum()), validacao=int(va.sum()), teste=int(te.sum())),
        periodo_teste=f"{TEST_FROM} a {df.date.max()}",
        r1x2=dict(logloss_modelo=float(log_loss(y1x2[te], p, labels=[0, 1, 2])),
                  logloss_frequencia_base=float(log_loss(y1x2[te], np.tile(base, (te.sum(), 1)), labels=[0, 1, 2])),
                  logloss_modelo_mesmas_partidas=float(log_loss(y1x2[te][ook], p[ook], labels=[0, 1, 2])),
                  logloss_casas_de_aposta=float(log_loss(y1x2[te][ook], imp, labels=[0, 1, 2])),
                  acerto_modelo=float((p.argmax(1) == y1x2[te]).mean()), acerto_casas=float((imp.argmax(1) == y1x2[te][ook]).mean()),
                  calibracao_vitoria_mandante=calib(p[:, 0], (y1x2[te] == 0).astype(int))),
        gols=dict(mae_mandante=float(mean_absolute_error(ht_, lht)), mae_visitante=float(mean_absolute_error(at_, lat)),
                  mae_ingenuo_mandante=float(mean_absolute_error(ht_, np.full(te.sum(), df.hg.values[tr].mean()))),
                  media_prevista_total=float((lht + lat).mean()), media_real_total=float(tot.mean())),
        mercados={k: dict(brier=float(brier_score_loss(y, mt[c])), brier_base=float(brier_score_loss(y, np.full(len(y), yb))),
                          previsto=float(mt[c].mean()), observado=float(y.mean()), calibracao=calib(mt[c].values, y))
                  for k, c, y, yb in [("ambos_marcam", "btts", ((ht_ > 0) & (at_ > 0)).astype(int), ((df.hg.values[tr] > 0) & (df.ag.values[tr] > 0)).mean()),
                                      ("mais_1_5", "over15", (tot > 1.5).astype(int), ((df.hg + df.ag).values[tr] > 1.5).mean()),
                                      ("mais_2_5", "over25", (tot > 2.5).astype(int), ((df.hg + df.ag).values[tr] > 2.5).mean()),
                                      ("mais_3_5", "over35", (tot > 3.5).astype(int), ((df.hg + df.ag).values[tr] > 3.5).mean())]},
        parametros=dict(rho_dixon_coles=rho, peso_poisson_no_1x2=w, alpha_escanteios=a_cor, alpha_cartoes=a_card,
                        fracao_gols_1o_tempo=p1, gols_por_chute_no_gol=sot_conv))
    for nm, model, y, ok, a, line in (("escanteios", m_cor, cor, cor_ok, a_cor, 9.5), ("cartoes", m_card, card, card_ok, a_card, 4.5)):
        k = te & ok; mu = model.predict(X[k]); yy = y[k]; po = np.array([_over(m, a, line) for m in mu]); yo = (yy > line).astype(int)
        metrics[nm] = dict(n_teste=int(k.sum()), mae=float(mean_absolute_error(yy, mu)), mae_ingenuo=float(mean_absolute_error(yy, np.full(len(yy), y[tr & ok].mean()))),
                           linha=line, brier_over=float(brier_score_loss(yo, po)), brier_base=float(brier_score_loss(yo, np.full(len(yo), (y[tr & ok] > line).mean()))),
                           previsto_over=float(po.mean()), observado_over=float(yo.mean()))
    # ao vivo: validacao no intervalo com placares reais de 1o tempo
    k = te & ht_ok; idx = np.where(k)[0]; sub = np.where(te)[0]; pos = {j: n for n, j in enumerate(sub)}
    bundle_tmp = dict(p_first_half=p1, sot_conv=sot_conv)
    pl = []
    for j in idx:
        n = pos[j]; mk = markets(score_matrix(lht[n] * remaining_share(45, p1), lat[n] * remaining_share(45, p1)), int(df.hthg.values[j]), int(df.htag.values[j]))
        pl.append([mk["p_home"], mk["p_draw"], mk["p_away"]])
    pl = np.clip(np.array(pl), 1e-6, 1); pl /= pl.sum(1, keepdims=True)
    metrics["ao_vivo_intervalo"] = dict(n=int(k.sum()), logloss_no_intervalo=float(log_loss(y1x2[k], pl, labels=[0, 1, 2])),
                                        logloss_pre_jogo_mesmas_partidas=float(log_loss(y1x2[k], p[[pos[j] for j in idx]], labels=[0, 1, 2])),
                                        nota="Validado apenas no minuto 45 (placar real do intervalo). Não existe base gratuita minuto a minuto para validar os demais minutos.")

    # --- reajuste final com todos os dados ---
    al = warm
    bundle = dict(feats=FEATS, trained_at=metrics["treinado_em"], rho=rho, w_blend=w, alpha_cor=a_cor, alpha_card=a_card,
                  p_first_half=p1, sot_conv=sot_conv,
                  m_hg=_reg(its["hg"]).fit(X[al], df.hg.values[al]), m_ag=_reg(its["ag"]).fit(X[al], df.ag.values[al]),
                  m_1x2=_clf(its["c"]).fit(X[al], y1x2[al]),
                  m_cor=_reg(its["cor"]).fit(X[al & cor_ok], cor[al & cor_ok]), m_card=_reg(its["card"]).fit(X[al & card_ok], card[al & card_ok]))
    pickle.dump(bundle, open(MODEL_PATH, "wb")); pickle.dump(st, open(STATE_PATH, "wb"))
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=1))
    return metrics


if __name__ == "__main__":
    from .db import init
    init(); m = train(); print(json.dumps(m, ensure_ascii=False, indent=1))
