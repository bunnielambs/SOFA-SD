// Acesso ao backend real. Na previa estatica (artefato) as respostas reais ja vem embutidas em window.__SNAP__.
import { useEffect, useRef, useState } from 'react'
import { hostedApi } from './hosted.js'
const SNAP = window.__SNAP__ || null
export const isPreview = !!SNAP
export const isHosted = !SNAP && import.meta.env.VITE_HOSTED === '1'
export const previewWhen = window.__SNAP_WHEN__ || ''

export async function api(path, opts) {
  if (SNAP) {
    if (opts && opts.method === 'POST') return SNAP.status
    let k = path; try { k = decodeURIComponent(path) } catch (e) {}
    return SNAP[k] ?? { error: 'Este item não foi incluído na prévia estática. No app completo ele abre normalmente.', available: false, reason: 'não incluído na prévia estática' }
  }
  if (isHosted) return opts && opts.method === 'POST' ? { error: 'Na versão online os dados se atualizam sozinhos.' } : hostedApi(path)
  try { const r = await fetch('/api/' + path, opts); return await r.json() }
  catch (e) { return { error: 'Sem conexão com o servidor local do SOFA SD.' } }
}

export function useApi(path, every) {
  const [data, setData] = useState(null)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true; setData(null)
    if (!path) return
    const load = () => api(path).then(d => alive.current && setData(d))
    load()
    const t = every && !isPreview ? setInterval(load, every) : null
    return () => { alive.current = false; t && clearInterval(t) }
  }, [path, every])
  return data
}

export const pct = x => x == null ? 'n/d' : Math.round(x * 100) + '%'
export const num = (x, d = 2) => x == null ? 'n/d' : Number(x).toFixed(d).replace('.', ',')
export const dday = s => { if (!s) return 'n/d'; const [y, m, d] = s.split('-'); return d + '/' + m }
export const dtime = s => s ? new Date(s).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'n/d'
export const hhmm = m => m.utc ? new Date(m.utc).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : (m.time || '')
export const longDay = s => new Date(s + 'T12:00').toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })
export const isLive = m => m.status === 'IN_PLAY' || m.status === 'PAUSED'
export const ST = { SCHEDULED: 'Agendado', TIMED: 'Agendado', IN_PLAY: 'Ao vivo', PAUSED: 'Intervalo', FINISHED: 'Encerrado', POSTPONED: 'Adiado', SUSPENDED: 'Suspenso', CANCELLED: 'Cancelado', AWARDED: 'Decidido', NO_SCORE: 'Sem placar na fonte' }

const get = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v) } catch (e) { return d } }
const set = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch (e) {} }
export const store = { get, set }
