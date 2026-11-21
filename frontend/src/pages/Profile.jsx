import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Avatar, { devBadge } from '../components/Avatar.jsx'
import BoardTable from '../components/BoardTable.jsx'
import PerfChart from '../components/PerfChart.jsx'
import Seg from '../components/Seg.jsx'
import { MODES } from './Leaderboard.jsx'
import { PERIODS, PLATFORMS, api, ordinal, periodLabel, platformBest, rankRows, useStored } from '../api.js'

const RANGES = [{ key: '7', label: 'Last Week' }, { key: '30', label: 'Last Month' }, { key: '0', label: 'All Time' }]
const CHART_PLATFORMS = [{ key: 'all', label: 'All' }, ...PLATFORMS.map((p) => ({ key: p.key, label: p.label }))]

// sum the chosen platform(s) for one student: solved totals or ratings
function seriesOf(per, platform, metric, length) {
  const keys = platform === 'all' ? Object.keys(per || {}) : [platform]
  return Array.from({ length }, (_, i) => {
    let sum = null
    for (const k of keys) {
      const v = per?.[k]?.[metric]?.[i]
      if (v !== null && v !== undefined) sum = (sum ?? 0) + v
    }
    return sum
  })
}

export default function Profile() {
  const { id } = useParams()
  const [board, setBoard] = useState(null)
  const [err, setErr] = useState('')
  const [period, setPeriod] = useStored('sepc-period', 'week')
  const [mode, setMode] = useStored('sepc-mode', 'solved')
  const [range, setRange] = useStored('sepc-range', '30')
  const [platform, setPlatform] = useState('all')
  const [hist, setHist] = useState(null)

  useEffect(() => {
    api('/api/board').then(setBoard).catch((e) => setErr(e.message))
  }, [])

  const ranked = useMemo(() => (board ? rankRows(board.rows, period, mode) : []), [board, period, mode])
  const me = ranked.find((r) => String(r.id) === id)
  const leader = ranked[0]
  const best = useMemo(() => platformBest(ranked, period, mode), [ranked, period, mode])

  useEffect(() => {
    if (me) document.title = `${me.name} · SEPC`
  }, [me])

  useEffect(() => {
    if (!me) return
    const ids = leader && leader.id !== me.id ? `${me.id},${leader.id}` : `${me.id}`
    api(`/api/history?ids=${ids}&days=${range}`).then(setHist).catch(() => setHist(null))
  }, [me?.id, leader?.id, range])

  if (err) return <div className="err">{err}</div>
  if (!board) return <div className="empty-state">Loading…</div>
  if (!me) return <div className="empty-state">Student not found. <Link to="/">Back to leaderboard</Link></div>

  const metric = mode === 'rank' ? 'rating' : 'solved'
  const len = hist?.dates.length || 0
  const lines = hist ? [{ kind: 'me', label: me.name, values: seriesOf(hist.series[me.id], platform, metric, len) }] : []
  if (hist && leader && leader.id !== me.id) {
    lines.push({ kind: 'leader', label: `#1 ${leader.name}`, values: seriesOf(hist.series[leader.id], platform, metric, len) })
  }
  const links = [
    me.github && ['GitHub', me.github],
    me.linkedin && ['LinkedIn', me.linkedin],
    ...PLATFORMS.filter((p) => me.p[p.key]).map((p) => [p.label, me.p[p.key].url]),
  ].filter(Boolean)

  return (
    <>
      <div className="toolbar">
        <Link to="/" className="btn">← Leaderboard</Link>
        <span className="grow" />
        <Seg options={PERIODS} value={period} onChange={setPeriod} />
        <Seg options={MODES} value={mode} onChange={setMode} />
      </div>

      <section className="profile-top">
        <Avatar key={`${me.id}-${me.medal}`} src={me.avatar} size={92} medal={me.medal} reveal />
        <div>
          <h1>
            {me.name}
            {me.role === 'developer' && <img src={devBadge} alt="Developer" title="SEPC Developer" width="24" height="24" />}
          </h1>
          <div className="info">Department of {me.department || 'Software Engineering'}</div>
          <div className="info">
            ID: <span className="mono">{me.student_id}</span>{me.batch && <> · Batch {me.batch}</>}
          </div>
          <div className="links">
            {links.map(([label, url]) => <a key={label} href={url} target="_blank" rel="noreferrer">{label} ↗</a>)}
          </div>
        </div>
        <div className={`place p${me.medal}`} title={`${periodLabel(period)} · ${mode}`}>
          <span className="big">{me.rank}</span>
          <sup>{ordinal(me.rank)}</sup>
          <span className="slash" />
          <span className="of">{ranked.length}</span>
        </div>
      </section>

      <BoardTable rows={[me]} period={period} mode={mode} best={best} />

      <div className="section-title">
        Performance
        <span className="grow" style={{ flex: 1 }} />
        <Seg options={CHART_PLATFORMS} value={platform} onChange={setPlatform} />
        <Seg options={RANGES} value={range} onChange={setRange} />
      </div>
      <div className="chart-box">
        <div className="legend">
          <span><i style={{ background: 'var(--accent)', height: 3 }} />{me.name}</span>
          {leader && leader.id !== me.id
            ? <span><i style={{ background: 'var(--muted)', opacity: 0.6 }} />#1 {leader.name}</span>
            : <span className="muted">This student is #1 for {periodLabel(period)}</span>}
          <span className="muted">{mode === 'rank' ? 'Contest rating' : 'Total solved'}</span>
        </div>
        {hist ? <PerfChart dates={hist.dates} lines={lines} animKey={`${platform}${range}${mode}${leader?.id}`} />
          : <div className="empty-state">Loading chart…</div>}
      </div>
    </>
  )
}
