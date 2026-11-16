import React, { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { api, useApi, pct, num, dday, dtime, hhmm, longDay, isLive, ST, isPreview, isHosted, store } from './api.js'
import { unlock, canVibrate } from './sound.js'
import { Loader, Crest, ProbBar, Meter, ScoreNum, Src, NA, Sec, FormDots, MatchCard, CompareBars, CornerFlag, CardIcon, Toggle } from './ui.jsx'

const Chips = ({ items, value, onChange, all }) => (
  <div className="chips">{all && <button className={value === '' ? 'on' : ''} onClick={() => onChange('')}>Todas</button>}
    {items.map(l => <button key={l.code} className={l.code === value ? 'on' : ''} onClick={() => onChange(l.code)}>{l.name}</button>)}</div>
)
const up = ms => ms.map(m => m.updated_at).filter(Boolean).sort().pop()

/* ---------------- Inicio ---------------- */
export function Home({ ctx }) {
  const { go, today, favs, prefs, savePrefs } = ctx
  const upc = useApi('matches?scope=upcoming'), hi = useApi('highlights'), intel = useApi('intelligence'), leagues = useApi('leagues')
  const live = (today?.matches || []).filter(isLive), rest = (today?.matches || []).filter(m => !isLive(m))
  return (<>
    <div className="hero"><div><p className="eyebrow">{new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}</p>
      <h1>O jogo inteiro,<br />em números reais.</h1></div><div className="stripes" aria-hidden="true" /></div>
    <InstallHint />
    {!prefs.sound && <motion.button className="cta" whileTap={{ scale: 0.97 }} onClick={() => { unlock(); savePrefs({ ...prefs, sound: true }) }}>Ativar som de gol e apitos<small>toca só quando um gol real chegar nos dados</small></motion.button>}

    <Sec title="Ao vivo" tag={live.length ? live.length + ' agora' : null} action="Ver ao vivo" onAction={() => go('live')}>
      {!today ? <Loader /> : live.length ? <div className="hscroll">{live.map(m => <MatchCard key={m.id} m={m} go={go} big />)}</div>
        : <NA>{today.live_available || (!isHosted && today.provider === 'fdorg') ? 'Nenhuma partida em andamento agora nas ligas cobertas.'
          : isHosted ? (today.live_reason || 'Placar ao vivo indisponível agora.') + ' Enquanto isso, o app mostra calendário, resultados e previsões.'
          : 'Placar ao vivo exige a chave gratuita do football-data.org (aba Mais). Sem ela, o app mostra calendário, resultados e previsões.'}</NA>}
    </Sec>

    <Sec title="Jogos de hoje" action="Todos os jogos" onAction={() => go('games')}>
      {!today ? <Loader /> : rest.length ? <div className="list">{rest.slice(0, 8).map(m => <MatchCard key={m.id} m={m} go={go} />)}</div>
        : <NA>Nenhuma partida hoje nas ligas cobertas, segundo a fonte. Nada é preenchido com dados inventados.</NA>}
      {today && <Src label={today.provider_label} when={up(today.matches || [])} />}
    </Sec>

    <Sec title="Próximos jogos" action="Ver todos" onAction={() => go('games', { seg: 'upcoming' })}>
      {!upc ? <Loader /> : upc.matches?.length ? <div className="hscroll">{upc.matches.slice(0, 10).map(m => <MatchCard key={m.id} m={m} go={go} big />)}</div> : <NA>Nenhuma partida nos próximos 14 dias, segundo a fonte.</NA>}
    </Sec>

    <Sec title="Times favoritos">
      {favs.length ? <div className="favs">{favs.map(f => <FavCard key={f.league + f.team} f={f} go={go} />)}</div>
        : <NA>Você ainda não marcou favoritos. Abra uma tabela e toque na estrela ao lado do time.</NA>}
    </Sec>

    <Sec title="SOFA Intelligence" tag="modelo próprio">
      {!intel ? <Loader label="Calculando probabilidades" /> : intel.unavailable ? <NA>{intel.unavailable}</NA> : <>
        <p className="lead">O modelo analisou {intel.n_analyzed} de {intel.n_fixtures} jogos dos próximos 10 dias. São probabilidades estatísticas, não certezas.</p>
        <div className="igrid">
          <IntelCol title="Favoritos mais claros" items={intel.favorites} go={go} val={m => pct(Math.max(m.p_home, m.p_away))} sub={m => (m.p_home > m.p_away ? m.home : m.away)} />
          <IntelCol title="Mais chance de gols" items={intel.goals} go={go} val={m => pct(m.over25)} sub={() => 'mais de 2,5 gols'} />
          <IntelCol title="Jogos mais equilibrados" items={intel.balanced} go={go} val={m => pct(m.p_draw)} sub={() => 'chance de empate'} />
        </div>
        {intel.any_stale && <NA>Parte dessas leituras usa forma recente com mais de 21 dias. Atualize os dados na aba Mais.</NA>}
        <Src label="modelo do SOFA SD treinado com partidas reais" when={intel.model_trained_at} extra={'histórico até ' + dday(intel.data_until)} /></>}
    </Sec>

    <Sec title="Destaques estatísticos" tag="temporada atual">
      {!hi ? <Loader /> : <>
        <div className="tiles">
          {hi.best_attack && <Tile big={num(hi.best_attack.gf)} unit="gols por jogo" label="Melhor ataque" name={hi.best_attack.team} sub={hi.best_attack.league_name + ' · ' + hi.best_attack.p + ' jogos'} onClick={() => go('team', { league: hi.best_attack.league, name: hi.best_attack.team })} />}
          {hi.best_defense && <Tile big={num(hi.best_defense.ga)} unit="sofridos por jogo" label="Melhor defesa" name={hi.best_defense.team} sub={hi.best_defense.league_name + ' · ' + hi.best_defense.p + ' jogos'} onClick={() => go('team', { league: hi.best_defense.league, name: hi.best_defense.team })} />}
          {hi.biggest_win && <Tile big={hi.biggest_win.hg + '-' + hi.biggest_win.ag} unit={dday(hi.biggest_win.date)} label="Maior goleada (30 dias)" name={hi.biggest_win.home + ' x ' + hi.biggest_win.away} sub={hi.biggest_win.league_name} onClick={() => go('match', { id: hi.biggest_win.id })} />}
        </div>
        {hi.top_elo?.length > 0 && <div className="panel"><h3>Ranking de força (Elo do SOFA SD)</h3>
          {hi.top_elo.map((t, i) => <button className="rank" key={t.team} onClick={() => go('team', { league: t.league, name: t.team })}><b>{i + 1}</b><Crest name={t.team} size={26} /><span>{t.team}<small>{t.league_name}</small></span>
            <div className="rbar"><motion.i initial={{ width: 0 }} animate={{ width: ((t.elo - 1500) / (hi.top_elo[0].elo - 1500) * 100) + '%' }} transition={{ duration: 1, delay: i * 0.08 }} /></div><em>{t.elo}</em></button>)}</div>}
        {hi.league_goals?.length > 0 && <div className="panel"><h3>Média de gols por jogo em cada liga</h3>
          {hi.league_goals.map((l, i) => <div className="rank flat" key={l.league}><span>{l.name}<small>{l.matches} jogos</small></span>
            <div className="rbar"><motion.i initial={{ width: 0 }} animate={{ width: (l.goals / hi.league_goals[0].goals * 100) + '%' }} transition={{ duration: 1, delay: i * 0.05 }} /></div><em>{num(l.goals)}</em></div>)}</div>}
        <Src label={hi.source} extra={hi.data_until ? 'resultados até ' + dday(hi.data_until) + '/' + hi.data_until.slice(0, 4) : null} /></>}
    </Sec>

    <Sec title="Campeonatos">
      <div className="comps">{(leagues || []).map(l => <motion.button key={l.code} whileHover={{ y: -3 }} whileTap={{ scale: 0.97 }} onClick={() => go('standings', { league: l.code })}><b>{l.name}</b><span>{l.country}</span></motion.button>)}</div>
    </Sec>
  </>)
}
function InstallHint() {
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent), standalone = window.navigator.standalone || window.matchMedia?.('(display-mode: standalone)').matches
  const [hide, setHide] = useState(() => store.get('sofa_install_hint', false))
  if (!isHosted || !ios || standalone || hide) return null
  return <div className="install"><div><b>Instale no iPhone</b>No Safari, toque em <span className="share" aria-label="Compartilhar" /> Compartilhar e depois em "Adicionar à Tela de Início". O SOFA SD abre em tela cheia, como um app.</div>
    <button onClick={() => { store.set('sofa_install_hint', true); setHide(true) }} aria-label="Fechar">×</button></div>
}
const Tile = ({ big, unit, label, name, sub, onClick }) => (
  <motion.button className="tile" onClick={onClick} whileHover={{ y: -3 }} whileTap={{ scale: 0.97 }}><span className="tl">{label}</span><b>{big}</b><span className="tu">{unit}</span><span className="tn">{name}</span><small>{sub}</small></motion.button>
)
const IntelCol = ({ title, items, go, val, sub }) => (
  <div className="panel"><h3>{title}</h3>{items.map(m => <button className="irow" key={m.id} onClick={() => go('match', { id: m.id })}>
    <span>{m.home} x {m.away}<small>{m.league_name} · {dday(m.date)} · {sub(m)}</small></span><b>{val(m)}</b></button>)}</div>
)
function FavCard({ f, go }) {
  const t = useApi(`team?league=${f.league}&name=${encodeURIComponent(f.team)}`)
  return (<motion.button className="fav" whileHover={{ y: -3 }} onClick={() => go('team', { league: f.league, name: f.team })}><Crest name={f.team} size={38} />
    <div><b>{f.team}</b>{!t ? <small>carregando</small> : t.error ? <small>{t.error}</small> : <><FormDots form={(t.form || []).slice(0, 5)} />
      <small>{t.next?.[0] ? 'Próximo: ' + dday(t.next[0].date) + ' · ' + t.next[0].home + ' x ' + t.next[0].away : 'Sem próximo jogo no calendário da fonte'}</small></>}</div></motion.button>)
}

/* ---------------- Jogos / Ao vivo ---------------- */
export function Games({ ctx, scope, params }) {
  const [seg, setSeg] = useState(params?.seg || 'today'), [league, setLeague] = useState('')
  const leagues = useApi('leagues'), sc = scope || seg
  const r = useApi(`matches?scope=${sc}${league ? '&league=' + league : ''}`, sc === 'live' || sc === 'today' ? 60000 : 0)
  let last = ''
  return (<>
    <h1 className="ptitle">{scope === 'live' ? 'Ao vivo' : 'Jogos'}</h1>
    {!scope && <div className="seg">{[['today', 'Hoje'], ['upcoming', 'Próximos'], ['results', 'Resultados']].map(([k, l]) => <button key={k} className={seg === k ? 'on' : ''} onClick={() => setSeg(k)}>{l}{seg === k && <motion.i layoutId="seg" />}</button>)}</div>}
    <Chips items={leagues || []} value={league} onChange={setLeague} all />
    {!r ? <Loader /> : r.error ? <NA tone="bad">{r.error}</NA> : <>
      {r.unavailable && <NA>{r.unavailable}</NA>}{r.note && <NA>{r.note}</NA>}
      {!r.matches.length && !r.unavailable && <NA>Nenhuma partida {({ today: 'hoje', live: 'ao vivo agora', upcoming: 'nos próximos 14 dias', results: 'encontrada' })[sc]} nas ligas cobertas, segundo a fonte.</NA>}
      <div className="list">{r.matches.map(m => { const h = sc !== 'today' && sc !== 'live' && m.date !== last; last = m.date
        return <React.Fragment key={m.id}>{h && <h3 className="day">{longDay(m.date)}</h3>}<MatchCard m={m} go={ctx.go} big={sc === 'live'} /></React.Fragment> })}</div>
      {sc === 'results' ? <Src label="indicada dentro de cada partida" /> : <Src label={r.provider_label} when={up(r.matches)} />}</>}
  </>)
}

/* ---------------- Partida ---------------- */
function analysis(m) {
  const p = m.pred, out = []; if (!p?.available) return out
  const d = p.p_home - p.p_away, fav = d > 0 ? m.home : m.away, pf = Math.max(p.p_home, p.p_away)
  out.push(Math.abs(d) < 0.08 ? `Jogo equilibrado: ${m.home} ${pct(p.p_home)}, empate ${pct(p.p_draw)}, ${m.away} ${pct(p.p_away)}.`
    : `${fav} chega como favorito, com ${pct(pf)} de chance de vitória. Empate tem ${pct(p.p_draw)}.`)
  out.push(`O modelo espera ${num(p.exp_home + p.exp_away, 1)} gols no total (${num(p.exp_home, 1)} do mandante e ${num(p.exp_away, 1)} do visitante). Mais de 2,5 gols tem ${pct(p.over25)} e ambos marcam tem ${pct(p.btts)}.`)
  out.push(`Em força acumulada (Elo), ${m.home} tem ${p.info.elo_h} e ${m.away} tem ${p.info.elo_a}.`)
  const c = f => (f || []).slice(0, 5).reduce((a, x) => (a[x.res]++, a), { V: 0, E: 0, D: 0 })
  if (m.form) { const a = c(m.form.home), b = c(m.form.away); out.push(`Nos últimos 5 jogos: ${m.home} ${a.V}V ${a.E}E ${a.D}D; ${m.away} ${b.V}V ${b.E}E ${b.D}D.`) }
  if (m.h2h?.summary) { const s = m.h2h.summary; out.push(`Nos últimos ${s.n} confrontos diretos: ${m.home} venceu ${s.home_wins}, ${m.away} venceu ${s.away_wins} e houve ${s.draws} ${s.draws === 1 ? 'empate' : 'empates'}.`) }
  if (p.corners?.available) out.push(`Escanteios esperados: ${num(p.corners.expected, 1)}. Cartões esperados: ${p.cards?.available ? num(p.cards.expected, 1) : 'indisponível'}.`)
  return out
}
const v = x => x ? x.value : null

export function Match({ ctx, params }) {
  const [liveNow, setLiveNow] = useState(false)
  const m = useApi('match?id=' + encodeURIComponent(params.id), liveNow ? 60000 : 0)
  const reds = useRef(null)
  useEffect(() => { if (!m || m.error) return; setLiveNow(isLive(m))
    const ev = m.live_extra?.events; if (!ev) return
    const r = ev.filter(e => e.type === 'Card' && /Red|Second Yellow/.test(e.detail || ''))
    if (reds.current != null && r.length > reds.current) { const e = r[r.length - 1]; ctx.onRed(`${e.player || 'Jogador não informado'} (${e.team || ''})${e.minute ? ' · ' + e.minute + "'" : ''}`) }
    reds.current = r.length }, [m])
  if (!m) return <Loader />
  if (m.error) return <NA tone="bad">{m.error}</NA>
  const live = isLive(m), p = m.pred, ip = m.inplay, L = m.live_extra, fin = m.status === 'FINISHED'
  const T = (n, c) => c ? <button className="tlink" onClick={() => ctx.go('team', { league: m.league, name: c })}>{n}</button> : <span>{n}</span>
  const S = m.season, st = m.stats
  return (<>
    <div className={'scoreboard' + (live ? ' live' : '')}>
      <p className="comp">{m.league_name}{m.round ? ' · ' + m.round : ''}</p>
      <div className="sbrow">
        <div className="side"><Crest name={m.home} url={m.extra?.crest_h} size={64} />{T(m.home, m.home_canon)}</div>
        <div className="mid">{m.hg != null ? <div className="bigscore"><ScoreNum v={m.hg} /><i>:</i><ScoreNum v={m.ag} /></div> : <div className="vs">{hhmm(m) || 'x'}</div>}
          {live ? <span className="clock"><i />{m.status === 'PAUSED' ? 'Intervalo' : ((ip?.minute ?? m.minute) != null ? (ip?.minute ?? m.minute) + "'" : 'Ao vivo')}</span>
            : <span className="state">{ST[m.status] || m.status}</span>}
          {m.hthg != null && <small>1º tempo {m.hthg}-{m.htag}</small>}</div>
        <div className="side"><Crest name={m.away} url={m.extra?.crest_a} size={64} />{T(m.away, m.away_canon)}</div>
      </div>
      <p className="when">{m.utc ? dtime(m.utc) : longDay(m.date) + (m.time ? ' · ' + m.time + ' (horário local da liga)' : '')}</p>
      {ip?.minute_estimated && <p className="when">Minuto estimado pelo horário de início: a fonte não informa o cronômetro.</p>}
    </div>
    <Src label={m.source} when={m.updated_at} />
    {m.status === 'NO_SCORE' && <NA>A data desta partida já passou, mas a fonte gratuita ainda não publicou o placar. O SOFA SD não preenche placar por conta própria.</NA>}

    {ip && <Sec title="Probabilidades ao vivo" tag={'minuto ' + ip.minute}><Probs p={ip} /><p className="src">Dados reais usados: {ip.inputs_used.join(', ')}.{ip.missing.length ? ' Não disponíveis na fonte: ' + ip.missing.join(', ') + '.' : ''} O efeito de expulsão usa valor da literatura.</p></Sec>}
    {m.inplay_unavailable && <NA>Probabilidades ao vivo indisponíveis: {m.inplay_unavailable}</NA>}

    {p && !fin && <Sec title={live ? 'Antes do jogo' : 'Probabilidades'} tag="SOFA Intelligence">
      {p.available ? <><Probs p={p} />
        <div className="two"><StatBox icon={<CornerFlag />} name="Escanteios" unit="escanteios" s={p.corners} /><StatBox icon={<span className="cards2"><CardIcon kind="yellow" /><CardIcon kind="red" /></span>} name="Cartões" unit="cartões" s={p.cards} /></div>
        {p.stale_warning && <NA>{p.stale_warning}</NA>}
        <Src label="modelo próprio do SOFA SD" when={p.model_trained_at} extra={'histórico até ' + dday(p.data_until) + ' · estimativa estatística, não é certeza'} /></>
        : <NA>Previsão indisponível: {p.reason}</NA>}</Sec>}

    {p?.available && !fin && <Sec title="Análise da inteligência artificial">
      <div className="panel ai">{analysis(m).map((t, i) => <motion.p key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.12 * i }}>{t}</motion.p>)}
        <small>Texto montado automaticamente a partir dos números do modelo e do histórico real. Não é palpite humano nem garantia de resultado.</small></div></Sec>}

    <Sec title="Eventos da partida">
      {L?.available ? (L.events.length ? <div className="panel">{L.events.map((e, i) => <div className="ev" key={i}><b>{e.minute ?? ''}'</b>
        {e.type === 'Card' ? <CardIcon kind={/Red|Second/.test(e.detail || '') ? 'red' : 'yellow'} /> : <span className="evdot" />}<span>{e.type === 'Goal' ? 'Gol' : e.type === 'Card' ? 'Cartão' : e.type === 'subst' ? 'Substituição' : e.type}{e.detail ? ': ' + e.detail : ''}<small>{e.player || 'jogador não informado'} · {e.team}</small></span></div>)}<Src label={L.source} when={L.updated_at} /></div> : <NA>Nenhum evento enviado pela fonte até agora.</NA>)
        : <NA>{live ? L?.reason : fin ? 'As fontes gratuitas não guardam os eventos (gols, cartões, substituições) de partidas encerradas.' : 'Eventos aparecem durante o jogo, com a chave gratuita da API-Football.'}</NA>}
    </Sec>

    <Sec title="Estatísticas">
      {L?.statistics ? <div className="panel"><CompareBars home={m.home} away={m.away} rows={Object.entries(L.statistics).filter(([, x]) => typeof x.h === 'number' && typeof x.a === 'number').map(([k, x]) => [k, x.h, x.a])} /><Src label={L.source} when={L.statistics_updated_at} /></div>
        : st ? <div className="panel"><CompareBars home={m.home} away={m.away} rows={[['Finalizações', st.hs, st.as_], ['No gol', st.hst, st.ast], ['Escanteios', st.hc, st.ac], ['Amarelos', st.hy, st.ay], ['Vermelhos', st.hr, st.ar]]} /></div>
          : <NA>{m.stats_unavailable || (live ? (L?.statistics_unavailable || L?.reason) : 'Estatísticas da partida só existem depois do jogo (football-data.co.uk) ou ao vivo (API-Football).')}</NA>}
      {S && <div className="panel"><h3>Médias por jogo na temporada</h3><CompareBars home={m.home} away={m.away} rows={[['Gols marcados', v(S.home.goals_for), v(S.away.goals_for)], ['Gols sofridos', v(S.home.goals_against), v(S.away.goals_against)], ['Finalizações', v(S.home.shots), v(S.away.shots)], ['No gol', v(S.home.shots_on_target), v(S.away.shots_on_target)], ['Escanteios', v(S.home.corners), v(S.away.corners)], ['Amarelos', v(S.home.yellow), v(S.away.yellow)]]} />
        <Src label="football-data.co.uk / base histórica aberta" extra={`${S.home.played} e ${S.away.played} jogos na temporada`} /></div>}
    </Sec>

    <Sec title="Escalações">
      {L?.lineups ? <div className="two">{L.lineups.map(t => <div className="panel" key={t.team}><h3>{t.team}{t.formation ? ' · ' + t.formation : ''}</h3>{t.start.map(x => <div className="pl" key={x.name}><b>{x.number ?? ''}</b><span>{x.name}</span><em>{x.pos || ''}</em></div>)}{t.coach && <small>Técnico: {t.coach}</small>}</div>)}</div>
        : <NA>{live ? (L?.lineups_unavailable || L?.reason) : 'Nenhuma fonte gratuita publica escalações antes ou depois do jogo. Durante a partida elas chegam pela API-Football, se o plano gratuito liberar.'}</NA>}
    </Sec>

    {m.form && <Sec title="Desempenho recente"><div className="panel"><div className="frow"><span>{m.home}</span><FormDots form={m.form.home} /></div><div className="frow"><span>{m.away}</span><FormDots form={m.form.away} /></div><small>Mais recente à esquerda.</small></div></Sec>}
    {m.h2h ? <Sec title="Confrontos diretos">{m.h2h.summary ? <div className="panel">
      <ProbBar h={m.h2h.summary.home_wins / m.h2h.summary.n} d={m.h2h.summary.draws / m.h2h.summary.n} a={m.h2h.summary.away_wins / m.h2h.summary.n} labels={false} />
      <div className="plab"><span>{m.home} {m.h2h.summary.home_wins}</span><span>Empates {m.h2h.summary.draws}</span><span>{m.away} {m.h2h.summary.away_wins}</span></div>
      {m.h2h.matches.map(x => <div className="h2h" key={x.date}><small>{x.date.split('-').reverse().join('/')}</small><span>{x.home}</span><b>{x.hg}-{x.ag}</b><span>{x.away}</span></div>)}
      <Src label="football-data.co.uk / base histórica aberta" /></div> : <NA>Nenhum confronto anterior no histórico.</NA>}</Sec>
      : !fin && <NA>Histórico e confrontos indisponíveis: time ainda não ligado ao histórico.</NA>}
  </>)
}
const Probs = ({ p }) => (<>
  <div className="p3">{[['Casa', p.p_home], ['Empate', p.p_draw], ['Fora', p.p_away]].map(([l, x], i) => <motion.div key={l} className={'pk k' + i} initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: i * 0.08 }}><b>{pct(x)}</b><span>{l}</span></motion.div>)}</div>
  <ProbBar h={p.p_home} d={p.p_draw} a={p.p_away} labels={false} />
  <div className="panel"><h3>Gols</h3><p className="xg"><b>{num(p.exp_home, 1)}</b> x <b>{num(p.exp_away, 1)}</b><span>gols esperados no placar final</span></p>
    <Meter label="Ambos marcam" value={p.btts} /><Meter label="Mais de 1,5 gols" value={p.over15} /><Meter label="Mais de 2,5 gols" value={p.over25} /><Meter label="Mais de 3,5 gols" value={p.over35} />
    <h3>Placares mais prováveis</h3><div className="scores">{p.top_scores.map((s, i) => <motion.div key={s.score} initial={{ height: 0 }} animate={{ height: (s.p / p.top_scores[0].p * 64) + 'px' }} transition={{ duration: 0.8, delay: i * 0.08 }}><em>{pct(s.p)}</em><b>{s.score}</b></motion.div>)}</div></div>
</>)
const StatBox = ({ icon, name, unit, s }) => (
  <div className="panel statbox"><h3>{icon}{name}</h3>{!s ? null : s.available ? <><p className="xg"><b>{num(s.expected, 1)}</b><span>{unit} esperados no jogo</span></p>
    {Object.entries(s.overs).map(([l, x]) => <Meter key={l} label={'Mais de ' + l.replace('.', ',')} value={x} />)}</> : <NA>Indisponível. {s.reason}</NA>}</div>
)

/* ---------------- Tabelas ---------------- */
export function Standings({ ctx, params }) {
  const leagues = useApi('leagues'), [league, setLeague] = useState(params?.league || 'BRA')
  const r = useApi('standings/' + league), isFav = t => ctx.favs.some(f => f.league === league && f.team === t)
  return (<>
    <h1 className="ptitle">Tabelas</h1><Chips items={leagues || []} value={league} onChange={setLeague} />
    {!r ? <Loader /> : <>{r.unavailable && <NA>{r.unavailable}</NA>}{r.error && <NA>{r.error}</NA>}
      {r.rows?.length > 0 && <div className="panel tablewrap"><table><thead><tr><th>#</th><th className="l">Time</th><th>J</th><th>V</th><th>E</th><th>D</th><th>SG</th><th>Pts</th></tr></thead>
        <tbody>{r.rows.map((t, i) => <motion.tr key={t.team} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i * 0.025, 0.5) }}>
          <td>{t.pos}</td><td className="l">{t.canon && <button className={'star' + (isFav(t.canon) ? ' on' : '')} onClick={() => ctx.toggleFav(league, t.canon)} aria-label="Favoritar">{isFav(t.canon) ? '★' : '☆'}</button>}
            {t.canon ? <button className="tlink" onClick={() => ctx.go('team', { league, name: t.canon })}>{t.team}</button> : t.team}</td>
          <td>{t.p}</td><td>{t.w}</td><td>{t.d}</td><td>{t.l}</td><td>{t.gd > 0 ? '+' + t.gd : t.gd}</td><td><b>{t.pts}</b></td></motion.tr>)}</tbody></table></div>}
      <Src label={r.source} when={r.updated_at} extra={r.data_until ? 'resultados até ' + dday(r.data_until) + '/' + r.data_until.slice(0, 4) : null} /></>}
  </>)
}

/* ---------------- Time ---------------- */
export function Team({ ctx, params }) {
  const t = useApi(`team?league=${params.league}&name=${encodeURIComponent(params.name)}`)
  if (!t) return <Loader />; if (t.error) return <NA tone="bad">{t.error}</NA>
  const s = t.season, fav = ctx.favs.some(f => f.league === params.league && f.team === params.name)
  const K = ({ x, l }) => <div className="pk"><b>{x ? num(x.value, 1) : 'n/d'}</b><span>{l}{x ? ` (${x.n} j.)` : ''}</span></div>
  return (<>
    <div className="scoreboard"><div className="teamhead"><Crest name={t.team} size={72} /><div><h1>{t.team}</h1><p className="comp">{t.league_name} · Elo {t.elo ?? 'n/d'} · {t.matches_in_history} partidas no histórico</p>
      <button className={'favbtn' + (fav ? ' on' : '')} onClick={() => ctx.toggleFav(params.league, params.name)}>{fav ? '★ Favorito' : '☆ Favoritar'}</button></div></div></div>
    <Sec title="Temporada atual" tag={s.played + ' jogos'}><div className="p6"><K x={s.goals_for} l="gols pró" /><K x={s.goals_against} l="gols contra" /><K x={s.shots} l="finalizações" /><K x={s.shots_on_target} l="no gol" /><K x={s.corners} l="escanteios" /><K x={s.yellow} l="amarelos" /></div></Sec>
    <Sec title="Últimos jogos"><div className="panel">{t.form.length ? t.form.map(x => <div className="h2h" key={x.date}><small>{x.date.split('-').reverse().join('/')}</small><span>{x.venue === 'C' ? 'casa' : 'fora'} x {x.opponent}</span><b>{x.gf}-{x.ga}</b><span className="form"><i className={'f' + x.res}>{x.res}</i></span></div>) : <small>sem partidas no histórico</small>}</div></Sec>
    {t.next.length > 0 && <Sec title="Próximos jogos"><div className="panel">{t.next.map(x => <button className="irow" key={x.id} onClick={() => ctx.go('match', { id: x.id })}><span>{x.home} x {x.away}<small>{dday(x.date)} {x.time || ''}</small></span><b>›</b></button>)}</div></Sec>}
    <Src label={t.source} extra={t.data_until ? 'histórico até ' + dday(t.data_until) : null} />
    <Sec title="Elenco">{t.squad.available ? <div className="panel">{t.squad.coach && <small>Técnico: {t.squad.coach}</small>}{t.squad.players.map(p => <div className="pl" key={p.name}><span>{p.name}</span><em>{p.position || 'n/d'} · {p.nationality || 'n/d'}</em></div>)}<Src label={t.squad.source} when={t.squad.updated_at} /></div> : <NA>{t.squad.reason}</NA>}</Sec>
  </>)
}

/* ---------------- Mais: ajustes, jogadores, fontes e modelos ---------------- */
export function More({ ctx }) {
  const [sub, setSub] = useState('settings')
  return (<>
    <h1 className="ptitle">Mais</h1>
    <div className="seg">{[['settings', 'Ajustes'], ['players', 'Jogadores'], ['status', 'Fontes e modelos']].map(([k, l]) => <button key={k} className={sub === k ? 'on' : ''} onClick={() => setSub(k)}>{l}{sub === k && <motion.i layoutId="seg2" />}</button>)}</div>
    {sub === 'settings' ? <Settings ctx={ctx} /> : sub === 'players' ? <Players /> : <Status />}
  </>)
}
function Settings({ ctx }) {
  const { prefs, savePrefs } = ctx
  return (<>
    <div className="panel">
      <Toggle id="t-sound" on={prefs.sound} onChange={x => savePrefs({ ...prefs, sound: x })} label="Sons" hint="Gol, apito de início, fim do 1º tempo, apito final e cartão vermelho. Só toca depois de você ligar aqui." />
      <Toggle id="t-vib" on={prefs.vibrate} onChange={x => savePrefs({ ...prefs, vibrate: x })} label="Vibração" hint={canVibrate() ? 'Vibra em gols e eventos importantes.' : 'Este navegador ou aparelho não permite vibração (iPhone, por exemplo).'} />
    </div>
    <div className="panel"><h3>Testar</h3><button className="btn" onClick={ctx.testGoal}>Testar som e animação de gol</button>
      <small>O teste aparece marcado como teste. Em jogo, a comemoração só dispara quando o placar real muda na fonte.</small></div>
    <NA>O app precisa estar aberto na tela para avisar. As consultas acontecem a cada 60 segundos e o placar gratuito do football-data.org chega com atraso, então o aviso de gol não é instantâneo.{/iPhone|iPad/.test(navigator.userAgent) ? ' No iPhone não existe vibração pelo navegador; o aviso vem com som e animação.' : ''}</NA>
  </>)
}
function Players() {
  const leagues = useApi('leagues'), [league, setLeague] = useState('BRA'), r = useApi('scorers/' + league)
  return (<><Chips items={leagues || []} value={league} onChange={setLeague} />
    {!r ? <Loader /> : r.available ? <div className="panel tablewrap"><table><thead><tr><th className="l">Jogador</th><th className="l">Time</th><th>J</th><th>Gols</th><th>Ass.</th></tr></thead>
      <tbody>{r.rows.map(s => <tr key={s.player}><td className="l">{s.player}</td><td className="l">{s.team}</td><td>{s.played ?? 'n/d'}</td><td><b>{s.goals ?? 'n/d'}</b></td><td>{s.assists ?? 'n/d'}</td></tr>)}</tbody></table><Src label={r.source} when={r.updated_at} /></div>
      : <NA>{r.reason}</NA>}</>)
}
function Status() {
  const [s, setS] = useState(null), [k1, setK1] = useState(''), [k2, setK2] = useState(''), [busy, setBusy] = useState('')
  useEffect(() => { api('status').then(setS) }, [])
  const post = async (path, body, label) => { setBusy(label); const r = await api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }); if (r && r.sources) setS(r); else api('status').then(setS); setBusy('') }
  if (!s) return <Loader />; if (s.error) return <NA tone="bad">{s.error}</NA>
  const m = s.metrics, r = m?.r1x2
  return (<>
    <div className="panel"><h3>Fontes de dados · custo zero</h3>{s.sources.map(x => <div className="srcrow" key={x.id}><span>{x.label}{x.error && <small className="bad">{x.error}</small>}</span>
      <em>{x.needs_key ? (x.key_set ? 'chave ok' : 'falta chave') : 'sem chave'}<small>{x.used_minute}/{x.limit_minute} por min{x.limit_day ? ' · ' + x.used_day + '/' + x.limit_day + ' hoje' : ''}</small><small>{x.last_success ? dtime(x.last_success) : 'sem acesso ainda'}</small></em></div>)}</div>
    {s.hosted ? <div className="panel"><h3>Versão online</h3>
      <p className="lead">Dados publicados em {dtime(s.generated_at)}. O GitHub atualiza resultados e previsões 4 vezes por dia e treina os modelos uma vez por semana.</p>
      <div className="srcrow"><span>Placar ao vivo · football-data.org{!s.live?.available && <small className="bad">{s.live?.reason}</small>}{s.live?.error && <small className="bad">{s.live.error}</small>}</span><em>{s.live?.available ? 'funcionando' : 'indisponível'}<small>{s.live?.fetched_at ? dtime(s.live.fetched_at) : ''}</small></em></div>
      <small>Eventos, estatísticas e escalações ao vivo vêm da API-Football quando alguém abre uma partida em andamento (limite de 100 consultas por dia, compartilhado).</small></div> : <>
    <div className="panel"><h3>Chaves gratuitas</h3><small>Ficam salvas só neste computador.</small>
      <label htmlFor="k1">football-data.org</label><input id="k1" value={k1} onChange={e => setK1(e.target.value)} placeholder="cole a chave" disabled={isPreview} />
      <label htmlFor="k2">API-Football</label><input id="k2" value={k2} onChange={e => setK2(e.target.value)} placeholder="cole a chave" disabled={isPreview} />
      {isPreview ? <small>Na prévia estática as chaves ficam desativadas.</small> : <div className="btns"><button className="btn" onClick={() => post('keys', { ...(k1 && { fdorg: k1 }), ...(k2 && { apifootball: k2 }) }, 'k')}>{busy === 'k' ? 'Testando' : 'Salvar e testar'}</button>
        <button className="btn ghost" onClick={() => post('refresh', null, 'r')}>{busy === 'r' ? 'Atualizando' : 'Atualizar dados'}</button><button className="btn ghost" onClick={() => post('retrain', null, 't')}>{s.training ? 'Treinando' : 'Treinar de novo'}</button></div>}</div></>}
    <div className="panel tablewrap"><h3>Partidas reais no banco: {s.total_matches.toLocaleString('pt-BR')}</h3><table><thead><tr><th className="l">Liga</th><th>Partidas</th><th>Até</th><th>Com escanteios</th></tr></thead>
      <tbody>{s.coverage.map(c => <tr key={c.league}><td className="l">{c.name}</td><td>{c.matches}</td><td>{c.last ? dday(c.last) + '/' + c.last.slice(2, 4) : 'n/d'}</td><td>{c.with_corners || 0}</td></tr>)}</tbody></table></div>
    {s.unmapped_teams.length > 0 && <NA>Times do calendário ainda sem ligação confirmada com o histórico (sem previsão): {s.unmapped_teams.map(t => t.name).join(', ')}.</NA>}
    {m ? <div className="panel"><h3>Modelos testados em {m.partidas.teste.toLocaleString('pt-BR')} partidas que nunca viram</h3><small>{m.periodo_teste} · treinado em {dtime(m.treinado_em)}</small>
      <div className="p3"><div className="pk"><b>{num(r.logloss_modelo, 3)}</b><span>SOFA SD</span></div><div className="pk"><b>{num(r.logloss_casas_de_aposta, 3)}</b><span>casas de aposta</span></div><div className="pk"><b>{num(r.logloss_frequencia_base, 3)}</b><span>chute pela frequência</span></div></div>
      <small>Log loss do resultado: quanto menor, melhor.</small>
      <h3>Previsto x aconteceu</h3>{[['Vitória do favorito (acerto)', r.acerto_modelo, r.acerto_casas, 'casas'], ...Object.entries(m.mercados).map(([k, x]) => [({ ambos_marcam: 'Ambos marcam', mais_1_5: 'Mais de 1,5', mais_2_5: 'Mais de 2,5', mais_3_5: 'Mais de 3,5' })[k], x.previsto, x.observado]), ['Escanteios +' + m.escanteios.linha, m.escanteios.previsto_over, m.escanteios.observado_over], ['Cartões +' + m.cartoes.linha, m.cartoes.previsto_over, m.cartoes.observado_over]]
        .map(([l, a, b, alt]) => <div className="cal" key={l}><span>{l}</span><div><Meter label={alt ? 'SOFA SD' : 'previsto'} value={a} /><Meter label={alt || 'aconteceu'} value={b} /></div></div>)}
      <small>Ao vivo: log loss no intervalo {num(m.ao_vivo_intervalo.logloss_no_intervalo, 3)} (antes do jogo {num(m.ao_vivo_intervalo.logloss_pre_jogo_mesmas_partidas, 3)}). {m.ao_vivo_intervalo.nota}</small></div> : <NA>Modelos ainda não treinados.</NA>}
  </>)
}
