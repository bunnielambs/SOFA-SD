// Placar ao vivo do football-data.org (plano gratuito: 10 req/min, placar com atraso).
// A chave fica na variavel FOOTBALL_DATA_ORG_KEY do Netlify; o celular nunca ve a chave.
import { json, readCache, writeCache, sourceError } from "./_shared.mjs"

const COMPS = ["BSA", "PL", "ELC", "PD", "SA", "BL1", "FL1", "DED", "PPL"]
const TTL = 45_000
const SOURCE = "football-data.org (plano gratuito)"
const day = (now, off) => new Date(now + off * 86_400_000).toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" })

export default async () => {
  const key = Netlify.env.get("FOOTBALL_DATA_ORG_KEY")
  if (!key) return json({ available: false, reason: "A chave gratuita do football-data.org ainda não foi configurada no Netlify." })
  const now = Date.now()
  const cached = await readCache("fd-live")
  if (cached && now - cached.fetched_at < TTL) return json({ ...cached, from_cache: true })
  try {
    const r = await fetch(`https://api.football-data.org/v4/matches?dateFrom=${day(now, -1)}&dateTo=${day(now, 1)}`,
      { headers: { "X-Auth-Token": key }, signal: AbortSignal.timeout(12_000) })
    if (!r.ok) throw new Error(sourceError(r.status))
    const j = await r.json()
    const matches = (j.matches || []).filter(m => COMPS.includes(m.competition?.code)).map(m => ({
      fd_id: m.id, comp: m.competition.code, utc: m.utcDate, status: m.status, minute: m.minute ?? null, injury: m.injuryTime ?? null,
      hg: m.score?.fullTime?.home ?? null, ag: m.score?.fullTime?.away ?? null, hthg: m.score?.halfTime?.home ?? null, htag: m.score?.halfTime?.away ?? null,
      home: m.homeTeam?.name, away: m.awayTeam?.name, last_updated: m.lastUpdated || null,
    }))
    const out = { available: true, source: SOURCE, fetched_at: now, matches }
    await writeCache("fd-live", out)
    return json(out)
  } catch (e) {
    const msg = e.name === "TimeoutError" ? "a fonte demorou para responder" : (e.message === "fetch failed" ? "falha de conexão com a fonte" : (e.message || "falha de conexão"))
    if (cached) return json({ ...cached, stale: true, error: msg })
    return json({ available: false, reason: "Não foi possível obter o placar ao vivo: " + msg })
  }
}

export const config = { path: "/api/live" }
