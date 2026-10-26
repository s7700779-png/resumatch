import React, { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmtDate } from '../api.js'
import { Head, Skeleton, ErrorBox, Empty, Confirm, useLoad, useToast } from '../ui.jsx'

const KIND = { candidate_pdf: 'Candidate PDF', batch_csv: 'Batch CSV', compare_csv: 'Comparison CSV' }

export function Reports() {
  const toast = useToast(), [del, setDel] = useState(null)
  const { data, error, loading, reload } = useLoad(() => api.get('/reports'))
  const remove = async () => { try { await api.del(`/reports/${del.id}`); toast('Report deleted'); setDel(null); reload() } catch (e) { toast(e.message, 'error') } }
  return (
    <>
      <Head title="Reports" sub="Generated from stored analysis records. Create new ones from a candidate, batch or comparison." />
      <div className="card">{loading ? <Skeleton rows={3} /> : error ? <ErrorBox msg={error} retry={reload} /> : !data.reports.length ? <Empty title="No reports yet" text="Open a candidate and choose “Download report”, or export a batch." /> : (
        <div className="tw"><table><thead><tr><th>Report</th><th>Type</th><th>Created</th><th /></tr></thead><tbody>
          {data.reports.map((r) => <tr key={r.id}><td><Link to={`/reports/${r.id}`}>{r.title}</Link></td><td>{KIND[r.kind] || r.kind}</td><td className="small">{fmtDate(r.created_at)}</td>
            <td className="row"><a className="btn ghost sm" href={`/api/reports/${r.id}/download`}>Download</a><button className="btn danger sm" onClick={() => setDel(r)}>Delete</button></td></tr>)}</tbody></table></div>)}</div>
      {del && <Confirm title="Delete this report?" text={del.title} onYes={remove} onNo={() => setDel(null)} />}
    </>
  )
}

export function ReportDetail() {
  const { reportId } = useParams(), nav = useNavigate(), toast = useToast(), [del, setDel] = useState(false)
  const { data, error, loading, reload } = useLoad(() => api.get(`/reports/${reportId}`), [reportId])
  if (loading) return <Skeleton rows={4} />
  if (error) return <ErrorBox msg={error} retry={reload} />
  const r = data.report, c = data.candidate
  const remove = async () => { try { await api.del(`/reports/${reportId}`); toast('Report deleted'); nav('/reports') } catch (e) { toast(e.message, 'error') } }
  return (
    <>
      <Head title={r.title} sub={`${KIND[r.kind] || r.kind} · ${fmtDate(r.created_at)}`}>
        <a className="btn" href={`/api/reports/${reportId}/download`}>Download</a><button className="btn danger" onClick={() => setDel(true)}>Delete</button></Head>
      <div className="card">
        {c ? <><h2>Report preview</h2><p>File: <Link to={`/candidates/${c.id}`}>{c.filename}</Link></p><p>Estimated match: <strong>{c.score}</strong> · {c.parsing} · {c.evidence}</p>
          <p className="small">Matched: {c.matched.join(', ') || '—'}<br />Not clearly evidenced: {c.missing_required.join(', ') || '—'}</p></> : <p className="muted">This export is a data file; download it to view the contents.</p>}
        <p className="small muted">Scores are internal estimates, not official ATS results or hiring recommendations.</p>
      </div>
      {del && <Confirm title="Delete this report?" text="The generated file will be removed." onYes={remove} onNo={() => setDel(false)} />}
    </>
  )
}
