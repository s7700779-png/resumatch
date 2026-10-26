import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Head, Skeleton, ErrorBox, Confirm, useLoad, useToast } from '../ui.jsx'

export default function Settings() {
  const toast = useToast()
  const { data, error, loading, reload } = useLoad(() => api.get('/settings'))
  const [f, setF] = useState(null), [purge, setPurge] = useState(false), [withJobs, setWithJobs] = useState(false)
  useEffect(() => { if (data) setF(data.settings) }, [data])
  if (loading || !f) return error ? <ErrorBox msg={error} retry={reload} /> : <Skeleton rows={6} />
  const L = data.limits
  async function save(e) {
    e.preventDefault()
    try { await api.put('/settings', f); toast('Settings saved'); reload() } catch (x) { toast(x.message, 'error') }
  }
  async function doPurge() {
    try { await api.post('/settings/purge', { confirm: true, include_jobs: withJobs }); toast('All resume data deleted'); setPurge(false) } catch (x) { toast(x.message, 'error') }
  }
  const num = (k, label) => <><label htmlFor={k}>{label} ({L[k][0]}–{L[k][1]})</label><input id={k} type="number" min={L[k][0]} max={L[k][1]} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></>
  return (
    <>
      <Head title="Settings" />
      <form className="card" onSubmit={save}>
        <h2>Upload limits &amp; retention</h2>
        {num('max_files', 'Maximum files per batch')}{num('max_size_mb', 'Maximum file size (MB)')}{num('retention_days', 'Auto-delete analyses older than N days (0 = keep)')}
        <label>Supported formats</label><p>{data.supported_formats.map((x) => x.toUpperCase()).join(', ')} <span className="muted small">(fixed)</span></p>
        <p><button className="btn">Save settings</button></p>
      </form>
      <div className="card"><h2>Analysis &amp; AI</h2>
        <p>Method: {data.analysis_method}</p>
        <p className="small">Score weights: {Object.entries(data.weights).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(', ')} <span className="muted">(set in backend/app/matching.py)</span></p>
        <p>AI provider (Gemini): <strong>{data.ai.configured ? 'configured' : 'not configured'}</strong> <span className="muted small">— {data.ai.message}. The key is read from the server environment and never sent to the browser.</span></p>
        <p>OCR for scanned PDFs: <strong>{data.ocr_available ? 'available' : 'unavailable'}</strong> <span className="muted small">{!data.ocr_available && '— install Tesseract and pytesseract to enable it.'}</span></p></div>
      <div className="card"><h2>Privacy &amp; deletion</h2>
        <p className="small muted">This build has no user accounts and is meant for a trusted local setup. Delete resume data when you are done.</p>
        <label className="chk"><input type="checkbox" checked={withJobs} onChange={(e) => setWithJobs(e.target.checked)} /> Also delete saved job descriptions</label>
        <p><button className="btn danger" onClick={() => setPurge(true)}>Delete all resume data</button></p></div>
      {purge && <Confirm title="Delete all resume data?" text="All batches, uploaded files, analyses and reports will be permanently removed." onYes={doPurge} onNo={() => setPurge(false)} yes="Delete everything" />}
    </>
  )
}
