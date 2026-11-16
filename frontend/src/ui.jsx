import React, { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { pct, dday, dtime, hhmm, isLive, ST, isPreview } from './api.js'

export const Logo = ({ small }) => (
  <div className={'logo' + (small ? ' sm' : '')} aria-label="SOFA SD">
    <svg viewBox="0 0 40 40" className="mark" aria-hidden="true">
      <circle cx="20" cy="20" r="18.5" fill="#fff" />
      <path d="M20 9.5l9.6 7-3.7 11.3H14.1L10.4 16.5z" fill="#050505" />
      <path d="M20 1.5v8M38 14.6l-8.4 1.9M31.2 36l-5.3-8.2M8.8 36l5.3-8.2M2 14.6l8.4 1.9" stroke="#050505" strokeWidth="2.2" />
    </svg>
    <span className="w1">SOFA</span><span className="w2">SD</span>
  </div>
)

export const GoalSvg = ({ shake, ball = true }) => (
  <svg viewBox="0 0 120 70" className={'goalsvg' + (shake ? ' shake' : '')} aria-hidden="true">
    <g className="net" stroke="currentColor" strokeWidth="0.6" opacity="0.55">
      {Array.from({ length: 13 }, (_, i) => <path key={'v' + i} d={`M${12 + i * 8} 10V58`} />)}
      {Array.from({ length: 6 }, (_, i) => <path key={'h' + i} d={`M10 ${14 + i * 8}H110`} />)}
    </g>
    <path d="M10 60V10H110V60" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M2 61H118" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
    {ball && <g className="ballin"><circle r="6" fill="#fff" stroke="#050505" strokeWidth="1" /><path d="M0-3l2.9 2.1-1.1 3.4h-3.6l-1.1-3.4z" fill="#050505" /></g>}
  </svg>
)

export const Loader = ({ label = 'Buscando dados reais' }) => (
  <div className="loader" role="status"><GoalSvg shake /><span>{label}</span></div>
)

const initials = n => { const w = String(n || '?').replace(/\b(FC|CF|AFC|SC|AC|EC|CA|CR|SE|RB|de|do|da)\b/gi, ' ').trim().split(/\s+/).filter(Boolean); return ((w[0]?.[0] || '?') + (w[1]?.[0] || w[0]?.[1] || '')).toUpperCase() }
const hash = s => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h) }
// Escudo generico em monograma: nao copia escudo oficial de clube nenhum. Com chave do football-data.org usa o escudo enviado pela fonte.
export function Crest({ name, url, size = 44 }) {
  const [bad, setBad] = React.useState(false)
  if (url && !bad && !isPreview) return <img className="crest" src={url} width={size} height={size} alt="" onError={() => setBad(true)} loading="lazy" />
  const v = hash(name) % 3, dark = v === 1
  return (
    <svg className="crest" width={size} height={size} viewBox="0 0 44 44" aria-hidden="true">
      <path d="M22 2l17 5v14c0 10-7 17-17 21C12 38 5 31 5 21V7z" fill={dark ? '#0b0b0b' : '#fff'} stroke="#fff" strokeWidth="1.6" />
      {v === 2 && <path d="M12 5.5v31M22 3v39M32 5.5v31" stroke="#0b0b0b" strokeWidth="3.4" opacity="0.14" />}
      <text x="22" y="27" textAnchor="middle" fontFamily="Barlow Condensed, sans-serif" fontWeight="800" fontSize="15" fill={dark ? '#fff' : '#0b0b0b'}>{initials(name)}</text>
    </svg>
  )
}

export const ProbBar = ({ h, d, a, labels = true }) => (
  <div className="prob">
    <div className="track">
      {[[h, 'ph'], [d, 'pd'], [a, 'pa']].map(([v, c], i) => (
        <motion.i key={c} className={c} initial={{ width: 0 }} animate={{ width: (v * 100) + '%' }} transition={{ duration: 0.9, delay: 0.1 * i, ease: [0.2, 0.8, 0.2, 1] }} />))}
    </div>
    {labels && <div className="plab"><span>Casa {pct(h)}</span><span>Empate {pct(d)}</span><span>Fora {pct(a)}</span></div>}
  </div>
)

export const Meter = ({ label, value, sub }) => (
  <div className="meter">
    <div className="mhead"><span>{label}</span><b>{pct(value)}</b></div>
    <div className="mtrack"><motion.i initial={{ width: 0 }} animate={{ width: ((value || 0) * 100) + '%' }} transition={{ duration: 1, ease: 'easeOut' }} /></div>
    {sub && <small>{sub}</small>}
  </div>
)

export const ScoreNum = ({ v }) => (
  <span className="scorenum"><AnimatePresence mode="popLayout" initial={false}>
    <motion.b key={String(v)} initial={{ y: '-90%', opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: '90%', opacity: 0 }} transition={{ type: 'spring', stiffness: 380, damping: 26 }}>{v ?? ''}</motion.b>
  </AnimatePresence></span>
)

export const Src = ({ label, when, extra }) => <p className="src">Fonte: {label || 'n/d'}{when ? ' · Atualizado: ' + dtime(when) : ''}{extra ? ' · ' + extra : ''}</p>
export const NA = ({ children, tone }) => <div className={'na ' + (tone || '')}>{children}</div>
export const Sec = ({ title, action, onAction, children, tag }) => (
  <section className="sec"><header><h2>{title}{tag && <em>{tag}</em>}</h2>{action && <button className="link" onClick={onAction}>{action}</button>}</header>{children}</section>
)
export const FormDots = ({ form }) => form && form.length
  ? <span className="form">{form.map((x, i) => <motion.i key={i} className={'f' + x.res} title={`${x.date} ${x.venue === 'C' ? 'casa' : 'fora'} x ${x.opponent} ${x.gf}-${x.ga}`} initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: i * 0.06 }}>{x.res}</motion.i>)}</span>
  : <small className="mut">sem partidas no histórico</small>

export function MatchCard({ m, go, big }) {
  const live = isLive(m), p = m.pred
  return (
    <motion.button className={'mcard' + (live ? ' live' : '') + (big ? ' big' : '')} onClick={() => go('match', { id: m.id })} whileHover={{ y: -3 }} whileTap={{ scale: 0.98 }} layout>
      <div className="mtop"><span>{m.league_name}{m.round ? ' · ' + m.round : ''}</span>
        {live ? <span className="livetag"><i />{m.status === 'PAUSED' ? 'INTERVALO' : (m.minute ? m.minute + "'" : 'AO VIVO')}</span> : <span>{m.status === 'FINISHED' ? 'Encerrado · ' + dday(m.date) : m.status === 'NO_SCORE' ? 'Sem placar na fonte' : dday(m.date) + (hhmm(m) ? ' · ' + hhmm(m) : '')}</span>}</div>
      <div className="mrow"><Crest name={m.home} url={m.extra?.crest_h} size={big ? 40 : 30} /><span className="tn">{m.home}</span><ScoreNum v={m.hg} /></div>
      <div className="mrow"><Crest name={m.away} url={m.extra?.crest_a} size={big ? 40 : 30} /><span className="tn">{m.away}</span><ScoreNum v={m.ag} /></div>
      {p && (p.available ? <ProbBar h={p.p_home} d={p.p_draw} a={p.p_away} /> : <div className="plab"><span>Previsão indisponível: {p.reason}</span></div>)}
    </motion.button>
  )
}

export const CompareBars = ({ rows, home, away }) => (
  <div className="cmp">
    <div className="cmph"><span>{home}</span><span>{away}</span></div>
    {rows.map(([label, a, b]) => { const ok = a != null && b != null, mx = Math.max(a || 0, b || 0, 0.001); return (
      <div className="cmpr" key={label}><div className="cmpl"><b>{ok ? String(a).replace('.', ',') : 'n/d'}</b><span>{label}</span><b>{ok ? String(b).replace('.', ',') : 'n/d'}</b></div>
        <div className="cmpt"><div className="l">{ok && <motion.i initial={{ width: 0 }} animate={{ width: (a / mx * 100) + '%' }} transition={{ duration: 0.9 }} />}</div>
          <div className="r">{ok && <motion.i initial={{ width: 0 }} animate={{ width: (b / mx * 100) + '%' }} transition={{ duration: 0.9 }} />}</div></div></div>) })}
  </div>
)

export const CornerFlag = () => (
  <svg className="cflag" viewBox="0 0 40 40" aria-hidden="true"><path d="M4 36A30 30 0 0 0 34 6" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.5" /><path d="M8 36V8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><path className="flag" d="M8 8l14 4-14 6z" fill="currentColor" /></svg>
)
export const CardIcon = ({ kind }) => <motion.i className={'cardico ' + kind} initial={{ rotateY: 90, y: -8 }} animate={{ rotateY: 0, y: 0 }} transition={{ type: 'spring', stiffness: 200, damping: 12 }} whileHover={{ rotate: -12, y: -3 }} />

// Comemoracao. So aparece quando um gol real chega nos dados (ou no botao de teste, com aviso claro).
export function GoalOverlay({ ev, onClose }) {
  useEffect(() => { if (!ev) return; const t = setTimeout(onClose, 6500); return () => clearTimeout(t) }, [ev])
  return (
    <AnimatePresence>{ev && (
      <motion.div className="goalov" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="alert">
        <div className="confetti" aria-hidden="true">{Array.from({ length: 26 }, (_, i) => <i key={i} style={{ left: (i * 37 % 100) + '%', animationDelay: (i % 9) * 0.12 + 's', background: i % 3 ? '#fff' : '#777' }} />)}</div>
        <motion.div className="goalbox" initial={{ scale: 0.6, y: 40 }} animate={{ scale: 1, y: 0 }} transition={{ type: 'spring', stiffness: 220, damping: 14 }}>
          <GoalSvg shake />
          <motion.h1 initial={{ letterSpacing: '-0.1em', opacity: 0 }} animate={{ letterSpacing: '0.04em', opacity: 1 }} transition={{ duration: 0.6 }}>GOOOOL!</motion.h1>
          {ev.test ? <p className="gtest">Teste de som e animação. Não é um gol real.</p> : <>
            <p className="gteam">{ev.team}</p>
            <p className="gscore">{ev.home} <b>{ev.hg}</b> x <b>{ev.ag}</b> {ev.away}</p>
            <p className="gwho">{ev.scorer ? ev.scorer : 'Autor do gol não informado pela fonte'}{ev.minute ? ' · ' + ev.minute + "'" : ''}</p>
            <p className="gsrc">{ev.league}</p></>}
          <small>toque para fechar</small>
        </motion.div>
      </motion.div>)}</AnimatePresence>
  )
}

export const Toasts = ({ items }) => (
  <div className="toasts" aria-live="polite"><AnimatePresence>{items.map(t => (
    <motion.div key={t.id} className={'toast ' + (t.kind || '')} initial={{ y: -30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ x: 80, opacity: 0 }}>
      {t.kind === 'red' && <CardIcon kind="red" />}<div><b>{t.title}</b><span>{t.text}</span></div></motion.div>))}</AnimatePresence></div>
)
export const BallsBg = () => <div className="ballsbg" aria-hidden="true"><i /><i /></div>
export const Toggle = ({ on, onChange, label, hint, id }) => (
  <label className="toggle" htmlFor={id}><div><b>{label}</b>{hint && <small>{hint}</small>}</div>
    <input id={id} type="checkbox" checked={on} onChange={e => onChange(e.target.checked)} /><span className="sw"><i /></span></label>
)
