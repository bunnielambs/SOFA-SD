import React, { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence, MotionConfig } from 'framer-motion'
import { api, isPreview, previewWhen, isLive, store, loadCrests } from './api.js'
import { play, unlock, audioReady } from './sound.js'
import { Logo, GoalOverlay, Toasts, BallsBg } from './ui.jsx'
import { Home, Games, Match, Standings, Team, More } from './pages.jsx'

const TABS = [['home', 'Início', 'M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z'], ['live', 'Ao vivo', 'M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14'],
  ['games', 'Jogos', 'M4 5h16v15H4zM4 10h16M9 3v4M15 3v4'], ['standings', 'Tabelas', 'M4 6h16M4 12h16M4 18h10'], ['more', 'Mais', 'M5 12h.01M12 12h.01M19 12h.01']]

export default function App() {
  const [stack, setStack] = useState([{ name: 'home', params: {} }])
  const route = stack[stack.length - 1]
  const go = useCallback((name, params = {}) => { setStack(s => TABS.some(t => t[0] === name) ? [{ name, params }] : [...s, { name, params }]); window.scrollTo(0, 0) }, [])
  const back = useCallback(() => setStack(s => s.length > 1 ? s.slice(0, -1) : s), [])
  const [prefs, setPrefs] = useState(() => store.get('sofa_prefs', { sound: false, vibrate: true }))
  const prefsRef = useRef(prefs); prefsRef.current = prefs
  const savePrefs = p => { setPrefs(p); store.set('sofa_prefs', p); if (p.sound) unlock() }
  const [favs, setFavs] = useState(() => store.get('sofa_favs', []))
  const toggleFav = (league, team) => setFavs(f => { const has = f.some(x => x.league === league && x.team === team); const n = has ? f.filter(x => !(x.league === league && x.team === team)) : [...f, { league, team }]; store.set('sofa_favs', n); return n })
  const [userName, setUserNameState] = useState(() => store.get('sofa_name', 'Sérgio Domingos'))
  const setUserName = n => { setUserNameState(n); store.set('sofa_name', n) }
  const [goal, setGoal] = useState(null), [toasts, setToasts] = useState([]), [today, setToday] = useState(null)
  const toast = useCallback(t => { const id = Date.now() + Math.random(); setToasts(x => [...x, { ...t, id }]); setTimeout(() => setToasts(x => x.filter(y => y.id !== id)), 7000) }, [])
  const prev = useRef(null)
  const [, setCrestsReady] = useState(0)
  useEffect(() => { loadCrests().then(m => setCrestsReady(Object.keys(m).length)) }, [])
  // iPhone e navegadores exigem um toque antes de liberar o som a cada vez que o app abre
  const [audioOk, setAudioOk] = useState(false)
  useEffect(() => {
    if (!prefs.sound) return
    const on = () => { unlock(); setTimeout(() => setAudioOk(audioReady()), 120) }
    window.addEventListener('pointerdown', on); return () => window.removeEventListener('pointerdown', on)
  }, [prefs.sound])

  // Vigia de partidas: compara os dados reais de uma consulta com a anterior. Nada dispara sem mudanca real na fonte.
  useEffect(() => {
    let stop = false
    const tick = async () => {
      const r = await api('matches?scope=today'); if (stop || !r || r.error) return
      setToday(r)
      const now = {}; for (const m of r.matches || []) now[m.id] = m
      if (prev.current) for (const m of r.matches || []) {
        const o = prev.current[m.id]; if (!o) continue
        const P = prefsRef.current, name = `${m.home} x ${m.away}`
        if (!isLive(o) && o.status !== 'FINISHED' && m.status === 'IN_PLAY') { play('kickoff', P); toast({ title: 'Começou', text: name }) }
        if (o.status === 'IN_PLAY' && m.status === 'PAUSED') { play('halftime', P); toast({ title: 'Fim do 1º tempo', text: `${m.home} ${m.hg} x ${m.ag} ${m.away}` }) }
        if (isLive(o) && m.status === 'FINISHED') { play('fulltime', P); toast({ title: 'Fim de jogo', text: `${m.home} ${m.hg} x ${m.ag} ${m.away}` }) }
        if (o.hg != null && m.hg != null && (isLive(m) || isLive(o))) {
          const dh = m.hg - o.hg, da = m.ag - o.ag
          if (dh > 0 || da > 0) {
            const side = dh > 0 ? 'h' : 'a'; play('goal', P)
            const ev = { home: m.home, away: m.away, hg: m.hg, ag: m.ag, team: side === 'h' ? m.home : m.away, minute: m.minute, league: m.league_name }
            setGoal(ev)
            api('match?id=' + encodeURIComponent(m.id)).then(d => { // autor do gol: so se a fonte de eventos informar
              const evs = (d?.live_extra?.events || []).filter(e => e.type === 'Goal'); const last = evs[evs.length - 1]
              if (last) setGoal(g => g && g.home === ev.home ? { ...g, scorer: last.player, minute: last.minute || g.minute } : g)
            })
          } else if (dh < 0 || da < 0) toast({ title: 'Placar corrigido pela fonte', text: `${m.home} ${m.hg} x ${m.ag} ${m.away}` })
        }
      }
      prev.current = now
    }
    tick(); const t = isPreview ? null : setInterval(tick, 60000)
    return () => { stop = true; t && clearInterval(t) }
  }, [toast])

  const ctx = { userName, setUserName, go, back, prefs, savePrefs, favs, toggleFav, today, toast, onRed: (txt) => { play('red', prefsRef.current); toast({ kind: 'red', title: 'Cartão vermelho', text: txt }) },
    testGoal: () => { unlock(); play('goal', { ...prefsRef.current, sound: true }); setGoal({ test: true }) } }
  const Page = { home: Home, live: Games, games: Games, standings: Standings, more: More, match: Match, team: Team }[route.name] || Home
  const tab = TABS.some(t => t[0] === route.name) ? route.name : null
  return (
    <MotionConfig reducedMotion="user">
      <BallsBg />
      <header className="top"><div className="wrap">
        {stack.length > 1 ? <button className="backbtn" onClick={back} aria-label="Voltar">‹ Voltar</button> : <Logo />}
        <button className={'sndbtn' + (prefs.sound ? ' on' : '')} onClick={() => savePrefs({ ...prefs, sound: !prefs.sound })} aria-pressed={prefs.sound}>{prefs.sound ? 'Som ligado' : 'Som desligado'}</button>
      </div></header>
      {isPreview && <div className="wrap"><p className="preview">Prévia estática. Dados reais capturados em {previewWhen}. Ao vivo, notificações de gol e atualização funcionam no app rodando no seu computador.</p></div>}
      <main className="wrap">
        <AnimatePresence mode="wait">
          <motion.div key={route.name + JSON.stringify(route.params)} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.22 }}>
            <Page ctx={ctx} params={route.params} scope={route.name === 'live' ? 'live' : undefined} />
          </motion.div>
        </AnimatePresence>
      </main>
      <nav className="tabs">{TABS.map(([k, l, d]) => (
        <button key={k} className={tab === k ? 'on' : ''} onClick={() => go(k)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg><span>{l}</span>
          {tab === k && <motion.i layoutId="tabdot" className="dot" />}</button>))}</nav>
      {prefs.sound && !audioOk && !isPreview && <button className="unlock" onClick={() => { unlock(); setTimeout(() => setAudioOk(audioReady()), 120) }}>Toque para liberar o som</button>}
      <Toasts items={toasts} />
      <GoalOverlay ev={goal} onClose={() => setGoal(null)} />
    </MotionConfig>
  )
}
