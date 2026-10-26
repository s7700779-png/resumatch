import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, downloadPost, pct } from '../api.js'
import { Head, Skeleton, ErrorBox, Empty, Bar, useLoad, useToast, useDebounced } from '../ui.jsx'

export default function Compare() {
  const toast = useToast()
  const [tab, setTab] = useState('compare')
  const [jobId, setJobId] = useState('')
  const [q, setQ] = useState(''), dq = useDebounced(q)
  const [sel, setSel] = useState(() => JSON.parse(localStorage.getItem('compare_ids') || '[]'))
  const [sort, setSort] = useState({ k: 'score', dir: -1 })
  const [minScore, setMinScore] = useState(0)
  const [result, setResult] = useState(null), [err, setErr] = useState('')
  const { data: jobs } = useLoad(() => api.get('/jobs'))
  const { data: cands, loading, error, reload } = useLoad(() => api.get(`/candidates?job_id=${jobId}&q=${encodeURIComponent(dq)}`), [jobId, dq])
  const { data: picked } = useLoad(() => (sel.length ? api.get(`/candidates?ids=${sel.join(',')}`) : Promise.resolve({ candidates: [] })), [sel.join(',')])
  useEffect(() => localStorage.setItem('compare_ids', JSON.stringify(sel)), [sel])
  useEffect(() => {
    setResult(null); setErr('')
    if (sel.length < 2) return
    api.post('/compare', { candidate_ids: sel }).then(setResult).catch((e) => setErr(e.message))
  }, [sel.join(',')]) // eslint-disable-line
  const toggle = (id) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  const rows = useMemo(() => {
    const l = (cands?.candidates || []).filter((c) => c.score >= minScore)
    return l.sort((a, b) => ((a[sort.k] ?? -1) > (b[sort.k] ?? -1) ? 1 : -1) * sort.dir)
  }, [cands, sort, minScore])
  const th = (k, label) => <th className="sort" onClick={() => setSort({ k, dir: sort.k === k ? -sort.dir : -1 })} aria-sort={sort.k === k ? (sort.dir < 0 ? 'descending' : 'ascending') : 'none'}>{label}{sort.k === k ? (sort.dir < 0 ? ' ↓' : ' ↑') : ''}</th>
  const exp = async () => { try { await downloadPost('/compare/export', { candidate_ids: sel }, 'comparison.csv'); toast('Comparison exported') } catch (e) { toast(e.message, 'error') } }
  return (
    <>
      <Head title="Compare Candidates" sub="Side-by-side evidence for human review — not a hiring decision.">
        <button className={'btn ' + (tab === 'compare' ? '' : 'ghost')} onClick={() => setTab('compare')}>Candidates</button>
        <button className={'btn ' + (tab === 'versions' ? '' : 'ghost')} onClick={() => setTab('versions')}>Resume versions</button>
      </Head>
      {tab === 'versions' ? <Versions cands={cands?.candidates || []} jobId={jobId} setJobId={setJobId} jobs={jobs?.jobs || []} /> : (
        <>
          <div className="card">
            <div className="grid g3">
              <div><label htmlFor="j">Job description</label><select id="j" value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">All</option>{jobs?.jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</select></div>
              <div><label htmlFor="s">Search file or name</label><input id="s" value={q} onChange={(e) => setQ(e.target.value)} /></div>
              <div><label htmlFor="m">Minimum score: {minScore}</label><input id="m" type="range" min="0" max="100" value={minScore} onChange={(e) => setMinScore(+e.target.value)} /></div>
            </div>
            {loading ? <Skeleton rows={3} /> : error ? <ErrorBox msg={error} retry={reload} /> : !rows.length ? <Empty title="No analysed candidates" text="Analyse resumes first, or relax the filters."><Link className="btn" to="/analyze">Analyze resumes</Link></Empty> : (
              <div className="tw"><table><thead><tr><th>Select</th>{th('filename', 'File')}{th('score', 'Score')}{th('required_coverage', 'Required')}{th('preferred_coverage', 'Preferred')}</tr></thead>
                <tbody>{rows.map((c) => <tr key={c.id}><td><input type="checkbox" aria-label={`Select ${c.filename}`} checked={sel.includes(c.id)} onChange={() => toggle(c.id)} /></td>
                  <td><Link to={`/candidates/${c.id}`}>{c.filename}</Link></td><td>{c.score}</td><td>{pct(c.required_coverage)}</td><td>{pct(c.preferred_coverage)}</td></tr>)}</tbody></table></div>)}
          </div>
          <div className="card">
            <div className="row" style={{ justifyContent: 'space-between' }}><h2>Side-by-side ({sel.length} selected)</h2>
              <div className="row">{sel.length > 0 && <button className="btn ghost sm" onClick={() => setSel([])}>Clear selection</button>}<button className="btn sm" disabled={sel.length < 2 || !result} onClick={exp}>Export CSV</button></div></div>
            {sel.length < 2 ? <p className="muted">Select at least two candidates (for the same job description).</p> : err ? <ErrorBox msg={err} /> : !result ? <Skeleton rows={4} /> : (
              <div className="tw"><table><thead><tr><th>Measure</th>{result.candidates.map((c) => <th key={c.id}>{c.filename} <button className="btn ghost sm" onClick={() => toggle(c.id)} aria-label={`Remove ${c.filename}`}>×</button></th>)}</tr></thead>
                <tbody>
                  <tr><td>Estimated match score</td>{result.candidates.map((c) => <td key={c.id}><strong>{c.score}</strong></td>)}</tr>
                  {[['required', 'Required skill coverage'], ['preferred', 'Preferred skill coverage'], ['experience', 'Relevant experience evidence'], ['project_edu', 'Project / education evidence'], ['keywords', 'Keyword coverage'], ['similarity', 'Text relevance']].map(([k, l]) =>
                    <tr key={k}><td>{l}</td>{result.candidates.map((c) => <td key={c.id}>{pct(c.breakdown[k])}<Bar v={c.breakdown[k]} /></td>)}</tr>)}
                  <tr><td>Parsing quality</td>{result.candidates.map((c) => <td key={c.id} className="small">{c.parsing}</td>)}</tr>
                  <tr><td>Strengths (required skills evidenced)</td>{result.candidates.map((c) => <td key={c.id} className="small">{c.strengths.join(', ') || '—'}</td>)}</tr>
                  <tr><td>Areas needing review</td>{result.candidates.map((c) => <td key={c.id} className="small">{c.review_areas.length ? c.review_areas.map((x) => <div key={x}>{x}</div>) : '—'}</td>)}</tr>
                </tbody></table></div>)}
            <p className="small muted">{result?.note} Comparisons use only resume content versus the job description; no personal attributes are used.</p>
          </div>
        </>
      )}
    </>
  )
}

function Versions({ cands, jobId, setJobId, jobs }) {
  const [a, setA] = useState(''), [b, setB] = useState(''), [res, setRes] = useState(null), [err, setErr] = useState('')
  const run = async () => { setErr(''); setRes(null); try { setRes(await api.post('/versions/compare', { old_id: a, new_id: b })) } catch (e) { setErr(e.message) } }
  const sign = (n) => (n > 0 ? '+' : '') + n
  return (
    <div className="card">
      <p className="muted">Upload both versions in an analysis for the same job description, then choose them here.</p>
      <label htmlFor="vj">Job description</label><select id="vj" value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">Select…</option>{jobs.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</select>
      <div className="grid g2"><div><label htmlFor="va">Old version</label><select id="va" value={a} onChange={(e) => setA(e.target.value)}><option value="">Select…</option>{cands.map((c) => <option key={c.id} value={c.id}>{c.filename}</option>)}</select></div>
        <div><label htmlFor="vb">New version</label><select id="vb" value={b} onChange={(e) => setB(e.target.value)}><option value="">Select…</option>{cands.map((c) => <option key={c.id} value={c.id}>{c.filename}</option>)}</select></div></div>
      <p><button className="btn" disabled={!a || !b || a === b} onClick={run}>Compare versions</button></p>
      {err && <ErrorBox msg={err} />}
      {res && <>
        <p>Estimated score change: <strong>{sign(res.score_change)}</strong> · Parsing quality change: {sign(res.parsing_change)} · Job keywords covered: {sign(res.keyword_coverage_change)}</p>
        <p className="small">Newly evidenced skills: {res.newly_evidenced.join(', ') || 'none'} · No longer evidenced: {res.no_longer_evidenced.join(', ') || 'none'}</p>
        <div className="grid g2"><div><h3>Added</h3>{res.added.map((x, i) => <div className="diff-a small" key={i}>{x}</div>)}{!res.added.length && <p className="muted small">None</p>}</div>
          <div><h3>Removed</h3>{res.removed.map((x, i) => <div className="diff-r small" key={i}>{x}</div>)}{!res.removed.length && <p className="muted small">None</p>}</div></div>
        <h3 style={{ marginTop: 12 }}>Modified lines</h3>{res.modified.map((m, i) => <div key={i} className="small"><div className="diff-r">{m.before}</div><div className="diff-a">{m.after}</div></div>)}
        <p className="small muted">{res.note}</p></>}
    </div>
  )
}
