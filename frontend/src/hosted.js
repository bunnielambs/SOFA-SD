// Modo hospedado (Netlify): dados reais pre-calculados no GitHub (ramo "data") + ao vivo pelas funcoes /api/live e /api/events.
const DATA = import.meta.env.VITE_DATA_BASE
const AF = { BRA: 71, E0: 39, E1: 40, SP1: 140, I1: 135, D1: 78, F1: 61, N1: 88, P1: 94 }
const LIVE = ['IN_PLAY', 'PAUSED']

export const slug = s => String(s).normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
const todaySP = (off = 0) => new Date(Date.now() + off * 86400000).toLocaleDateString('en-CA', { timeZone: 'America/Sao_Paulo' })

const mem = new Map()
async function file(path, ttl = 300000) {
  const c = mem.get(path); if (c && Date.now() - c.t < ttl) return c.v
  const r = await fetch(`${DATA}/${path}`, { cache: 'no-cache' })
  if (!r.ok) throw new Error(r.status === 404 ? 'não encontrado' : 'HTTP ' + r.status)
  const v = await r.json(); mem.set(path, { t: Date.now(), v }); return v
}
async function live() {
  const c = mem.get('live'); if (c && Date.now() - c.t < 25000) return c.v
  let v; try { const r = await fetch('/api/live', { cache: 'no-store' }); v = await r.json() } catch (e) { v = { available: false, reason: 'Sem conexão com o servidor do SOFA SD.' } }
  mem.set('live', { t: Date.now(), v }); return v
}

function overlay(m, L) {
  const fd = m.extra?.fd_id; if (!fd || !L?.available) return m
  const x = L.matches.find(y => y.fd_id === fd); if (!x) return m
  return { ...m, status: x.status || m.status, minute: x.minute ?? m.minute, hg: x.hg ?? m.hg, ag: x.ag ?? m.ag, hthg: x.hthg ?? m.hthg, htag: x.htag ?? m.htag,
    source: L.source, updated_at: new Date(L.fetched_at).toISOString() }
}
function noScore(m) { // jogo cuja hora ja passou e a fonte ainda nao informou nada
  if (!['SCHEDULED', 'TIMED'].includes(m.status)) return m
  const kick = m.utc ? Date.parse(m.utc) : null
  if ((kick && Date.now() - kick > 3 * 3600000) || (!kick && m.date < todaySP())) return { ...m, status: 'NO_SCORE' }
  return m
}

async function matches(scope, league) {
  if (scope === 'results') {
    const r = await file('results.json'); return { matches: r.matches.filter(m => !league || m.league === league).slice(0, 80) }
  }
  const [F, L] = await Promise.all([file('fixtures.json'), live()])
  let ms = F.matches.map(m => noScore(overlay(m, L))).filter(m => !league || m.league === league)
  const out = { provider: F.provider, provider_label: L.available ? L.source + ' + ' + F.provider_label : F.provider_label, live_available: !!L.available, live_reason: L.available ? null : L.reason }
  if (scope === 'live') {
    if (!L.available) return { ...out, matches: [], unavailable: L.reason }
    return { ...out, matches: ms.filter(m => LIVE.includes(m.status)), note: 'No plano gratuito do football-data.org o placar ao vivo chega com atraso.' + (L.stale ? ' Fonte instável agora: mostrando a última leitura.' : '') }
  }
  if (scope === 'today') return { ...out, matches: ms.filter(m => m.date === todaySP() || LIVE.includes(m.status)) }
  const end = todaySP(14)
  return { ...out, matches: ms.filter(m => m.date >= todaySP() && m.date <= end && ['SCHEDULED', 'TIMED'].includes(m.status)).slice(0, 150) }
}

/* ---- probabilidades ao vivo (mesmo modelo do backend Python) ---- */
const pmf = (l, n) => { const o = [Math.exp(-l)]; for (let k = 1; k < n; k++) o.push(o[k - 1] * l / k); return o }
function markets(lh, la, bh = 0, ba = 0, n = 11) {
  const A = pmf(lh, n), B = pmf(la, n); let s = 0; const P = A.map(a => B.map(b => (s += a * b, a * b)))
  const r = { p_home: 0, p_draw: 0, p_away: 0, btts: 0, over15: 0, over25: 0, over35: 0, exp_home: 0, exp_away: 0 }, top = []
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const p = P[i][j] / s, h = i + bh, a = j + ba, t = h + a
    if (h > a) r.p_home += p; else if (h === a) r.p_draw += p; else r.p_away += p
    if (h > 0 && a > 0) r.btts += p; if (t > 1.5) r.over15 += p; if (t > 2.5) r.over25 += p; if (t > 3.5) r.over35 += p
    r.exp_home += p * h; r.exp_away += p * a; top.push({ score: `${h}-${a}`, p })
  }
  r.top_scores = top.sort((x, y) => y.p - x.p).slice(0, 5); return r
}
function remaining(minute, p1) {
  const m = Math.max(0, Math.min(minute, 90))
  return Math.max(m <= 45 ? (1 - p1) + p1 * (45 - m) / 45 : (1 - p1) * (90 - m) / 45, 0.03)
}
function inplay(par, pre, minute, hg, ag, ex) {
  const r = remaining(minute, par.p_first_half); let lh = pre.lambda_home, la = pre.lambda_away; const used = ['minuto', 'placar'], missing = []
  const sot = ex?.statistics?.['Shots on Goal']
  if (sot && typeof sot.h === 'number' && typeof sot.a === 'number') {
    const e = 1 - r; lh = (lh * par.prior_weight + sot.h * par.sot_conv) / (par.prior_weight + e); la = (la * par.prior_weight + sot.a * par.sot_conv) / (par.prior_weight + e); used.push('chutes no gol')
  } else missing.push('chutes no gol')
  if (ex?.available) {
    const rh = ex.red_h || 0, ra = ex.red_a || 0
    if (rh || ra) { lh *= par.red_own ** rh * par.red_opp ** ra; la *= par.red_own ** ra * par.red_opp ** rh; used.push('cartões vermelhos') }
  } else missing.push('cartões vermelhos')
  return { ...markets(lh * r, la * r, hg, ag), minute, remaining_share: r, inputs_used: used, missing }
}

async function match(id) {
  let m
  try { m = await file(`match/${slug(id)}.json`) } catch (e) { return { error: 'Partida não encontrada nos dados publicados. Ela aparece aqui depois da próxima atualização automática.' } }
  if (m.status === 'FINISHED' && !m.extra?.fd_id) return m
  const L = await live(); m = noScore(overlay(m, L))
  if (!LIVE.includes(m.status)) return m
  let ex = { available: false, reason: 'Eventos ao vivo indisponíveis.' }
  try {
    const q = new URLSearchParams({ league: AF[m.league], home: m.home, away: m.away })
    ex = await (await fetch('/api/events?' + q, { cache: 'no-store' })).json()
  } catch (e) { ex = { available: false, reason: 'Sem conexão com o servidor do SOFA SD.' } }
  m = { ...m, live_extra: ex }
  const pre = m.pred
  if (pre?.available && m.hg != null) {
    const st = await file('status.json', 3600000), par = st.model_params
    let minute = ex.available && ex.minute != null ? ex.minute : m.minute, est = false
    if (minute == null) {
      if (m.status === 'PAUSED') minute = 45
      else if (m.utc) { const el = (Date.now() - Date.parse(m.utc)) / 60000; minute = Math.round(Math.max(1, Math.min(90, el <= 47 ? el : Math.max(46, el - 17)))); est = true }
    }
    if (minute != null) m.inplay = { ...inplay(par, pre, minute, m.hg, m.ag, ex), minute_estimated: est }
  } else if (!pre?.available) m.inplay_unavailable = pre?.reason
  return m
}

export async function hostedApi(path) {
  try {
    const [p, qs] = path.split('?'), q = new URLSearchParams(qs || '')
    if (['leagues', 'highlights', 'intelligence'].includes(p)) return await file(p + '.json')
    if (p === 'status') { const [s, L] = await Promise.all([file('status.json', 60000), live()]); return { ...s, hosted: true, live: L } }
    if (p === 'matches') return await matches(q.get('scope') || 'today', q.get('league') || '')
    if (p === 'match') return await match(q.get('id'))
    if (p.startsWith('standings/') || p.startsWith('scorers/')) return await file(p + '.json')
    if (p === 'team') return await file(`team/${q.get('league')}/${slug(q.get('name'))}.json`)
    return { error: 'recurso desconhecido' }
  } catch (e) {
    return { error: 'Não foi possível carregar os dados publicados (' + e.message + '). Confira a internet e tente de novo.', available: false, reason: 'dados publicados indisponíveis' }
  }
}
