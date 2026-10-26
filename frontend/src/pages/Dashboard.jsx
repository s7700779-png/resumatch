import React from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar as RBar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api, fmtDate } from '../api.js'
import { Head, Skeleton, ErrorBox, Empty, Badge, useLoad } from '../ui.jsx'

export default function Dashboard() {
  const { data: d, error, loading, reload } = useLoad(() => api.get('/dashboard'))
  if (loading) return <Skeleton rows={6} />
  if (error) return <ErrorBox msg={error} retry={reload} />
  const t = d.totals
  return (
    <>
      <Head title="Dashboard" sub="Everything here is computed from your stored analyses.">
        <Link className="btn" to="/analyze">Analyze resumes</Link><Link className="btn ghost" to="/jobs">Job descriptions</Link>
      </Head>
      {t.total === 0 ? (
        <div className="card"><Empty title="No analyses yet" text="Upload resumes and choose a job description to see statistics here."><Link className="btn" to="/analyze">Start an analysis</Link></Empty></div>
      ) : (
        <>
          <div className="grid g4">
            {[['Resumes analyzed', t.total], ['Completed', t.completed], ['Failed', t.failed], ['Average estimated match', t.average_score == null ? '—' : t.average_score]].map(([l, v]) =>
              <div className="card stat" key={l}><b>{v}</b><span>{l}</span></div>)}
          </div>
          <div className="grid g2">
            <div className="card"><h2>Estimated score distribution</h2>
              <ResponsiveContainer width="100%" height={200}><BarChart data={d.score_distribution}><XAxis dataKey="range" fontSize={12} /><YAxis allowDecimals={false} fontSize={12} width={30} /><Tooltip /><RBar dataKey="count" fill="#8a7563" /></BarChart></ResponsiveContainer></div>
            <div className="card"><h2>Analyses per day</h2>
              {d.activity.length ? <ResponsiveContainer width="100%" height={200}><BarChart data={d.activity}><XAxis dataKey="day" fontSize={11} /><YAxis allowDecimals={false} fontSize={12} width={30} /><Tooltip /><RBar dataKey="count" fill="#222" /></BarChart></ResponsiveContainer> : <p className="muted">No completed analyses yet.</p>}</div>
          </div>
          <div className="grid g2">
            <div className="card"><h2>Recent batches</h2>
              {d.recent_batches.map((b) => <p key={b.id}><Link to={`/batches/${b.id}`}>{b.job_title}</Link> <Badge s={b.status} /> <span className="muted small">{b.total} files · {fmtDate(b.created_at)}</span></p>)}</div>
            <div className="card"><h2>Recent candidate results</h2>
              {d.recent_candidates.length ? d.recent_candidates.map((c) => <p key={c.id}><Link to={`/candidates/${c.id}`}>{c.filename}</Link> <span className="badge">{c.score}</span></p>) : <p className="muted">None yet.</p>}</div>
            <div className="card"><h2>Frequently used job descriptions</h2>
              {d.frequent_jobs.map((j) => <p key={j.id}>{j.title} <span className="muted small">{j.batches} batch(es)</span></p>)}</div>
            <div className="card"><h2>Recent reports</h2>
              {d.recent_reports.length ? d.recent_reports.map((r) => <p key={r.id}><Link to={`/reports/${r.id}`}>{r.title}</Link></p>) : <p className="muted">No reports generated yet.</p>}</div>
          </div>
        </>
      )}
    </>
  )
}
