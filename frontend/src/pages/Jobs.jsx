import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate } from '../api.js'
import { Head, Skeleton, ErrorBox, Empty, Badge, Confirm, useLoad, useToast, useDebounced } from '../ui.jsx'

const blank = { title: '', department: '', description: '', required_skills: '', preferred_skills: '' }

export default function Jobs() {
  const toast = useToast()
  const [q, setQ] = useState(''), dq = useDebounced(q)
  const { data, error, loading, reload } = useLoad(() => api.get(`/jobs?q=${encodeURIComponent(dq)}`), [dq])
  const [form, setForm] = useState(null), [err, setErr] = useState(''), [del, setDel] = useState(null), [view, setView] = useState(null)
  const edit = (j) => { setErr(''); setForm(j ? { ...j, required_skills: j.required_skills.join(', '), preferred_skills: j.preferred_skills.join(', ') } : { ...blank }) }
  async function save(e) {
    e.preventDefault(); setErr('')
    try { form.id ? await api.put(`/jobs/${form.id}`, form) : await api.post('/jobs', form); toast('Job description saved'); setForm(null); reload() }
    catch (x) { setErr(x.message) }
  }
  async function remove(withBatches) {
    try { await api.del(`/jobs/${del.id}${withBatches ? '?with_batches=true' : ''}`); toast('Deleted'); setDel(null); reload() }
    catch (x) { setDel({ ...del, conflict: x.message }) }
  }
  async function open(j) { try { setView(await api.get(`/jobs/${j.id}`)) } catch (x) { toast(x.message, 'error') } }
  return (
    <>
      <Head title="Job Descriptions" sub="Saved descriptions can be reused for any analysis."><button className="btn" onClick={() => edit(null)}>New job description</button></Head>
      {form && (
        <form className="card" onSubmit={save}>
          <h2>{form.id ? 'Edit' : 'New'} job description</h2>{err && <ErrorBox msg={err} />}
          <label htmlFor="jt">Title *</label><input id="jt" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <label htmlFor="jd">Department</label><input id="jd" value={form.department || ''} onChange={(e) => setForm({ ...form, department: e.target.value })} />
          <label htmlFor="jx">Description *</label><textarea id="jx" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <label htmlFor="jr">Required skills (comma-separated, optional)</label><input id="jr" value={form.required_skills} onChange={(e) => setForm({ ...form, required_skills: e.target.value })} />
          <label htmlFor="jp">Preferred skills (optional)</label><input id="jp" value={form.preferred_skills} onChange={(e) => setForm({ ...form, preferred_skills: e.target.value })} />
          <p className="row" style={{ marginTop: 12 }}><button className="btn">Save</button><button type="button" className="btn ghost" onClick={() => setForm(null)}>Cancel</button></p>
        </form>)}
      <div className="card">
        <label htmlFor="q">Search</label><input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Title, department or text" />
        {loading ? <Skeleton rows={3} /> : error ? <ErrorBox msg={error} retry={reload} /> : !data.jobs.length ? <Empty title="No job descriptions" text={dq ? 'Nothing matches your search.' : 'Create one to get started.'} /> : (
          <div className="tw"><table><thead><tr><th>Title</th><th>Department</th><th>Batches</th><th>Updated</th><th /></tr></thead><tbody>
            {data.jobs.map((j) => <tr key={j.id}><td><button className="btn ghost sm" onClick={() => open(j)}>{j.title}</button></td><td>{j.department || '—'}</td><td>{j.batch_count}</td><td className="small">{fmtDate(j.updated_at)}</td>
              <td className="row"><button className="btn ghost sm" onClick={() => edit(j)}>Edit</button><button className="btn danger sm" onClick={() => setDel(j)}>Delete</button></td></tr>)}</tbody></table></div>)}
      </div>
      {view && <div className="card"><h2>{view.job.title}</h2><pre className="resume">{view.job.description}</pre><h3 style={{ marginTop: 10 }}>Analysis batches</h3>
        {view.batches.length ? view.batches.map((b) => <p key={b.id}><Link to={`/batches/${b.id}`}>{b.id}</Link> <Badge s={b.status} /> <span className="muted small">{b.total} files</span></p>) : <p className="muted small">No batches yet.</p>}
        <button className="btn ghost sm" onClick={() => setView(null)}>Close</button></div>}
      {del && <Confirm title={`Delete “${del.title}”?`} text={del.conflict ? `${del.conflict} Delete the job together with its batches?` : 'This cannot be undone.'} yes={del.conflict ? 'Delete job and batches' : 'Delete'} onYes={() => remove(!!del.conflict)} onNo={() => setDel(null)} />}
    </>
  )
}
