import { useEffect, useMemo, useState } from 'react'
import BoardTable from '../components/BoardTable.jsx'
import Seg from '../components/Seg.jsx'
import { PERIODS, api, platformBest, rankRows, useStored } from '../api.js'

export const MODES = [{ key: 'solved', label: 'Solved' }, { key: 'rank', label: 'Rank' }]

export default function Leaderboard() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [period, setPeriod] = useStored('sepc-period', 'week')
  const [mode, setMode] = useStored('sepc-mode', 'solved')
  const [q, setQ] = useState('')

  useEffect(() => {
    document.title = 'SEPC · Leaderboard'
    api('/api/board').then(setData).catch((e) => setErr(e.message))
  }, [])

  const ranked = useMemo(() => (data ? rankRows(data.rows, period, mode) : []), [data, period, mode])
  const best = useMemo(() => platformBest(ranked, period, mode), [ranked, period, mode])
  const shown = q ? ranked.filter((r) => `${r.name} ${r.student_id} ${r.batch}`.toLowerCase().includes(q.toLowerCase())) : ranked

  return (
    <>
      <div className="toolbar">
        <Seg options={PERIODS} value={period} onChange={setPeriod} />
        <input className="input" placeholder="Search name / ID" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 170 }} />
        <span className="grow" />
        {data && <span className="meta-line">{ranked.length} students · data of {data.as_of}</span>}
        <Seg options={MODES} value={mode} onChange={setMode} />
      </div>
      {err && <div className="err">{err}</div>}
      {!data && !err && <div className="empty-state">Loading…</div>}
      {data && <BoardTable rows={shown} period={period} mode={mode} best={best} />}
      <p className="meta-line" style={{ marginTop: 6 }}>
        {mode === 'solved'
          ? 'Solved: problems solved in the selected period (small number = platform total). Growth compares with the period before.'
          : 'Rank: contest ratings (Codeforces + LeetCode + CodeChef), with the change in the selected period. Beecrowd shows site rank.'}
      </p>
    </>
  )
}
