import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtDate } from '../api.js'
import { Head, Skeleton, ErrorBox, Empty, Badge, Pager, useLoad, useDebounced } from '../ui.jsx'

export default function History() {
  const [q, setQ] = useState(''), dq = useDebounced(q), [status, setStatus] = useState(''), [page, setPage] = useState(1)
  const { data, error, loading, reload } = useLoad(() => api.get(`/history?q=${encodeURIComponent(dq)}&status=${status}&page=${page}&per_page=10`), [dq, status, page])
  return (
    <>
      <Head title="Analysis History" sub="Reopen any previous batch without uploading the files again."><Link className="btn" to="/analyze">New analysis</Link></Head>
      <div className="card">
        <div className="grid g2">
          <div><label htmlFor="hq">Search job title or batch ID</label><input id="hq" value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} /></div>
          <div><label htmlFor="hs">Status</label><select id="hs" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
            <option value="">All</option>{['completed', 'partially_completed', 'processing', 'failed'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}</select></div>
        </div>
        {loading ? <Skeleton rows={4} /> : error ? <ErrorBox msg={error} retry={reload} /> : !data.items.length ? <Empty title="No batches found" text="Run an analysis, or adjust the search and filter." /> : (
          <><div className="tw"><table><thead><tr><th>Batch</th><th>Job</th><th>Created</th><th>Files</th><th>Completed</th><th>Failed</th><th>Status</th></tr></thead><tbody>
            {data.items.map((b) => <tr key={b.id}><td><Link to={`/batches/${b.id}`}>{b.id}</Link></td><td>{b.job_title}</td><td className="small">{fmtDate(b.created_at)}</td><td>{b.total}</td><td>{b.counts.completed || 0}</td><td>{b.counts.failed || 0}</td><td><Badge s={b.status} /></td></tr>)}</tbody></table></div>
            <Pager page={data.page} total={data.total} per={data.per_page} onPage={setPage} /></>)}
      </div>
    </>
  )
}
