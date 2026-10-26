async function req(url, opts) {
  let r
  try { r = await fetch('/api' + url, opts) } catch { throw new Error('Cannot reach the server. Is the backend running?') }
  let d = null
  try { d = await r.json() } catch { /* non-JSON */ }
  if (!r.ok) throw new Error(d?.error?.message || `Request failed (${r.status})`)
  return d
}
const json = (method) => (url, body) => req(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
export const api = {
  get: (u) => req(u), post: json('POST'), put: json('PUT'), del: (u) => req(u, { method: 'DELETE' }),
  form: (u, fd) => req(u, { method: 'POST', body: fd }),
}
export async function downloadPost(url, body, fallbackName) {
  const r = await fetch('/api' + url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) { let d = null; try { d = await r.json() } catch {} throw new Error(d?.error?.message || 'Export failed') }
  const blob = await r.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob); a.download = fallbackName; a.click(); URL.revokeObjectURL(a.href)
}
export const fmtDate = (s) => (s ? new Date(s).toLocaleString() : '—')
export const pct = (v) => (v == null ? 'n/a' : Math.round(v * 100) + '%')
