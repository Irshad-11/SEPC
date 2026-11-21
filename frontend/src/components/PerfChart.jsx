import { useEffect, useRef, useState } from 'react'
import { fmt } from '../api.js'

// Line chart in plain SVG. lines = [{ label, values: [number|null], kind: 'me' | 'leader' }]
export default function PerfChart({ dates, lines, animKey, unit = '' }) {
  const box = useRef(null)
  const [width, setWidth] = useState(800)
  const [hover, setHover] = useState(null)
  const height = 230
  const pad = { l: 46, r: 12, t: 10, b: 24 }

  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(300, e.contentRect.width)))
    if (box.current) ro.observe(box.current)
    return () => ro.disconnect()
  }, [])

  const all = lines.flatMap((l) => l.values).filter((v) => v !== null && v !== undefined)
  if (!dates.length || !all.length) return <div ref={box} className="empty-state">No history yet. Data appears after the first sync.</div>

  let min = Math.min(...all)
  let max = Math.max(...all)
  if (min === max) { min -= 1; max += 1 }
  const span = max - min
  min = Math.max(0, min - span * 0.08)
  max = max + span * 0.08
  const W = width - pad.l - pad.r
  const H = height - pad.t - pad.b
  const x = (i) => pad.l + (dates.length === 1 ? W / 2 : (i * W) / (dates.length - 1))
  const y = (v) => pad.t + H - ((v - min) / (max - min)) * H

  const path = (values) => {
    let d = ''
    let pen = false
    values.forEach((v, i) => {
      if (v === null || v === undefined) { pen = false; return }
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)} `
      pen = true
    })
    return d
  }
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) * i) / 4)
  const step = Math.max(1, Math.ceil(dates.length / Math.floor(W / 70)))
  const me = lines.find((l) => l.kind === 'me')
  const firstMe = me?.values.findIndex((v) => v !== null)
  const area = me && firstMe >= 0
    ? `${path(me.values)} L${x(me.values.length - 1)} ${pad.t + H} L${x(firstMe)} ${pad.t + H} Z`
    : ''

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    const i = Math.round(((e.clientX - r.left - pad.l) / W) * (dates.length - 1))
    setHover(i >= 0 && i < dates.length ? i : null)
  }

  return (
    <div ref={box} className="chart" style={{ position: 'relative' }}>
      <svg height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <g className="grid">
          {ticks.map((t) => <line key={t} x1={pad.l} x2={pad.l + W} y1={y(t)} y2={y(t)} />)}
        </g>
        <g className="axis">
          {ticks.map((t) => <text key={t} x={pad.l - 6} y={y(t) + 3} textAnchor="end">{fmt(Math.round(t))}</text>)}
          {dates.map((d, i) => (i % step === 0 || i === dates.length - 1) && (
            <text key={d} x={x(i)} y={height - 6} textAnchor="middle">{d.slice(5)}</text>
          ))}
        </g>
        <path key={`a${animKey}`} className="area" d={area} style={{ opacity: 0.8 }} />
        {lines.map((l) => (
          <path key={`${l.kind}${animKey}`} pathLength="1" className={`line draw ${l.kind === 'me' ? 'me-line' : 'leader-line'}`} d={path(l.values)} />
        ))}
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + H} stroke="var(--line2)" />
            {lines.map((l) => l.values[hover] != null && (
              <circle key={l.kind} cx={x(hover)} cy={y(l.values[hover])} r="3.2"
                fill={l.kind === 'me' ? 'var(--accent)' : 'var(--muted)'} />
            ))}
          </g>
        )}
      </svg>
      {hover !== null && (
        <div className="tip" style={{ left: Math.min(x(hover) + 10, width - 170), top: 8 }}>
          <div>{dates[hover]}</div>
          {lines.map((l) => <div key={l.kind}>{l.label}: {fmt(l.values[hover])}{unit}</div>)}
        </div>
      )}
    </div>
  )
}
