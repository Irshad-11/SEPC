import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import SepcLogo from './SepcLogo.jsx'
import deptLight from '../assets/dept-logo-olive.png'
import deptDark from '../assets/dept-logo-white.png'

// External links (hardcoded for now)
const UNIVERSITY_URL = 'https://uftb.ac.bd/'
const DEPARTMENT_URL = 'https://se.uftb.ac.bd/'

// Replace the placeholder LinkedIn URLs with the real ones when you have them.
// Supervisor has no student id / batch, so those fields are optional;
// `designation` is shown for him instead.
const TEAM = [
  {
    role: 'Project Supervisor',
    name: 'Md. Mahmodul Hasan',
    designation: 'Lecturer, Department of Software Engineering',
    linkedin: 'https://www.linkedin.com/in/md-mahmodul-hasan-09173b305/',
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
    linkedin: 'https://www.linkedin.com/in/irshad-hossain',
    work: [
      'Led the project and coordinated the overall development effort.',
      'Designed the whole site, including its structure, visual identity and user experience.',
      'Handled deployment and ongoing maintenance of the platform.',
    ],
  },
  {
    role: 'Backend Developer',
    name: 'Md Mahbub Tanmay',
    id: '2403016',
    batch: '2024-25',
    linkedin: 'https://www.linkedin.com/in/mdmahbubtanmay/',
    work: [
      'Designed the REST API that powers the platform.',
      'Built and managed the backend logic and request handling.',
    ],
  },
  {
    role: 'Frontend Developer',
    name: 'Md Mahbubul Alom Sifat',
    id: '2303028',
    batch: '2023-24',
    linkedin: 'https://www.linkedin.com/in/mahbubsifat/',
    work: [
      'Implemented the frontend interface from the approved designs.',
      'Built the pages and components, and connected them to the API.',
    ],
  },
  {
    role: 'UI/UX & Documentation',
    name: 'Md Ramjan Ali',
    id: '2403019',
    batch: '2024-25',
    linkedin: 'https://www.linkedin.com/in/md--ramzan--ali/',
    work: [
      'UI/UX expert of the project, shaping a consistent and easy-to-use interface.',
      'Documentation writing.',
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
        <span className="muted role">{m.role}:</span>
        <b>{m.name}</b>
        {m.batch && <span className="muted small">({m.batch})</span>}
        <a className="icon-btn" href={m.linkedin} target="_blank" rel="noreferrer"
          aria-label={`${m.name} on LinkedIn`} title="LinkedIn">
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
          {m.id && (
            <div className="pop-line"><span className="muted">Student ID</span><span className="mono">{m.id}</span></div>
          )}
          {m.batch && (
            <div className="pop-line"><span className="muted">Batch</span><span>{m.batch}</span></div>
          )}
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
  // true once the expand animation has finished (lets the overlay of the extra
  // members escape the clipped, animating box)
  const [settled, setSettled] = useState(false)
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

  // after the expand animation (~0.4s) mark it as settled
  useEffect(() => {
    if (!showAll) return
    const t = setTimeout(() => setSettled(true), 420)
    return () => clearTimeout(t)
  }, [showAll])

  const toggleMore = () => {
    if (showAll) setSettled(false)
    setShowAll(!showAll)
    setOpenId(null)
  }

  const first = TEAM.slice(0, VISIBLE)
  const extra = TEAM.slice(VISIBLE)
  const renderMember = (m) => (
    <Member key={m.name} m={m} open={openId === m.name}
      onToggle={() => setOpenId(openId === m.name ? null : m.name)} />
  )

  return (
    <footer className="footer">
      <div className="footer-in">
        <div className="f-brand-group">
          <div className="f-brand-row">
            <div className="f-mark">
              <SepcLogo size={40} />
              <b>SEPC</b>
            </div>
            <div className="f-dept-wrap">
              <img className="f-dept" src={dark ? deptDark : deptLight} alt="Department of Software Engineering, UFTB" />
            </div>
          </div>
          <div className="f-brand-sub">Software Engineering Programming Community</div>
        </div>

        <div className="f-links">
          <h4>Links</h4>
          <div className="f-links-grid">
            <Link to="/">Leaderboard</Link>
            <Link to="/manage">Manage Student</Link>
            <Link to="/settings">Settings</Link>
            <Link to="/login">Login</Link>
            <a className="ext" href={UNIVERSITY_URL} target="_blank" rel="noreferrer">University Site</a>
            <a className="ext" href={DEPARTMENT_URL} target="_blank" rel="noreferrer">Department Site</a>
          </div>
        </div>

        <div className="team" ref={teamRef}>
          <h4>Behind This Project</h4>
          <div className="team-tag">The people who made it real</div>

          {first.map(renderMember)}

          {/* extra members: height animates open/closed smoothly */}
          <div className={`team-extra${showAll ? ' open' : ''}${settled ? ' settled' : ''}`} inert={!showAll}>
            <div className="team-extra-inner">
              {extra.map(renderMember)}
            </div>
          </div>

          <button type="button" className="more-btn" onClick={toggleMore} aria-expanded={showAll}>
            {showAll ? 'Show less' : `+${extra.length} more`}
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