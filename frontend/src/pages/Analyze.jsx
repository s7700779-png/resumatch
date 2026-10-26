import React, { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Head, ErrorBox, useLoad, useToast } from '../ui.jsx'

const kb = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.ceil(n / 1024) + ' KB')

export default function Analyze() {
  const nav = useNavigate(), toast = useToast(), pick = useRef()
  const { data: s } = useLoad(() => api.get('/settings'))
  const { data: jobs } = useLoad(() => api.get('/jobs'))
  const [files, setFiles] = useState([])
  const [over, setOver] = useState(false)
  const [mode, setMode] = useState('new')
  const [jobId, setJobId] = useState('')
  const [f, setF] = useState({ title: '', department: '', description: '', required_skills: '', preferred_skills: '' })
  const [skipDup, setSkipDup] = useState(false)
  const [errs, setErrs] = useState([])
  const [busy, setBusy] = useState(false)
  const lim = s?.settings || { max_files: 20, max_size_mb: 10 }

  function add(list) {
    const msgs = [], next = [...files]
    for (const file of list) {
      const ext = file.name.split('.').pop().toLowerCase()
      if (!['pdf', 'docx'].includes(ext)) { msgs.push(`${file.name}: only PDF and DOCX are supported.`); continue }
      if (file.size === 0) { msgs.push(`${file.name}: file is empty.`); continue }
      if (file.size > lim.max_size_mb * 1048576) { msgs.push(`${file.name}: larger than ${lim.max_size_mb} MB.`); continue }
      if (next.some((x) => x.name === file.name && x.size === file.size)) { msgs.push(`${file.name}: already in the list (duplicate).`); continue }
      if (next.length >= lim.max_files) { msgs.push(`Limit of ${lim.max_files} files per batch reached.`); break }
      next.push(file)
    }
    setFiles(next); setErrs(msgs)
  }

  async function submit(e) {
    e.preventDefault()
    const m = []
    if (!files.length) m.push('Add at least one resume.')
    if (mode === 'saved' && !jobId) m.push('Select a saved job description.')
    if (mode === 'new' && !f.title.trim()) m.push('Job title is required.')
    if (mode === 'new' && !f.description.trim()) m.push('Job description cannot be empty.')
    if (m.length) return setErrs(m)
    const fd = new FormData()
    files.forEach((x) => fd.append('files', x))
    if (mode === 'saved') fd.append('job_id', jobId); else Object.entries(f).forEach(([k, v]) => fd.append(k, v))
    fd.append('skip_duplicates', skipDup)
    setBusy(true); setErrs([])
    try { const r = await api.form('/batches', fd); toast('Batch submitted'); nav(`/batches/${r.batch_id}`) }
    catch (er) { setErrs([er.message]); setBusy(false) }
  }

  return (
    <form onSubmit={submit}>
      <Head title="Analyze Resumes" sub="Upload PDF or DOCX resumes and compare them with a job description."><button className="btn" disabled={busy}>{busy ? 'Submitting…' : 'Analyze'}</button></Head>
      {errs.length > 0 && <div className="err" role="alert">{errs.map((x) => <div key={x}>{x}</div>)}</div>}
      <div className="grid g2">
        <div className="card">
          <h2>1. Resumes</h2>
          <div className={'drop' + (over ? ' over' : '')} role="button" tabIndex={0} onClick={() => pick.current.click()} onKeyDown={(e) => e.key === 'Enter' && pick.current.click()}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); add([...e.dataTransfer.files]) }}>
            <strong>Drop files here or click to browse</strong><div className="muted small">PDF or DOCX · up to {lim.max_files} files · {lim.max_size_mb} MB each</div>
          </div>
          <input ref={pick} type="file" hidden multiple accept=".pdf,.docx" onChange={(e) => { add([...e.target.files]); e.target.value = '' }} />
          {files.length > 0 && <div className="tw"><table><tbody>{files.map((x, i) => (
            <tr key={i}><td>{x.name}</td><td className="muted small">{x.name.split('.').pop().toUpperCase()} · {kb(x.size)}</td>
              <td><button type="button" className="btn ghost sm" onClick={() => setFiles(files.filter((_, j) => j !== i))} aria-label={`Remove ${x.name}`}>Remove</button></td></tr>))}</tbody></table></div>}
          <label className="chk"><input type="checkbox" checked={skipDup} onChange={(e) => setSkipDup(e.target.checked)} /> Skip files identical to ones already analysed for this job</label>
        </div>
        <div className="card">
          <h2>2. Job description</h2>
          <div className="row"><label className="chk"><input type="radio" checked={mode === 'new'} onChange={() => setMode('new')} /> New</label>
            <label className="chk"><input type="radio" checked={mode === 'saved'} onChange={() => setMode('saved')} /> Saved</label></div>
          {mode === 'saved' ? (
            <><label htmlFor="jb">Saved job description</label>
              <select id="jb" value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">Select…</option>{jobs?.jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</select>
              {jobs && !jobs.jobs.length && <p className="muted small">No saved descriptions yet. Choose “New”.</p>}</>
          ) : (
            <>
              <label htmlFor="t">Job title *</label><input id="t" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
              <label htmlFor="d">Department (optional)</label><input id="d" value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} />
              <label htmlFor="ds">Job description *</label><textarea id="ds" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} placeholder="Paste the description. Put preferred items after a line starting with “Preferred”." />
              <label htmlFor="rs">Required skills (optional, comma-separated)</label><input id="rs" value={f.required_skills} onChange={(e) => setF({ ...f, required_skills: e.target.value })} />
              <label htmlFor="ps">Preferred skills (optional)</label><input id="ps" value={f.preferred_skills} onChange={(e) => setF({ ...f, preferred_skills: e.target.value })} />
              <p className="small muted">New descriptions are saved automatically. Leave skills blank to detect them from the text.</p>
            </>
          )}
        </div>
      </div>
      <div className="note">Scores are internal estimates of relevance to the job description. They are not official ATS scores or hiring decisions.</div>
    </form>
  )
}
