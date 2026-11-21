import { useState } from 'react'

// API client + small shared helpers (ranking, labels, formatting)
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:5000').replace(/\/$/, '')

export const getToken = () => localStorage.getItem('sepc-token')
export const setToken = (t) => (t ? localStorage.setItem('sepc-token', t) : localStorage.removeItem('sepc-token'))

export async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res
  try {
    res = await fetch(API_URL + path, { method, headers, body: form || (body !== undefined ? JSON.stringify(body) : undefined) })
  } catch {
    throw new Error(`Cannot reach the server (${API_URL}). Is the backend running?`)
  }
  const data = await res.json().catch(() => null)
  if (res.status === 401 && token) {
    setToken(null)
    window.dispatchEvent(new Event('sepc-logout'))
  }
  if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`)
  return data
}

export const PLATFORMS = [
  { key: 'codeforces', label: 'Codeforces', short: 'CF' },
  { key: 'leetcode', label: 'LeetCode', short: 'LC' },
  { key: 'beecrowd', label: 'Beecrowd', short: 'BC' },
  { key: 'codechef', label: 'CodeChef', short: 'CC' },
]
export const PERIODS = [
  { key: 'day', label: 'This Day' },
  { key: 'week', label: 'Last Week' },
  { key: 'month', label: 'Last Month' },
  { key: 'all', label: 'All Time' },
]
// the extra column shows the next bigger period
export const NEXT = { day: 'week', week: 'month', month: 'all', all: 'month' }
export const periodLabel = (k) => PERIODS.find((p) => p.key === k)?.label

// value used for ranking
export function score(row, period, mode) {
  if (mode === 'rank') return [row.rating, row.rating_delta[period], row.solved.all]
  return [row.solved[period], row.solved.all, row.rating]
}

export function rankRows(rows, period, mode) {
  const sorted = [...rows].sort((a, b) => {
    const x = score(a, period, mode)
    const y = score(b, period, mode)
    for (let i = 0; i < x.length; i++) if (y[i] !== x[i]) return y[i] - x[i]
    return a.name.localeCompare(b.name)
  })
  return sorted.map((r, i) => ({ ...r, rank: i + 1, medal: score(r, period, mode)[0] > 0 && i < 3 ? i + 1 : 0 }))
}

// growth of the selected period compared with the period before it
export function growth(row, period, mode) {
  if (mode === 'rank') {
    const now = row.rating
    const before = now - row.rating_delta[period]
    if (!before) return null
    return Math.round(((now - before) * 1000) / before) / 10
  }
  const now = period === 'all' ? row.solved.all : row.solved[period]
  const before = row.prev[period]
  if (!before) return now > 0 ? 'new' : null
  return Math.round(((now - before) * 100) / before)
}

// best value of each platform column (to highlight the leader of that platform)
export function platformBest(rows, period, mode) {
  const best = {}
  for (const p of PLATFORMS) {
    best[p.key] = Math.max(0, ...rows.map((r) => cell(r, p.key, period, mode).value ?? 0))
  }
  return best
}

export function cell(row, platform, period, mode) {
  const p = row.p[platform]
  if (!p) return { value: null }
  if (mode === 'rank') {
    if (platform === 'beecrowd') return { value: null, text: p.rank && p.rank !== 'None' ? p.rank : '—', sub: p.rating ? `${Math.round(p.rating)} pts` : '' }
    return { value: p.rating ? Math.round(p.rating) : null, delta: p.rating_delta[period], sub: p.rank }
  }
  return { value: p.solved[period], sub: period === 'all' ? null : `${p.solved.all}` }
}

export function ordinal(n) {
  const s = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th'
  return s
}

export const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('en-US'))

// state that is remembered in the browser (filters shared by leaderboard and profile)
export function useStored(key, initial) {
  const [value, setValue] = useState(() => localStorage.getItem(key) || initial)
  const set = (v) => { localStorage.setItem(key, v); setValue(v) }
  return [value, set]
}
