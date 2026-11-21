import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import StudentForm from '../components/StudentForm.jsx'
import { API_URL, PLATFORMS, api } from '../api.js'

export default function Manage() {
  const [students, setStudents] = useState([])
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(null) // null | 'new' | student
  const [preview, setPreview] = useState(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)

  const load = () => api('/api/students').then(setStudents).catch((e) => setErr(e.message))
  useEffect(() => { document.title = 'Manage Student · SEPC'; load() }, [])

  async function remove(s) {
    if (!window.confirm(`Delete ${s.name} (${s.student_id})? Its history is deleted too.`)) return
    await api(`/api/students/${s.id}`, { method: 'DELETE' }).catch((e) => setErr(e.message))
    load()
  }

  async function upload(f, dryRun) {
    const form = new FormData()
    form.append('file', f)
    form.append('dry_run', dryRun ? '1' : '0')
    setErr('')
    try {
      const d = await api('/api/students/import', { method: 'POST', form })
      if (dryRun) { setFile(f); setPreview(d) } else { setPreview(null); setMsg(`Imported ${d.saved} students`); load() }
    } catch (e) {
      setErr(e.message)
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  const shown = students.filter((s) => `${s.name} ${s.student_id} ${s.batch}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <>
      <div className="toolbar">
        <b style={{ fontSize: 14 }}>Manage Student</b>
        <span className="muted">{students.length} total</span>
        <input className="input" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 170 }} />
        <span className="grow" />
        <a className="btn" href={`${API_URL}/api/students/template`}>Excel template</a>
        <button className="btn" onClick={() => fileRef.current?.click()}>Bulk import (.xlsx)</button>
        <input ref={fileRef} type="file" accept=".xlsx" hidden onChange={(e) => e.target.files[0] && upload(e.target.files[0], true)} />
        <button className="btn primary" onClick={() => setEditing('new')}>+ Add Student</button>
      </div>
      {msg && <div className="ok-msg">{msg}</div>}
      {err && <div className="err">{err}</div>}

      <div className="table-wrap">
        <table className="plain">
          <thead>
            <tr>
              <th>ID</th><th>Name</th><th>Batch</th><th>Role</th>
              {PLATFORMS.map((p) => <th key={p.key}>{p.label}</th>)}
              <th />
            </tr>
          </thead>
          <tbody>
            {shown.map((s) => (
              <tr key={s.id}>
                <td className="mono">{s.student_id}</td>
                <td><Link to={`/student/${s.id}`}>{s.name}</Link> {s.is_demo ? <span className="tag">test</span> : null}</td>
                <td>{s.batch}</td>
                <td><span className={`tag${s.role === 'developer' ? ' dev' : ''}`}>{s.role}</span></td>
                {PLATFORMS.map((p) => <td key={p.key} className="mono small">{s[p.key] || <span className="muted">·</span>}</td>)}
                <td><div className="row-actions">
                  <button className="btn" onClick={() => setEditing(s)}>Edit</button>
                  <button className="btn danger" onClick={() => remove(s)}>Delete</button>
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 && <div className="empty-state">No students.</div>}
      </div>

      {editing && (
        <StudentForm student={editing === 'new' ? null : editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); setMsg('Saved'); load() }} />
      )}

      {preview && (
        <div className="modal-bg">
          <div className="modal">
            <h3>Import preview: {preview.valid} of {preview.rows.length} rows are valid</h3>
            <div className="table-wrap" style={{ maxHeight: 340, overflow: 'auto' }}>
              <table className="plain">
                <thead><tr><th>Row</th><th>Action</th><th>ID</th><th>Name</th><th>Problems</th></tr></thead>
                <tbody>
                  {preview.rows.map((r) => (
                    <tr key={r.row}>
                      <td>{r.row}</td><td>{r.action}</td><td className="mono">{r.student_id}</td><td>{r.name}</td>
                      <td className={r.errors.length ? 'down' : 'up'}>{r.errors.join('; ') || 'ok'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="row-actions" style={{ marginTop: 8 }}>
              <button className="btn" onClick={() => setPreview(null)}>Cancel</button>
              <button className="btn primary" disabled={!preview.valid} onClick={() => upload(file, false)}>
                Import {preview.valid} rows
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
