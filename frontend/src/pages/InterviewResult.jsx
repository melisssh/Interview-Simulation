import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { API } from '../api'

/* ─── utils ─── */
const toNum     = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null }
const pickScore = (...vals) => { for (const v of vals) { const n = toNum(v); if (n !== null) return n } return null }
const parseMx   = (raw) => {
  if (!raw) return {}
  if (typeof raw === 'object') return raw
  try { const p = JSON.parse(raw); return (p && typeof p === 'object') ? p : {} } catch { return {} }
}
const pickMx = (...cs) => { for (const c of cs) { const p = parseMx(c); if (p && Object.keys(p).length) return p } return {} }

const REC = {
  label: {
    'Strong Yes': 'Interview Ready',
    'Yes':        'On the Right Track',
    'Maybe':      'Keep Practicing',
    'No':         'More Practice Needed',
    'Strong No':  'Early Stage',
  },
  color: { 'Strong Yes': '#16a34a', 'Yes': '#2563eb', 'Maybe': '#d97706', 'No': '#dc2626', 'Strong No': '#991b1b' },
  bg:    { 'Strong Yes': '#f0fdf4', 'Yes': '#eff6ff', 'Maybe': '#fffbeb', 'No': '#fef2f2', 'Strong No': '#fef2f2' },
}

/* ─── InfoChip ─── */
const InfoChip = ({ label, value }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: '0.45rem',
    padding: '0.4rem 0.85rem', background: '#f9fafb',
    border: '1px solid #e5e7eb', borderRadius: 99,
    fontSize: '0.82rem', color: '#374151',
  }}>
    <span style={{ color: '#9ca3af', fontWeight: 500 }}>{label}:</span>
    <span style={{ fontWeight: 600 }}>{value}</span>
  </div>
)

/* ─── CircleGauge ─── */
const CircleGauge = ({ score }) => {
  const s    = Math.max(0, Math.min(100, Number(score) || 0))
  const r    = 48, cx = 60, cy = 60
  const circ = 2 * Math.PI * r
  const off  = circ - (s / 100) * circ
  const color = s >= 75 ? '#16a34a' : s >= 55 ? '#d97706' : '#dc2626'
  return (
    <svg width="120" height="120" viewBox="0 0 120 120">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#f3f4f6" strokeWidth="9" />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="9"
        strokeDasharray={circ} strokeDashoffset={off} strokeLinecap="round"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      <text x={cx} y={cy - 4}  textAnchor="middle" fontSize="24" fontWeight="700" fill={color}>{s}</text>
      <text x={cx} y={cy + 13} textAnchor="middle" fontSize="10" fill="#9ca3af">/ 100</text>
    </svg>
  )
}

/* ─── ScoreRow ─── */
const ScoreRow = ({ label, score, note, last }) => {
  const s     = Math.max(0, Math.min(100, Number(score) || 0))
  const color = s >= 75 ? '#16a34a' : s >= 55 ? '#d97706' : '#dc2626'
  return (
    <div style={{ paddingBottom: last ? 0 : '1rem', marginBottom: last ? 0 : '1rem', borderBottom: last ? 'none' : '1px solid #f3f4f6' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.85rem', color: '#374151', fontWeight: 500 }}>{label}</span>
          {note && <span style={{ fontSize: '0.72rem', color: '#9ca3af' }}>· {note}</span>}
        </div>
        <span style={{ fontSize: '0.85rem', fontWeight: 700, color }}>{s}</span>
      </div>
      <div style={{ height: 5, background: '#f3f4f6', borderRadius: 99 }}>
        <div style={{ width: `${s}%`, height: '100%', background: color, borderRadius: 99, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  )
}

/* ─── OllamaBlock ─── */
const SECTION_ICONS = { 'Answer Analysis': '📋', 'Communication Style': '🎤', 'Recommendations': '💡' }

const OllamaBlock = ({ text }) => {
  if (!text) return null

  const regex = /\*\*([^*]+)\*\*/g
  const titles = [], positions = []
  let match
  while ((match = regex.exec(text)) !== null) {
    titles.push(match[1].trim())
    positions.push({ end: regex.lastIndex })
  }
  if (titles.length === 0) {
    return <p style={{ margin: 0, fontSize: '0.875rem', color: '#374151', lineHeight: 1.75 }}>{text}</p>
  }

  const blocks = titles.map((title, i) => {
    const bodyStart = positions[i].end
    const bodyEnd   = i + 1 < positions.length
      ? text.indexOf('**', positions[i].end)
      : text.length
    return { title, body: text.slice(bodyStart, bodyEnd > bodyStart ? bodyEnd : text.length).trim() }
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {blocks.map((b, i) => {
        const lines  = b.body.split('\n').filter(l => l.trim())
        const isList = lines.some(l => /^[-•]/.test(l.trim()))
        const isLast = i === blocks.length - 1
        return (
          <div key={i} style={{ padding: '1.25rem 0', borderBottom: isLast ? 'none' : '1px solid #f3f4f6' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '1rem' }}>{SECTION_ICONS[b.title] || '•'}</span>
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#374151' }}>{b.title}</span>
            </div>
            {isList ? (
              <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {lines.map((l, j) => (
                  <li key={j} style={{ fontSize: '0.875rem', color: '#4b5563', lineHeight: 1.65 }}>
                    {l.replace(/^[-•]\s*/, '')}
                  </li>
                ))}
              </ul>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                {lines.map((l, j) => {
                  const qMatch = l.match(/^(Question\s*\d+)\s*[:：]\s*(.+)/i)
                  if (qMatch) return (
                    <div key={j} style={{ display: 'flex', gap: '0.6rem', alignItems: 'flex-start' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#9ca3af', whiteSpace: 'nowrap', paddingTop: '0.18rem', minWidth: 60 }}>{qMatch[1]}</span>
                      <span style={{ fontSize: '0.875rem', color: '#4b5563', lineHeight: 1.65 }}>{qMatch[2]}</span>
                    </div>
                  )
                  return <p key={j} style={{ margin: 0, fontSize: '0.875rem', color: '#4b5563', lineHeight: 1.65 }}>{l}</p>
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ─── Shell ─── */
const Shell = ({ children }) => (
  <div style={{ minHeight: '100vh', background: '#fff' }}>
    <header style={{ borderBottom: '1px solid #e5e7eb', padding: '0 1.75rem', height: 52, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Link to="/dashboard" style={{ fontWeight: 700, color: '#111', textDecoration: 'none', fontSize: '1rem' }}>Interview Simulation</Link>
      <Link to="/dashboard" style={{ fontSize: '0.85rem', color: '#6b7280', textDecoration: 'none' }}>← Back to Dashboard</Link>
    </header>
    {children}
  </div>
)

/* ─── Main ─── */
export default function InterviewResult() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const token    = localStorage.getItem('token')

  const [interview, setInterview] = useState(null)
  const [analysis,  setAnalysis]  = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error,     setError]     = useState('')

  /* derived */
  const norm = analysis || (interview?.feedback
    ? { metrics: parseMx(interview.feedback.metrics_json), strengths: interview.feedback.strengths, improvements: interview.feedback.improvements }
    : null)
  const mx = pickMx(norm?.metrics, norm?.metrics_json, interview?.feedback?.metrics_json)

  const contentScore = pickScore(norm?.content_quality_score, mx.content_score)
  const speechScore  = pickScore(norm?.speech_quality_score,  mx.speech_quality_score)
  const nvRaw        = pickScore(norm?.nonverbal_score, mx.nonverbal_aggregate, mx.nonverbal_score)
  const hasNV        = nvRaw !== null && nvRaw > 0
  const overall      = pickScore(norm?.overall_score, mx.overall_score) ?? 0

  const rec      = norm?.overall_recommendation || ''
  const recColor = REC.color[rec] || '#6b7280'
  const recBg    = REC.bg[rec]    || '#f9fafb'

  const strengths = norm?.metrics?.strengths
    || (norm?.strengths    ? norm.strengths.split('\n').map(s => s.trim()).filter(Boolean)    : [])
  const improvs   = norm?.metrics?.improvements
    || (norm?.improvements ? norm.improvements.split('\n').map(s => s.trim()).filter(Boolean) : [])

  const aiText = norm?.actionable_recommendations || mx.actionable_recommendations || ''

  const scoreLabel = overall >= 80 ? 'Excellent' : overall >= 70 ? 'Good' : overall >= 55 ? 'Fair' : 'Needs Improvement'

  /* fetch */
  useEffect(() => {
    if (!token) { navigate('/login'); return }
    const load = async () => {
      try {
        const ir = await fetch(`${API}/interviews/${id}`, { headers: { Authorization: `Bearer ${token}` } })
        if (ir.status === 401 || ir.status === 403) { navigate('/login'); return }
        if (!ir.ok) throw new Error('Interview not found')
        const iv = await ir.json()
        if (['created', 'preparing', 'ready', 'in_progress'].includes(iv.status)) { navigate(`/interview/${id}`); return }
        setInterview(iv)
        const ar = await fetch(`${API}/interviews/${id}/analysis`, { headers: { Authorization: `Bearer ${token}` } })
        if (ar.ok) setAnalysis(await ar.json())
      } catch (e) { setError(e.message) }
      finally { setLoading(false) }
    }
    load()
  }, [id, token, navigate])

  /* poll */
  useEffect(() => {
    if (!token || !id || !interview || analysis || interview.status !== 'analyzing') return
    const t = setInterval(async () => {
      try {
        const [ir, ar] = await Promise.all([
          fetch(`${API}/interviews/${id}`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API}/interviews/${id}/analysis`, { headers: { Authorization: `Bearer ${token}` } }),
        ])
        if (ir.ok) setInterview(await ir.json())
        if (ar.ok) setAnalysis(await ar.json())
      } catch { /* ignore */ }
    }, 5000)
    return () => clearInterval(t)
  }, [id, token, interview, analysis])

  const startAnalysis = async () => {
    setAnalyzing(true); setError('')
    setInterview(p => p ? { ...p, status: 'analyzing' } : p)
    try {
      const res  = await fetch(`${API}/interviews/${id}/analyze`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
      const data = await res.json()
      if (res.ok) {
        const [ar, ir] = await Promise.all([
          fetch(`${API}/interviews/${id}/analysis`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API}/interviews/${id}`, { headers: { Authorization: `Bearer ${token}` } }),
        ])
        if (ar.ok) setAnalysis(await ar.json()); else setAnalysis(null)
        if (ir.ok) setInterview(await ir.json()); else setInterview(p => p ? { ...p, status: 'analyzed' } : p)
      } else {
        setError(data.detail || 'Could not start analysis')
        setInterview(p => p ? { ...p, status: 'analysis_failed' } : p)
      }
    } catch (e) {
      setError('Analysis error: ' + e.message)
      setInterview(p => p ? { ...p, status: 'analysis_failed' } : p)
    } finally { setAnalyzing(false) }
  }

  const isRunning = analyzing || interview?.status === 'analyzing'

  if (!token) return null
  if (loading)  return <Shell><div style={{ padding: '4rem', textAlign: 'center', color: '#9ca3af', fontSize: '0.9rem' }}>Loading…</div></Shell>
  if (error && !analysis) return (
    <Shell>
      <div style={{ maxWidth: 560, margin: '3rem auto', padding: '0 1.5rem' }}>
        <p style={{ color: '#dc2626', fontSize: '0.9rem', marginBottom: '1rem' }}>{error}</p>
        <button onClick={() => navigate('/dashboard')} style={btnStyle('#111')}>Back to Dashboard</button>
      </div>
    </Shell>
  )
  if (!interview) return <Shell><div style={{ padding: '4rem', textAlign: 'center', color: '#dc2626', fontSize: '0.9rem' }}>Interview not found</div></Shell>

  return (
    <div style={{ minHeight: '100vh', background: '#fff', fontFamily: 'system-ui, -apple-system, sans-serif' }}>

      {/* Header */}
      <header style={{ borderBottom: '1px solid #e5e7eb', padding: '0 1.75rem', height: 52, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link to="/dashboard" style={{ fontWeight: 700, color: '#111', textDecoration: 'none', fontSize: '1rem' }}>Interview Simulation</Link>
        <Link to="/dashboard" style={{ fontSize: '0.85rem', color: '#6b7280', textDecoration: 'none' }}>← Back to Dashboard</Link>
      </header>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '2.5rem 1.75rem' }}>

        {/* Title row */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 600, color: '#111' }}>{interview.title}</h1>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: '#9ca3af' }}>
              {interview.domain === 'technical' ? 'Technical Interview' : 'General Interview'}
              {interview.company_name ? ` · ${interview.company_name}` : ''}
            </p>
          </div>
          {(interview.status === 'completed' || interview.status === 'analyzed' || interview.status === 'analysis_failed') && (
            <button onClick={startAnalysis} disabled={isRunning} style={btnStyle(isRunning ? '#9ca3af' : '#374151', isRunning)}>
              {isRunning ? 'Running analysis…' : 'Re-run analysis'}
            </button>
          )}
        </div>

        {/* No analysis */}
        {!norm ? (
          <div style={section}>
            {isRunning
              ? <p style={muted}>Analysis in progress, please wait…</p>
              : <>
                  <p style={{ ...muted, marginBottom: '1rem' }}>
                    {interview.status === 'analysis_failed' ? 'Analysis failed. You can try again.' : 'Analysis has not been started yet.'}
                  </p>
                  <button onClick={startAnalysis} style={btnStyle('#111')}>
                    {interview.status === 'analysis_failed' ? 'Try Again' : 'Start Analysis'}
                  </button>
                </>
            }
          </div>
        ) : (
          <>
            {/* SESSION INFO */}
            {(interview.company_name || interview.position || interview.sector || interview.department_name) && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.25rem' }}>
                {interview.company_name && (
                  <InfoChip label="Company" value={interview.company_name} />
                )}
                {interview.position && (
                  <InfoChip label="Position" value={interview.position} />
                )}
                {interview.sector && (
                  <InfoChip label="Sector" value={interview.sector} />
                )}
                {interview.department_name && (
                  <InfoChip label="Department" value={interview.department_name} />
                )}
              </div>
            )}

            {/* TOP PANEL */}
            <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '1px', background: '#e5e7eb', border: '1px solid #e5e7eb', borderRadius: '12px 12px 0 0', overflow: 'hidden' }}>

              {/* Left: gauge */}
              <div style={{ background: '#fff', padding: '2rem 1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
                <CircleGauge score={overall} />
                {rec && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
                    <span style={{ fontSize: '0.72rem', color: '#9ca3af' }}>Your standing</span>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: recColor }}>
                      {REC.label[rec] || rec}
                    </span>
                  </div>
                )}
                <p style={{ margin: '0.1rem 0 0 0', fontSize: '0.72rem', color: '#d1d5db', textAlign: 'center' }}>
                  {interview.domain === 'technical' ? 'Technical' : 'General'}
                  {' · '}
                  {hasNV ? 'Video included' : 'No video'}
                </p>
              </div>

              {/* Right: score bars */}
              <div style={{ background: '#fff', padding: '1.75rem' }}>
                <p style={sectionLabel}>Score Breakdown</p>
                <ScoreRow label="Content Quality"  score={contentScore ?? 0} note="highest weight" />
                <ScoreRow label="Speech Quality"   score={speechScore  ?? 0} />
                {hasNV
                  ? <ScoreRow label="Body Language" score={nvRaw} last />
                  : <p style={{ ...muted, marginTop: '0.5rem', fontSize: '0.78rem' }}>Body language · no video analysis</p>
                }
              </div>
            </div>

            {/* STRENGTHS / IMPROVEMENTS */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px', background: '#e5e7eb', borderLeft: '1px solid #e5e7eb', borderRight: '1px solid #e5e7eb' }}>
              <div style={{ background: '#fff', padding: '1.5rem 1.75rem' }}>
                <p style={sectionLabel}>Strengths</p>
                {strengths.length
                  ? <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                      {strengths.map((s, i) => <li key={i} style={{ fontSize: '0.855rem', color: '#374151', lineHeight: 1.5 }}>{s}</li>)}
                    </ul>
                  : <p style={muted}>—</p>
                }
              </div>
              <div style={{ background: '#fff', padding: '1.5rem 1.75rem', borderLeft: '1px solid #e5e7eb' }}>
                <p style={sectionLabel}>Areas for Improvement</p>
                {improvs.length
                  ? <ul style={{ margin: 0, paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                      {improvs.map((s, i) => <li key={i} style={{ fontSize: '0.855rem', color: '#374151', lineHeight: 1.5 }}>{s}</li>)}
                    </ul>
                  : <p style={muted}>—</p>
                }
              </div>
            </div>

            {/* AI FEEDBACK */}
            {aiText && (
              <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 12px 12px', padding: '1.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
                  <p style={{ ...sectionLabel, marginBottom: 0 }}>DETAILED FEEDBACK</p>
                  <span style={{ fontSize: '0.7rem', color: '#9ca3af', background: '#f9fafb', border: '1px solid #e5e7eb', padding: '0.1rem 0.5rem', borderRadius: 99 }}>AI</span>
                </div>
                <OllamaBlock text={aiText} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/* ── shared micro-styles ── */
const section      = { border: '1px solid #e5e7eb', borderRadius: 12, padding: '1.75rem', background: '#fff' }
const muted        = { margin: 0, fontSize: '0.85rem', color: '#9ca3af' }
const sectionLabel = { margin: '0 0 1rem 0', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#9ca3af' }
const btnStyle     = (bg, disabled) => ({
  padding: '0.5rem 1rem',
  background: bg,
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  fontWeight: 600,
  fontSize: '0.83rem',
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.7 : 1,
})
