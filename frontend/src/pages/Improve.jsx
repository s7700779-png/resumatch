import React, { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { Head, Skeleton, ErrorBox, Empty, useLoad, useToast } from '../ui.jsx'

export default function Improve() {
  const { candidateId: id } = useParams(), toast = useToast()
  const [useAi, setUseAi] = useState(false)
  const { data, error, loading, reload } = useLoad(() => api.post(`/candidates/${id}/improve`, { use_ai: useAi }), [id, useAi])
  const [state, setState] = useState({}) // id -> {status, text}
  if (loading) return <Skeleton rows={6} />
  if (error) return <ErrorBox msg={error} retry={reload} />
  const set = (sid, patch) => setState((s) => ({ ...s, [sid]: { ...s[sid], ...patch } }))
  const sugg = data.suggestions
  const accepted = sugg.filter((s) => state[s.id]?.status === 'accepted')
  const text = (s) => state[s.id]?.text ?? s.suggested
  const copy = async (t) => { try { await navigator.clipboard.writeText(t); toast('Copied') } catch { toast('Copy failed — select the text manually', 'error') } }
  const final = accepted.filter((s) => s.kind !== 'keyword').map((s) => (s.kind === 'summary' ? 'Summary:\n' : '- ') + text(s)).join('\n')
  return (
    <>
      <Head title="Resume Improvement Studio" sub="Review each suggestion. Your original file is never changed.">
        <Link className="btn ghost" to={`/candidates/${id}`}>Back to results</Link></Head>
      <div className="card">
        <label className="chk"><input type="checkbox" checked={useAi} disabled={!data.ai.configured && !useAi} onChange={(e) => setUseAi(e.target.checked)} /> Also generate AI suggestions (Gemini)</label>
        <p className="small muted">{data.ai.configured ? 'Contact details are removed before text is sent to the AI provider.' : `AI is unavailable: ${data.ai.message}. Rule-based suggestions are still shown.`}</p>
        {data.ai_error && <ErrorBox msg={data.ai_error} />}
        <div className="note">{data.note}</div>
      </div>
      {!sugg.length ? <div className="card"><Empty title="No suggestions" text="Nothing in this resume triggered a rule-based suggestion." /></div> : sugg.map((s) => {
        const st = state[s.id]?.status
        return (
          <div className="card" key={s.id} style={st === 'rejected' ? { opacity: .55 } : null}>
            <div className="row"><span className="badge">{s.kind}</span><span className={'badge ' + (s.source === 'ai' ? 'warn' : '')}>{s.source === 'ai' ? 'AI-generated' : 'Rule-based'}</span>{st && <span className={'badge ' + (st === 'accepted' ? 'ok' : 'bad')}>{st}</span>}</div>
            {s.kind === 'keyword' ? <p style={{ marginTop: 8 }}><strong>{s.suggested}</strong></p> : (
              <div className="grid g2" style={{ marginTop: 8 }}>
                <div><h3>Original (from your resume)</h3><div className="resume" style={{ maxHeight: 160 }}>{s.original || 'Not detected'}</div></div>
                <div><h3>Suggested (editable)</h3><textarea style={{ minHeight: 100 }} aria-label="Suggested text" value={text(s)} onChange={(e) => set(s.id, { text: e.target.value })} /></div>
              </div>)}
            <p className="small muted">{s.rationale}</p>
            <div className="row"><button className="btn sm" onClick={() => set(s.id, { status: 'accepted' })}>Accept</button><button className="btn ghost sm" onClick={() => set(s.id, { status: 'rejected' })}>Reject</button><button className="btn ghost sm" onClick={() => copy(text(s))}>Copy</button></div>
          </div>)
      })}
      <div className="card"><h2>Final review</h2>
        {final ? <><pre className="resume">{final}</pre><button className="btn" onClick={() => copy(final)}>Copy accepted text</button></> : <p className="muted">Accepted suggestions appear here. Keyword suggestions are reminders only — add a skill to your resume only if it is true.</p>}</div>
    </>
  )
}
