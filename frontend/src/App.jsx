import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api, getToken, setToken } from './api.js'
import Header from './components/Header.jsx'
import Footer from './components/Footer.jsx'
import Leaderboard from './pages/Leaderboard.jsx'
import Profile from './pages/Profile.jsx'
import Login from './pages/Login.jsx'
import Manage from './pages/Manage.jsx'
import Settings from './pages/Settings.jsx'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export default function App() {
  const [user, setUser] = useState(null)
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')

  useEffect(() => {
    if (getToken()) api('/api/auth/me').then((d) => setUser(d.user)).catch(() => setUser(null))
    const out = () => setUser(null)
    window.addEventListener('sepc-logout', out)
    return () => window.removeEventListener('sepc-logout', out)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('sepc-theme', theme)
  }, [theme])

  const auth = {
    user,
    login: (token, u) => { setToken(token); setUser(u) },
    logout: () => { setToken(null); setUser(null) },
  }
  const loggedIn = !!getToken()

  return (
    <AuthContext.Provider value={auth}>
      <div className="app">
        <Header theme={theme} onTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
        <main className="page">
          <Routes>
            <Route path="/" element={<Leaderboard />} />
            <Route path="/student/:id" element={<Profile />} />
            <Route path="/login" element={<Login />} />
            <Route path="/manage" element={loggedIn ? <Manage /> : <Navigate to="/login" />} />
            <Route path="/settings" element={loggedIn ? <Settings /> : <Navigate to="/login" />} />
            <Route path="*" element={<p className="empty-state">Page not found.</p>} />
          </Routes>
        </main>
        <Footer theme={theme} />
      </div>
    </AuthContext.Provider>
  )
}
