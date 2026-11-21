import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App.jsx'
import { api } from '../api.js'
import SepcLogo from '../components/SepcLogo.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setErr('')
    try {
      const d = await api('/api/auth/login', { method: 'POST', body: { username, password } })
      login(d.token, d.user)
      navigate('/manage')
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="login-box" onSubmit={submit}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <SepcLogo size={24} />
        <div>
          <h2>Login</h2>
          <div className="meta-line">For SEPC developers and admins</div>
        </div>
      </div>
      <label className="field">Username
        <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
      </label>
      <label className="field">Password
        <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
      </label>
      {err && <div className="err">{err}</div>}
      <button className="btn primary" style={{ width: '100%', justifyContent: 'center', marginTop: 4 }} disabled={busy}>
        {busy ? 'Signing in…' : 'Login'}
      </button>
    </form>
  )
}
