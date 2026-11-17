// Eventos, estatisticas e escalacoes ao vivo da API-Football (plano gratuito: 100 req/dia, 10 req/min).
// So consulta quando alguem abre uma partida em andamento. Respostas ficam em cache e a cota do dia e protegida.
import { json, readCache, writeCache, sourceError } from "../lib/shared.mjs"

const SOURCE = "API-Football (plano gratuito)"
const RESERVE = 8 // nunca gastar as ultimas requisicoes do dia
const TTL_LIVE = 180_000, TTL_STATS = 300_000, TTL_LINEUPS = 3_600_000

const norm = s => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
  .split(/[^a-z0-9]+/).filter(t => t && !["fc", "cf", "afc", "sc", "ac", "ec", "ca", "cd", "ud", "fk", "sv", "vfl", "vfb", "tsg", "club", "clube", "de", "do", "da", "futebol", "calcio"].includes(t)).join(" ")
function sim(a, b) { // coeficiente de Dice em bigramas
  a = norm(a); b = norm(b); if (!a || !b) return 0; if (a === b) return 1
  const bg = s => { const o = new Map(); for (let i = 0; i < s.length - 1; i++) { const k = s.slice(i, i + 2); o.set(k, (o.get(k) || 0) + 1) } return o }
  const A = bg(a), B = bg(b); let inter = 0
  for (const [k, n] of A) inter += Math.min(n, B.get(k) || 0)
  return (2 * inter) / (Math.max(a.length - 1, 1) + Math.max(b.length - 1, 1))
}

async function af(path, key) {
  const today = new Date().toISOString().slice(0, 10)
  const q = await readCache("af-quota")
  if (q && q.day === today && q.remaining != null && q.remaining <= RESERVE)
    throw new Error("cota diária gratuita da API-Football praticamente esgotada; volta às 21h (horário de Brasília)")
  let r
  try { r = await fetch("https://v3.football.api-sports.io" + path, { headers: { "x-apisports-key": key }, signal: AbortSignal.timeout(12_000) }) }
  catch (e) { throw new Error(e.name === "TimeoutError" ? "a fonte demorou para responder" : "falha de conexão com a fonte") }
  const rem = r.headers.get("x-ratelimit-requests-remaining")
  if (rem != null) await writeCache("af-quota", { day: today, remaining: Number(rem), at: Date.now() })
  if (!r.ok) throw new Error(sourceError(r.status))
  const j = await r.json()
  if (j.errors && (Array.isArray(j.errors) ? j.errors.length : Object.keys(j.errors).length))
    throw new Error("API recusou: " + JSON.stringify(j.errors))
  return j
}

async function cached(key, ttl, load) {
  const c = await readCache(key)
  if (c && Date.now() - c.at < ttl) return c
  try { const data = await load(); const v = { at: Date.now(), data }; await writeCache(key, v); return v }
  catch (e) { if (c) return { ...c, stale: true, error: e.message }; throw e }
}

export default async (req) => {
  const key = Netlify.env.get("API_FOOTBALL_KEY")
  if (!key) return json({ available: false, reason: "Eventos e estatísticas ao vivo exigem a chave gratuita da API-Football, ainda não configurada no Netlify." })
  const u = new URL(req.url), league = Number(u.searchParams.get("league")), home = u.searchParams.get("home"), away = u.searchParams.get("away")
  if (!league || !home || !away) return json({ available: false, reason: "parâmetros incompletos" }, 400)
  let live
  try { live = await cached("af-live", TTL_LIVE, () => af("/fixtures?live=all", key)) }
  catch (e) { return json({ available: false, reason: e.message }) }
  const fx = (live.data.response || []).filter(f => f.league?.id === league)
    .map(f => ({ f, s: sim(f.teams?.home?.name, home) + sim(f.teams?.away?.name, away) })).sort((a, b) => b.s - a.s)[0]
  if (!fx || fx.s < 1.1) return json({ available: false, reason: "A API-Football não lista esta partida entre os jogos ao vivo agora." })
  const f = fx.f, hid = f.teams.home.id, ev = f.events || []
  const red = side => ev.filter(e => e.type === "Card" && /Red|Second Yellow/.test(e.detail || "") && ((e.team?.id === hid) === (side === "h"))).length
  const out = {
    available: true, source: SOURCE, updated_at: new Date(live.at).toISOString(), stale: !!live.stale, error: live.error || null,
    minute: f.fixture?.status?.elapsed ?? null, hg: f.goals?.home ?? null, ag: f.goals?.away ?? null, red_h: red("h"), red_a: red("a"),
    events: ev.map(e => ({ minute: e.time?.elapsed ?? null, team: e.team?.name, player: e.player?.name, type: e.type, detail: e.detail })),
  }
  try {
    const s = await cached("af-stats-" + f.fixture.id, TTL_STATS, () => af("/fixtures/statistics?fixture=" + f.fixture.id, key))
    const resp = s.data.response || []
    if (resp.length === 2) {
      const st = {}
      resp.forEach((blk, i) => (blk.statistics || []).forEach(it => { (st[it.type] ||= {})[i ? "a" : "h"] = it.value }))
      out.statistics = st; out.statistics_updated_at = new Date(s.at).toISOString()
    } else out.statistics_unavailable = "a fonte não enviou estatísticas para esta partida"
  } catch (e) { out.statistics_unavailable = e.message }
  try {
    const l = await cached("af-lineups-" + f.fixture.id, TTL_LINEUPS, () => af("/fixtures/lineups?fixture=" + f.fixture.id, key))
    const resp = l.data.response || []
    if (resp.length === 2) {
      out.lineups = resp.map(b => ({ team: b.team?.name, formation: b.formation, coach: b.coach?.name,
        start: (b.startXI || []).map(x => ({ name: x.player?.name, number: x.player?.number, pos: x.player?.pos })),
        bench: (b.substitutes || []).map(x => x.player?.name) }))
      out.lineups_updated_at = new Date(l.at).toISOString()
    } else out.lineups_unavailable = "a fonte não enviou as escalações desta partida"
  } catch (e) { out.lineups_unavailable = e.message }
  const q = await readCache("af-quota"); if (q) out.quota_remaining = q.remaining
  return json(out)
}

export const config = { path: "/api/events" }
