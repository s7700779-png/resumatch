import React, { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmtDate } from '../api.js'
import { Head, Skeleton, ErrorBox, Badge, Bar, Confirm, useLoad, useToast } from '../ui.jsx'

export default function Batch() {
  const { batchId } = useParams(), nav = useNavigate(), toast = useToast()
  const [del, setDel] = useState(false)
  const { data, error, loading, reload } = useLoad(() => api.get(`/batches/${batchId}`), [batchId], (d) => !d || ['pending', 'processing'].includes(d.batch.status))
  if (loading) return <Skeleton rows={6} />
  if (error) return <ErrorBox msg={error} retry={reload} />
  const { batch: b, candidates: cs } = data
  const failedRetry = cs.filter((c) => c.status === 'failed' && c.retryable).length
  const retry = async () => { try { const r = await api.post(`/batches/${batchId}/retry`); toast(`Retrying ${r.retried} file(s)`); reload() } catch (e) { toast(e.message, 'error') } }
  const remove = async () => { try { await api.del(`/batches/${batchId}`); toast('Batch deleted'); nav('/history') } catch (e) { toast(e.message, 'error') } }
  const active = ['pending', 'processing'].includes(b.status)
  return (
    <>
      <Head title={`Batch: ${b.job.title}`} sub={`Created ${fmtDate(b.created_at)} · ${b.total} file(s)`}>
        {failedRetry > 0 && <button className="btn" onClick={retry}>Retry {failedRetry} failed</button>}
        <a className="btn ghost" href={`/api/batches/${batchId}/export.csv`}>Export CSV</a>
        <button className="btn danger" onClick={() => setDel(true)}>Delete batch</button>
      </Head>
      <div className="card">
        <div className="row"><Badge s={b.status} /><span className="small muted">{Object.entries(b.counts).map(([k, v]) => `${v} ${k}`).join(' · ')}</span></div>
        <p className="small muted" style={{ margin: '8px 0 4px' }}>{active ? 'Processing — progress reflects files the server has finished.' : 'Finished.'} {b.progress}%</p>
        <Bar v={b.progress / 100} />
      </div>
      <div className="card tw">
        <table><thead><tr><th>File</th><th>Status</th><th>Estimated match</th><th>Parsing quality</th><th>Notes</th></tr></thead>
          <tbody>{cs.map((c) => (
            <tr key={c.id}>
              <td>{c.status === 'completed' ? <Link to={`/candidates/${c.id}`}>{c.filename}</Link> : c.filename}<div className="muted small">{c.name !== 'Not detected' ? c.name : ''}</div></td>
              <td><Badge s={c.status} /></td><td>{c.score ?? '—'}</td><td className="small">{c.parsing || '—'}</td>
              <td className="small">{c.error && <span style={{ color: 'var(--bad)' }}>{c.error}</span>}
                {c.duplicate_of && <div>Identical to an earlier file.</div>}
                {c.likely_duplicates?.length > 0 && <div>Likely duplicate of {c.likely_duplicates[0].filename} ({Math.round(c.likely_duplicates[0].similarity * 100)}% similar text).</div>}</td>
            </tr>))}</tbody></table>
      </div>
      {b.counts.completed > 1 && <Link className="btn ghost" to="/compare">Compare candidates</Link>}
      {del && <Confirm title="Delete this batch?" text="All analyses, uploaded files and reports in it will be permanently removed." onYes={remove} onNo={() => setDel(false)} />}
    </>
  )
}
