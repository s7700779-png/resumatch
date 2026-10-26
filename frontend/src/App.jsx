import React, { useState } from 'react'
import { NavLink, Route, Routes, Link, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Analyze from './pages/Analyze.jsx'
import Batch from './pages/Batch.jsx'
import Candidate from './pages/Candidate.jsx'
import Compare from './pages/Compare.jsx'
import Improve from './pages/Improve.jsx'
import Jobs from './pages/Jobs.jsx'
import History from './pages/History.jsx'
import { Reports, ReportDetail } from './pages/Reports.jsx'
import Settings from './pages/Settings.jsx'
import { Empty } from './ui.jsx'

const NAV = [['/', 'Dashboard'], ['/analyze', 'Analyze Resumes'], ['/history', 'Batches & History'], ['/compare', 'Compare Candidates'], ['/jobs', 'Job Descriptions'], ['/reports', 'Reports'], ['/settings', 'Settings']]
const CRUMB = { analyze: 'Analyze Resumes', batches: 'Batch Analysis', candidates: 'Candidate Results', compare: 'Compare Candidates', improve: 'Improvement Studio', jobs: 'Job Descriptions', history: 'Analysis History', reports: 'Reports', settings: 'Settings' }

export default function App() {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const first = loc.pathname.split('/')[1]
  return (
    <div className="shell">
      <nav className={'side' + (open ? ' open' : '')} aria-label="Main">
        <div className="brand">ResuMatch<small>AI Resume Analyzer &amp; ATS Optimizer</small></div>
        {NAV.map(([to, label]) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)}>{label}</NavLink>)}
      </nav>
      <div className="main">
        <header className="top">
          <button className="btn ghost sm menu" aria-label="Toggle menu" onClick={() => setOpen(!open)}>Menu</button>
          <Link to="/">Home</Link>{first && <span>/ {CRUMB[first] || first}</span>}
        </header>
        <main className="page">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/batches/:batchId" element={<Batch />} />
            <Route path="/candidates/:candidateId" element={<Candidate />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/improve/:candidateId" element={<Improve />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/history" element={<History />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/reports/:reportId" element={<ReportDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Empty title="Page not found" text="That page does not exist."><Link className="btn" to="/">Go to dashboard</Link></Empty>} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
