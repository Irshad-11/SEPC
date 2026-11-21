import { useState } from 'react'
import { api } from '../api.js'

const FIELDS = [
  ['student_id', 'Student ID *'], ['name', 'Name *'], ['batch', 'Batch (e.g. 2023-24)'], ['department', 'Department'],
  ['codeforces', 'Codeforces handle'], ['leetcode', 'LeetCode username'], ['codechef', 'CodeChef handle'], ['beecrowd', 'Beecrowd ID'],
  ['avatar_url', 'Photo URL'], ['github_url', 'GitHub URL'], ['linkedin_url', 'LinkedIn URL'], ['email', 'Email'],
]
const EMPTY = { department: 'Software Engineering', role: 'student' }

// Add / edit one student (modal)
export default function StudentForm({ student, onClose, onSaved }) {
  const [form, setForm] = useState(student ? { ...student } : { ...EMPTY })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setErr('')
    const body = {}
    for (const [k] of FIELDS) body[k] = form[k] ?? ''
    body.role = form.role
    try {
      if (student) await api(`/api/students/${student.id}`, { method: 'PUT', body })
      else await api('/api/students', { method: 'POST', body })
      onSaved()
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" onSubmit={save}>
        <h3>{student ? `Edit ${student.name}` : 'Add Student'}</h3>
        <div className="form-grid">
          {FIELDS.map(([k, label]) => (
            <label key={k} className="field">
              {label}
              <input className="input" value={form[k] ?? ''} onChange={set(k)} required={label.endsWith('*')} />
            </label>
          ))}
          <label className="field">
            Role
            <select className="input" value={form.role} onChange={set('role')}>
              <option value="student">Student</option>
              <option value="developer">Developer (shows badge)</option>
            </select>
          </label>
        </div>
        {err && <div className="err">{err}</div>}
        <div className="row-actions" style={{ marginTop: 6 }}>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </div>
  )
}
