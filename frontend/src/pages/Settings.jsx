import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../App.jsx'
import { API_URL, PLATFORMS, api, setToken } from '../api.js'

function LogLine({ l }) {
  return (
    <div>
      <span className="muted">[{l.t}]</span> <span className={l.ok ? 'ok' : 'bad'}>{l.ok ? 'OK ' : 'ERR'}</span>{' '}
      {l.platform.padEnd(10, ' ')} <b>{l.username}</b> {l.student && <span className="muted">{l.student}</span>} → {l.msg}
      {l.ms ? <span className="muted"> ({(l.ms / 1000).toFixed(1)}s)</span> : null}
    </div>
  )
}

export default function Settings() {
  const { user } = useAuth()
  const [status, setStatus] = useState(null)
  const [run, setRun] = useState(null)
  const [log, setLog] = useState([])
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [users, setUsers] = useState([])
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'developer' })
  const [pw, setPw] = useState({ current: '', new: '' })
  const stopRef = useRef(false)
  const logRef = useRef(null)

  const loadStatus = () => api('/api/sync/status').then((s) => {
    setStatus(s)
    if (!syncing && s.latest) { setRun(s.latest); setLog(s.latest.log || []) }
  }).catch((e) => setErr(e.message))
  const loadUsers = () => api('/api/users').then(setUsers).catch(() => {})

  useEffect(() => { document.title = 'Settings · SEPC'; loadStatus(); loadUsers() }, [])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [log])

  async function sync() {
    setErr('')
    setMsg('')
    setSyncing(true)
    stopRef.current = false
    try {
      const start = await api('/api/sync/start', { method: 'POST', body: {} })
      let current = start.run
      setRun(current)
      setLog(start.created ? [] : current.log || [])
      if (!current.total) setMsg('No accounts for the server platforms. Add students first.')
      while (current.status === 'running' && !stopRef.current) {
        const step = await api('/api/sync/step', { method: 'POST', body: { run_id: current.id } })
        current = step.run
        setRun(current)
        setLog((old) => [...old, ...step.lines].slice(-400))
        if (!step.lines.length && current.status === 'running') await new Promise((r) => setTimeout(r, 1500))
      }
      if (current.status === 'finished') setMsg(`Sync finished: ${current.ok} ok, ${current.failed} failed`)
    } catch (e) {
      setErr(`Sync stopped: ${e.message}`)
    } finally {
      setSyncing(false)
      loadStatus()
    }
  }

  async function stop() {
    stopRef.current = true
    await api('/api/sync/stop', { method: 'POST' }).catch(() => {})
  }

  async function action(path, okText) {
    setErr('')
    try {
      await api(path, { method: 'POST' })
      setMsg(okText)
      loadStatus()
    } catch (e) { setErr(e.message) }
  }

  async function addUser(e) {
    e.preventDefault()
    try {
      await api('/api/users', { method: 'POST', body: newUser })
      setNewUser({ username: '', password: '', role: 'developer' })
      setMsg('Login user added')
      loadUsers()
    } catch (e2) { setErr(e2.message) }
  }

  async function changePw(e) {
    e.preventDefault()
    try {
      const d = await api('/api/auth/password', { method: 'POST', body: pw })
      setToken(d.token)
      setPw({ current: '', new: '' })
      setMsg('Password changed')
    } catch (e2) { setErr(e2.message) }
  }

  const pct = run?.total ? Math.round((run.done * 100) / run.total) : 0
  return (
    <>
      <div className="toolbar">
        <b style={{ fontSize: 14 }}>Settings</b>
        <span className="muted">API: <code>{API_URL}</code></span>
        <span className="grow" />
        {msg && <span className="ok-msg">{msg}</span>}
      </div>
      {err && <div className="err">{err}</div>}

      <div className="cols-2">
        <div className="panel">
          <h3>Sync platforms</h3>
          {status && (
            <p className="small">
              Server fetches: <b>{status.server_platforms.join(', ') || 'nothing'}</b>
              {status.on_pythonanywhere ? ' (PythonAnywhere detected)' : ''} · curl_cffi {status.curl_cffi ? 'installed' : 'not installed'}
            </p>
          )}
          <div className="toolbar" style={{ margin: '6px 0' }}>
            <button className="btn primary" onClick={sync} disabled={syncing}>{syncing ? 'Syncing…' : 'Sync now'}</button>
            {syncing && <button className="btn danger" onClick={stop}>Stop</button>}
            {run && (
              <span className="small muted">
                #{run.id} {run.source} · {run.status} · {run.done}/{run.total} · <span className="up">{run.ok} ok</span> ·{' '}
                <span className="down">{run.failed} failed</span>
              </span>
            )}
          </div>
          <div className="bar"><i style={{ width: `${pct}%` }} /></div>
          <div className="log" ref={logRef}>
            {log.length ? log.map((l, i) => <LogLine key={i} l={l} />) : <span className="muted">Log appears here while syncing.</span>}
          </div>
          <p className="small muted">Keep this page open while syncing. The browser asks the server to fetch a few accounts at a time.</p>
        </div>

        <div>
          <div className="panel">
            <h3>Platform status</h3>
            <table className="plain">
              <thead><tr><th>Platform</th><th>Accounts</th><th>OK</th><th>Errors</th><th>Last update</th><th>Fetched by</th></tr></thead>
              <tbody>
                {status && PLATFORMS.map((p) => {
                  const s = status.platforms[p.key]
                  return (
                    <tr key={p.key}>
                      <td>{p.label}</td><td className="mono">{s.accounts}</td><td className="mono up">{s.ok}</td>
                      <td className={`mono ${s.errors ? 'down' : ''}`}>{s.errors}</td>
                      <td className="mono small">{s.last_synced || '—'}</td>
                      <td className="small">{s.on_server ? 'server' : 'local_sync.py'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="small">
              Fallback (CodeChef, Beecrowd, or anything blocked on the server): on your PC run{' '}
              <code>python local_sync.py</code> inside <code>backend/</code>. It fetches every platform and pushes the data here.
            </p>
          </div>

          <div className="panel" style={{ marginTop: 10 }}>
            <h3>Test data</h3>
            <p className="small">16 demo students with real public handles and 60 days of generated history (shows This Day / Week / Month and growth).</p>
            <div className="toolbar" style={{ margin: 0 }}>
              <button className="btn" onClick={() => action('/api/demo/load', 'Test data loaded')}>Load test data</button>
              <button className="btn danger" onClick={() => action('/api/demo/clear', 'Test data cleared')}>Clear test data</button>
            </div>
          </div>

          {status?.errors?.length > 0 && (
            <div className="panel" style={{ marginTop: 10 }}>
              <h3>Accounts with errors ({status.errors.length})</h3>
              <div style={{ maxHeight: 160, overflow: 'auto' }}>
                <table className="plain">
                  <tbody>
                    {status.errors.map((e, i) => (
                      <tr key={i}><td className="small">{e.platform}</td><td className="mono small">{e.username}</td><td className="small down">{e.last_error}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="cols-2" style={{ marginTop: 14 }}>
        <div className="panel">
          <h3>Recent syncs</h3>
          <table className="plain">
            <thead><tr><th>#</th><th>Source</th><th>Started</th><th>Status</th><th>OK</th><th>Failed</th></tr></thead>
            <tbody>
              {status?.runs.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td><td>{r.source}</td><td className="mono small">{r.started_at}</td>
                  <td>{r.status}</td><td className="mono up">{r.ok}</td><td className="mono down">{r.failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <h3>Login users</h3>
          <table className="plain">
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td><td><span className="tag">{u.role}</span></td>
                  <td><div className="row-actions">
                    {user?.role === 'admin' && u.id !== user.id && (
                      <button className="btn danger" onClick={() => api(`/api/users/${u.id}`, { method: 'DELETE' }).then(loadUsers)}>Remove</button>
                    )}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
          {user?.role === 'admin' && (
            <form className="toolbar" onSubmit={addUser}>
              <input className="input" placeholder="username" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} required />
              <input className="input" placeholder="password" type="password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} required />
              <select className="input" value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
                <option value="developer">developer</option><option value="admin">admin</option>
              </select>
              <button className="btn">Add</button>
            </form>
          )}
          <form className="toolbar" onSubmit={changePw}>
            <input className="input" type="password" placeholder="current password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} required />
            <input className="input" type="password" placeholder="new password" value={pw.new} onChange={(e) => setPw({ ...pw, new: e.target.value })} required />
            <button className="btn">Change my password</button>
          </form>
        </div>
      </div>
    </>
  )
}
