import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../App.jsx'
import SepcLogo from './SepcLogo.jsx'
import deptLogo from '../assets/dept-logo-white.png'

export default function Header({ theme, onTheme }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  return (
    <header className="header">
      <div className="header-in">
        <Link to="/" className="brand">
          <SepcLogo />
          <b>SEPC</b>
          <span>Software Engineering Programming Community</span>
        </Link>
        <div className="dept">
          <img src={deptLogo} alt="Department of Software Engineering" />
          <span>Department of Software Engineering, UFTB</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>Leaderboard</NavLink>
          {user && <NavLink to="/manage">Manage Student</NavLink>}
          {user && <NavLink to="/settings">Settings</NavLink>}
          <button onClick={onTheme} title="Switch theme">{theme === 'dark' ? '☀ Light' : '☾ Dark'}</button>
          {user ? (
            <button className="login-btn" onClick={() => { logout(); navigate('/') }}>Logout</button>
          ) : (
            <NavLink to="/login" className="login-btn">Login</NavLink>
          )}
        </nav>
      </div>
    </header>
  )
}
