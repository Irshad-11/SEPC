import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import SepcLogo from './SepcLogo.jsx'
import deptLight from '../assets/dept-logo-olive.png'
import deptDark from '../assets/dept-logo-white.png'

// role, name, student id, batch, linkedin (hardcoded for now), contributions
// Supervisor has no id/batch, so those are optional; `designation` is shown instead.
const TEAM = [
  {
    role: 'Project Supervisor',
    name: 'Md. Mahmodul Hasan',
    designation: 'Lecturer, Department of Software Engineering',
    linkedin: 'https://www.linkedin.com/in/your-profile',
    work: [
      'Supervisor of this project, providing academic guidance and direction.',
      'Reviewed the project scope and supported key decisions throughout development.',
    ],
  },
  {
    role: 'Project Lead & DevOps',
    name: 'Irshad Hossain',
    id: '2303030',
    batch: '2023-24',
    linkedin: 'https://www.linkedin.com/in/your-profile',
    work: [
      'Led the project and coordinated the overall development effort.',
      'Designed the whole site, including its structure, visual identity and user experience.',
      'Handled deployment and ongoing maintenance of the platform.',
    ],
  },
  {
    role: 'Backend Developer',
    name: 'Mahbub Tanmay',
    id: '2403016',
    batch: '2024-25',
    linkedin: 'https://www.linkedin.com/in/your-profile',
    work: [
      'Designed the REST API that powers the platform.',
      'Built and managed the backend logic and request handling.',
    ],
  },
  {
    role: 'Frontend Developer',
    name: 'Mahbubur Rahman Sifat',
    id: '2303028',
    batch: '2023-24',
    linkedin: 'https://www.linkedin.com/in/your-profile',
    work: [
      'Implemented the frontend interface from the approved designs.',
      'Built the pages and components, and connected them to the API.',
    ],
  },
  {
    role: 'UI/UX & Documentation',
    name: 'Ramjan Ali',
    id: '2403019',
    batch: '2024-25',
    linkedin: 'https://www.linkedin.com/in/your-profile',
    work: [
      'Supervised the UI/UX of the platform to keep it consistent and easy to use.',
      'Wrote and maintained the project documentation.',
    ],
  },
]

const VISIBLE = 3

function LinkedInIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.03-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.94v5.67H9.34V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 0 0 1 0 4.12zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z" />
    </svg>
  )
}

function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 11v6" />
      <circle cx="12" cy="7.5" r="0.6" fill="currentColor" />
    </svg>
  )
}

function Member({ m, open, onToggle }) {
  return (
    <div className="member">
      <div className="member-row">
        <span className="muted">{m.role}:</span>
        <b>{m.name}</b>
        {m.batch && <span className="muted small">({m.batch})</span>}
        <a className="icon-btn" href={m.linkedin} target="_blank" rel="noreferrer" aria-label={`${m.name} on LinkedIn`} title="LinkedIn">
          <LinkedInIcon />
        </a>
        <button type="button" className={`icon-btn${open ? ' on' : ''}`} onClick={onToggle}
          aria-expanded={open} aria-label={`About ${m.name}`} title="Details">
          <InfoIcon />
        </button>
      </div>
      {open && (
        <div className="member-pop" role="dialog" aria-label={`${m.name} details`}>
          <div className="pop-name">{m.name}</div>
          <div className="pop-line"><span className="muted">Role</span><span>{m.role}</span></div>
          {m.designation && (
            <div className="pop-line"><span className="muted">Position</span><span>{m.designation}</span></div>
          )}
          {m.id && <div className="pop-line"><span className="muted">Student ID</span><span className="mono">{m.id}</span></div>}
          {m.batch && <div className="pop-line"><span className="muted">Batch</span><span>{m.batch}</span></div>}
          <div className="pop-head">Contribution</div>
          <ul className="pop-work">
            {m.work.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function Footer({ theme }) {
  const dark = theme === 'dark'
  const [showAll, setShowAll] = useState(false)
  const [openId, setOpenId] = useState(null)
  const teamRef = useRef(null)

  // close the overlay on outside click or Escape
  useEffect(() => {
    if (!openId) return
    const onDown = (e) => { if (teamRef.current && !teamRef.current.contains(e.target)) setOpenId(null) }
    const onKey = (e) => { if (e.key === 'Escape') setOpenId(null) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [openId])

  const list = showAll ? TEAM : TEAM.slice(0, VISIBLE)
  const hidden = TEAM.length - VISIBLE

  return (
    <footer className="footer">
      <div className="footer-in">
        <div className="f-brand">
          <div className="f-brand-top">
            <SepcLogo size={44} />
            <b>SEPC</b>
          </div>
          <div className="f-brand-sub">Software Engineering Programming Community</div>
          <img className="f-dept" src={dark ? deptDark : deptLight} alt="Department of Software Engineering, UFTB" />
        </div>

        <div className="f-links">
          <h4>Links</h4>
          <Link to="/">Leaderboard</Link>
          <Link to="/manage">Manage Student</Link>
          <Link to="/settings">Settings</Link>
          <Link to="/login">Login</Link>
        </div>

        <div className="team" ref={teamRef}>
          <h4>Developers</h4>
          {list.map((m) => (
            <Member key={m.name} m={m} open={openId === m.name}
              onToggle={() => setOpenId(openId === m.name ? null : m.name)} />
          ))}
          <button type="button" className="more-btn"
            onClick={() => { setShowAll(!showAll); setOpenId(null) }}>
            {showAll ? 'Show less' : `+${hidden} more`}
          </button>
        </div>
      </div>
      <div className="copy">
        <span>SEPC@2026</span>
        <span>Department of Software Engineering, UFTB</span>
      </div>
    </footer>
  )
}