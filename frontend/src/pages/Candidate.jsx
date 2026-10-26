import React, { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, fmtDate, pct } from '../api.js'
import { Head, Skeleton, ErrorBox, Badge, Bar, Highlight, Confirm, scoreClass, useLoad, useToast } from '../ui.jsx'

const TYPE = { exact: 'Exact', synonym: 'Synonym', semantic: 'Semantic (needs review)', not_found: 'Not found' }

export default function Candidate() {
  const { candidateId: id } = useParams(), nav = useNavigate(), toast = useToast()
  const [sel, setSel] = useState(null), [del, setDel] = useState(false)
  const { data, error, loading, reload } = useLoad(() => api.get(`/candidates/${id}`), [id])
  if (loading) return <Skeleton rows={8} />
  if (error) return <ErrorBox msg={error} retry={reload} />
  const c = data.candidate, r = c.result
  if (!r) return <ErrorBox msg={c.error || 'This resume has not been analysed successfully.'} />
  const skills = [...r.required.map((s) => ({ ...s, req: true })), ...r.preferred]
  const chosen = skills.find((s) => s.skill === sel)
  const report = async () => { try { const x = await api.post(`/candidates/${id}/report`); window.location.href = `/api/reports/${x.report_id}/download`; toast('Report generated') } catch (e) { toast(e.message, 'error') } }
  const addCompare = () => { const ids = JSON.parse(localStorage.getItem('compare_ids') || '[]'); if (!ids.includes(id)) ids.push(id); localStorage.setItem('compare_ids', JSON.stringify(ids)); nav('/compare') }
  const remove = async () => { try { await api.del(`/candidates/${id}`); toast('Analysis deleted'); nav(`/batches/${c.batch_id}`) } catch (e) { toast(e.message, 'error') } }
  const cls = (s) => (s.status === 'matched' ? 'ok' : s.status === 'partial' ? 'part' : 'miss')
  return (
    <>
      <Head title={c.name || c.filename} sub={`${c.filename} · ${c.job.title} · ${fmtDate(c.analyzed_at)}`}>
        <Link className="btn" to={`/improve/${id}`}>Improvement studio</Link>
        <button className="btn ghost" onClick={addCompare}>Add to comparison</button>
        <button className="btn ghost" onClick={report}>Download report (PDF)</button>
        <a className="btn ghost" href={`/api/candidates/${id}/file`}>Original file</a>
        <Link className="btn ghost" to={`/batches/${c.batch_id}`}>Back to batch</Link>
        <button className="btn danger" onClick={() => setDel(true)}>Delete</button>
      </Head>
      <div className="grid g3">
        <div className="card"><div className={'score'}>{r.score}<span className="muted" style={{ fontSize: 16 }}>/100</span></div><p className="small muted">Estimated job-relevance match <span className={'badge ' + scoreClass(r.score)}>{r.score >= 70 ? 'strong' : r.score >= 40 ? 'moderate' : 'low'}</span></p></div>
        <div className="card"><h3>Document parsing quality</h3><p>{r.parsing.label}</p><Bar v={r.parsing.score / 100} />{r.parsing.warnings.map((w) => <p key={w} className="small muted">{w}</p>)}</div>
        <div className="card"><h3>Evidence coverage</h3><p>{r.evidence.label}</p><Bar v={r.evidence.score} /></div>
      </div>
      <div className="note" style={{ marginBottom: 16 }}>{r.disclaimer} Three separate indicators are shown on purpose: match, parsing quality and evidence coverage are not combined.</div>
      <div className="card tw"><h2>Score breakdown</h2>
        <table><thead><tr><th>Component</th><th>Value</th><th>Weight</th><th>Points</th><th /></tr></thead><tbody>
          {Object.values(r.breakdown).map((b) => <tr key={b.label}><td>{b.label}</td><td>{pct(b.value)}</td><td>{Math.round(b.weight * 100)}%</td><td>{b.points ?? '—'}</td><td style={{ width: 120 }}><Bar v={b.value} /></td></tr>)}</tbody></table>
        <p className="small muted">Weighted sum of the components; components that don't apply to this job are left out and weights renormalised. Method: {r.method}.</p></div>
      <div className="grid g2">
        <div className="card"><h2>Skills (click for evidence)</h2>
          {skills.map((s) => <button key={s.skill} className={`tag ${cls(s)} ${sel === s.skill ? 'sel' : ''}`} onClick={() => setSel(s.skill)} title={TYPE[s.match_type]}>{s.skill}{s.req ? ' *' : ''}</button>)}
          <p className="small muted">* required · green: found · tan: related wording only (not confirmed) · red: not clearly evidenced</p>
          {chosen && <div className="note"><strong>{chosen.skill}</strong> — {TYPE[chosen.match_type]}{chosen.listed_only && ' · listed in skills section only'}
            {chosen.evidence.length ? chosen.evidence.map((e, i) => <p key={i} style={{ marginTop: 6 }}>“<Highlight text={e.text} terms={[e.term].filter(Boolean)} />” <span className="muted">({e.section}{e.reason ? `, ${e.reason}` : ''})</span></p>) : <p style={{ marginTop: 6 }}>{chosen.note}</p>}</div>}
        </div>
        <div className="card"><h2>Findings</h2>
          <h3>Observations</h3>{r.observations.length ? <ul>{r.observations.map((o) => <li key={o}>{o}</li>)}</ul> : <p className="muted small">None.</p>}
          <h3>Improvement opportunities</h3>{r.opportunities.length ? <ul>{r.opportunities.map((o) => <li key={o}>{o}</li>)}</ul> : <p className="muted small">None.</p>}
          <h3>Job keywords</h3><p className="small">Covered: {r.keywords.covered.join(', ') || '—'}<br />Not found: {r.keywords.missing.join(', ') || '—'}</p></div>
      </div>
      <div className="grid g2">
        <div className="card"><h2>Extracted details <span className="small muted">(facts from the document)</span></h2>
          <p className="small">Name: {r.extracted.name || 'Not detected'}<br />Email: {r.extracted.email || 'Not detected'}<br />Phone: {r.extracted.phone || 'Not detected'}</p>
          {[['Summary', r.extracted.summary ? [r.extracted.summary] : []], ['Experience', r.extracted.experience], ['Projects', r.extracted.projects], ['Education', r.extracted.education], ['Certifications', r.extracted.certifications]].map(([t, v]) => (
            <div key={t}><h3>{t}</h3>{v?.length ? <ul className="small">{v.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="small muted">Not detected</p>}</div>))}
          {r.uncertain_fields.length > 0 && <p className="small muted">Uncertain fields: {r.uncertain_fields.join(', ')}</p>}</div>
        <div className="card"><h2>ATS readability audit</h2>
          {r.ats.map((a, i) => <div key={i} style={{ marginBottom: 10 }}><Badge s={a.kind} /> <span className={'badge ' + (a.severity === 'warning' ? 'warn' : a.severity === 'ok' ? 'ok' : '')}>{a.severity}</span> <strong>{a.title}</strong>
            <div className="small">{a.detail}</div><div className="small muted">Recommendation: {a.recommendation}</div></div>)}
          <p className="small muted">“confirmed” = measurable in this file; “heuristic” = common-practice warning. No employer's ATS is simulated.</p></div>
      </div>
      <div className="card"><h2>Extracted resume text with matched terms highlighted</h2><div className="resume"><Highlight text={c.text} terms={r.highlights} /></div></div>
      {del && <Confirm title="Delete this analysis?" text="The analysis, uploaded file and its reports will be permanently removed." onYes={remove} onNo={() => setDel(false)} />}
    </>
  )
}
