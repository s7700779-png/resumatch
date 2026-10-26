import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((msg, kind = 'ok') => {
    const id = Math.random()
    setItems((x) => [...x, { id, msg, kind }])
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4000)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">{items.map((t) => <div key={t.id} className={'toast ' + t.kind}>{t.msg}</div>)}</div>
    </ToastCtx.Provider>
  )
}

export function useLoad(fn, deps = [], poll = null) {
  const [state, set] = useState({ data: null, error: null, loading: true })
  const load = useCallback(async (quiet) => {
    if (!quiet) set((s) => ({ ...s, loading: true }))
    try { set({ data: await fn(), error: null, loading: false }) }
    catch (e) { set((s) => ({ data: quiet ? s.data : null, error: e.message, loading: false })) }
  }, deps) // eslint-disable-line
  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!poll) return
    const t = setInterval(() => { if (poll(state.data)) load(true) }, 1500)
    return () => clearInterval(t)
  }, [poll, load, state.data])
  return { ...state, reload: () => load(true) }
}

export const Head = ({ title, sub, children }) => (
  <div className="head"><div><h1>{title}</h1>{sub && <p>{sub}</p>}</div><div className="row">{children}</div></div>
)
export const Skeleton = ({ rows = 4 }) => <div className="card" aria-busy="true">{Array.from({ length: rows }).map((_, i) => <div key={i} className="skel" style={{ width: 100 - i * 12 + '%' }} />)}</div>
export const ErrorBox = ({ msg, retry }) => <div className="err" role="alert">{msg} {retry && <button className="btn ghost sm" onClick={retry}>Retry</button>}</div>
export const Empty = ({ title, text, children }) => <div className="empty"><h3>{title}</h3><p>{text}</p>{children}</div>
export const Bar = ({ v }) => <div className="bar" title={v == null ? 'n/a' : Math.round(v * 100) + '%'}><i style={{ width: (v || 0) * 100 + '%' }} /></div>

const STATUS = { completed: 'ok', failed: 'bad', partially_completed: 'warn', processing: 'warn', pending: '', skipped: '' }
export const Badge = ({ s }) => <span className={'badge ' + (STATUS[s] ?? '')}>{String(s).replace('_', ' ')}</span>
export const scoreClass = (s) => (s >= 70 ? 'ok' : s >= 40 ? 'warn' : 'bad')

export function Confirm({ title, text, onYes, onNo, yes = 'Delete' }) {
  useEffect(() => { const k = (e) => e.key === 'Escape' && onNo(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [onNo])
  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <div className="card"><h2>{title}</h2><p>{text}</p>
        <div className="row"><button className="btn danger" onClick={onYes} autoFocus>{yes}</button><button className="btn ghost" onClick={onNo}>Cancel</button></div></div>
    </div>
  )
}

export function Pager({ page, total, per, onPage }) {
  const pages = Math.max(1, Math.ceil(total / per))
  return (
    <div className="pager"><span className="small muted">{total} total</span>
      <button className="btn ghost sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <span className="small">Page {page} of {pages}</span>
      <button className="btn ghost sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button></div>
  )
}

export function Highlight({ text, terms }) {
  if (!terms?.length) return <>{text}</>
  const rx = new RegExp('(' + terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi')
  return <>{text.split(rx).map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : p))}</>
}

export function useDebounced(v, ms = 300) {
  const [d, setD] = useState(v)
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t) }, [v, ms])
  return d
}
