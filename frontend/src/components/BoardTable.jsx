import { useLayoutEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import Avatar from './Avatar.jsx'
import { NEXT, PLATFORMS, cell, fmt, growth, periodLabel } from '../api.js'

function Growth({ value }) {
  if (value === null || value === undefined) return <span className="muted">—</span>
  if (value === 'new') return <span className="growth up">new ▲</span>
  const cls = value > 0 ? 'up' : value < 0 ? 'down' : 'muted'
  return (
    <span className={`growth ${cls}`}>
      {value > 0 ? '+' : ''}{value}% {value > 0 ? '▲' : value < 0 ? '▼' : ''}
    </span>
  )
}

function Delta({ value }) {
  if (!value) return null
  return <span className={`delta ${value > 0 ? 'up' : 'down'}`}> {value > 0 ? '+' : ''}{value}</span>
}

// The leaderboard table. Rows slide to their new place when the order changes (FLIP animation).
export default function BoardTable({ rows, period, mode, best = {}, highlight }) {
  const refs = useRef(new Map())
  const tops = useRef(new Map())
  const order = rows.map((r) => r.id).join(',')

  useLayoutEffect(() => {
    const moved = []
    refs.current.forEach((el, id) => {
      if (!el) return
      const before = tops.current.get(id)
      const now = el.offsetTop
      if (before !== undefined && before !== now) {
        el.style.transition = 'none'
        el.style.transform = `translateY(${before - now}px)`
        moved.push(el)
      }
    })
    if (moved.length) {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        moved.forEach((el) => {
          el.style.transition = 'transform 450ms cubic-bezier(0.2, 0.8, 0.2, 1)'
          el.style.transform = ''
        })
      }))
    }
    const next = new Map()
    refs.current.forEach((el, id) => el && next.set(id, el.offsetTop))
    tops.current = next
  }, [order])

  const next = NEXT[period]
  return (
    <div className="table-wrap">
      <table className="board">
        <thead>
          <tr>
            <th className="l" style={{ width: 92 }}>Standing</th>
            <th className="l">Name</th>
            {PLATFORMS.map((p) => <th key={p.key}>{p.label}</th>)}
            <th>{mode === 'rank' ? 'Rating Sum' : 'Total'}</th>
            <th>{periodLabel(next)}{mode === 'rank' ? ' Δ' : ''}</th>
            <th>Growth</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} ref={(el) => (el ? refs.current.set(r.id, el) : refs.current.delete(r.id))}
              className={highlight === r.id ? 'me' : ''}>
              <td className="l">
                <div className="standing">
                  <span className={`pos m${r.medal}`}>{r.rank}</span>
                  <Link to={`/student/${r.id}`}>
                    <Avatar src={r.avatar} size={28} medal={r.medal} dev={r.role === 'developer'} />
                  </Link>
                </div>
              </td>
              <td className="l name-cell">
                <Link to={`/student/${r.id}`}>{r.name}</Link>
                <div className="sub">{r.batch ? `Batch ${r.batch} · ` : ''}<span className="mono">{r.student_id}</span></div>
              </td>
              {PLATFORMS.map((p) => {
                const c = cell(r, p.key, period, mode)
                if (c.value === null && !c.text) return <td key={p.key} className="val empty">·</td>
                const top = c.value !== null && c.value > 0 && c.value === best[p.key]
                return (
                  <td key={p.key} className={`val${top ? ' top' : ''}`} title={top ? `Highest in ${p.label}` : undefined}>
                    {c.text ?? <b style={{ fontWeight: top ? 600 : 400 }}>{fmt(c.value)}</b>}
                    {mode === 'rank' && <Delta value={c.delta} />}
                    {c.sub && <span className="sub">{mode === 'rank' ? c.sub : `of ${fmt(c.sub)}`}</span>}
                  </td>
                )
              })}
              <td className="val"><b>{fmt(mode === 'rank' ? r.rating : r.solved[period])}</b>
                {mode === 'rank' && <Delta value={r.rating_delta[period]} />}
              </td>
              <td className="val next-col">
                {mode !== 'rank' ? fmt(r.solved[next])
                  : r.rating_delta[next] ? <Delta value={r.rating_delta[next]} /> : <span className="muted">0</span>}
              </td>
              <td><Growth value={growth(r, period, mode)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <div className="empty-state">No students yet. Log in → Settings → Load test data, or add students.</div>}
    </div>
  )
}
