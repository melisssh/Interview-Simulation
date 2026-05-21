import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Header from '../components/Header'

import { API } from '../api'

export default function Dashboard() {
  const [interviews, setInterviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const hasPreparingRef = useRef(false)
  const fetchInterviewsRef = useRef(null)
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const email = localStorage.getItem('email') || ''
  const isAdmin = localStorage.getItem('is_admin') === '1'

  const fetchInterviews = () => {
    return fetch(`${API}/interviews`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (res.status === 401) { navigate('/login'); return null }
        return res.json()
      })
      .then((data) => {
        if (Array.isArray(data)) setInterviews(data)
      })
      .catch(() => setError('Could not fetch list'))
  }
  fetchInterviewsRef.current = fetchInterviews

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    fetchInterviews().finally(() => setLoading(false))
    fetch(`${API}/profile`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((profile) => { if (!profile?.full_name) navigate('/profile') })
      .catch(() => {})
  }, [token, navigate])

  useEffect(() => {
    hasPreparingRef.current = interviews.some((i) => i.status === 'preparing' || i.status === 'created' || i.status === 'analyzing')
  }, [interviews])

  useEffect(() => {
    const interval = setInterval(() => {
      if (hasPreparingRef.current) fetchInterviewsRef.current()
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  if (!token) return null

  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this interview?')) return
    try {
      const res = await fetch(`${API}/interviews/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Failed to delete interview')
        return
      }
      setInterviews((prev) => prev.filter((item) => item.id !== id))
    } catch {
      setError('An error occurred while deleting the interview')
    }
  }



  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <Header />

      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '1.5rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '1.25rem', color: '#111' }}>Dashboard</h1>

        {loading && <p style={{ color: '#6b7280' }}>Loading...</p>}
        {error && <p style={{ color: '#dc2626' }}>{error}</p>}

        {!loading && !error && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: '1rem',
          }}>
            <Link
              to="/interview/new"
              style={{
                border: '2px dashed #d1d5db',
                borderRadius: 12,
                padding: '1.5rem',
                minHeight: 160,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#fff',
                textDecoration: 'none',
                color: '#6b7280',
                transition: 'border-color 0.2s',
              }}
              onMouseOver={(e) => { e.currentTarget.style.borderColor = '#9ca3af'; e.currentTarget.style.color = '#374151'; }}
              onMouseOut={(e) => { e.currentTarget.style.borderColor = '#d1d5db'; e.currentTarget.style.color = '#6b7280'; }}
            >
              <span style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>+</span>
              <span style={{ fontWeight: 500 }}>Create new interview</span>
            </Link>

{interviews.map((i) => {
              const s = i.status
              const isPreparing = s === 'preparing'
              const isPrepFailed = s === 'preparation_failed'
              const isReady = s === 'ready' || s === 'in_progress'
              const isAnalyzing = s === 'analyzing'
              const isAnalyzed = s === 'analyzed'
              const isAnalysisFailed = s === 'analysis_failed'

              const statusLabel = isPreparing ? 'Preparing questions...'
                : isPrepFailed ? 'Preparation failed'
                : isReady ? 'Ready'
                : isAnalyzing ? 'Analyzing...'
                : isAnalyzed ? 'Results ready'
                : isAnalysisFailed ? 'Analysis failed'
                : s

              const ctaText = isReady ? 'Start interview →'
                : isAnalyzed ? 'Go to result →'
                : isAnalysisFailed ? 'Retry analysis →'
                : isPrepFailed ? 'Retry →'
                : ''

              const ctaLink = isReady ? `/interview/${i.id}`
                : isAnalyzed || isAnalysisFailed ? `/interview/${i.id}/sonuc`
                : isPrepFailed ? `/interview/${i.id}`
                : '#'

              const showSpinner = isPreparing || isAnalyzing

              return (
                <div
                  key={i.id}
                  style={{
                    background: isPreparing ? '#f0fdf4' : isAnalyzing ? '#eff6ff' : '#fff',
                    border: `1px solid ${isPrepFailed || isAnalysisFailed ? '#fecaca' : isPreparing ? '#22c55e' : isAnalyzing ? '#3b82f6' : '#e5e7eb'}`,
                    borderRadius: 12,
                    padding: '1.25rem',
                    minHeight: 160,
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => handleDelete(i.id)}
                    style={{
                      position: 'absolute',
                      top: 8,
                      right: 8,
                      border: 'none',
                      background: 'transparent',
                      color: '#9ca3af',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                    }}
                    title="Delete interview"
                  >
                    Delete
                  </button>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.25rem' }}>
                    {formatDate(i.created_at)}
                  </div>
                  {!showSpinner && ctaLink !== '#' ? (
                    <Link
                      to={ctaLink}
                      style={{
                        fontWeight: 600,
                        fontSize: '1rem',
                        color: '#111',
                        textDecoration: 'none',
                        marginBottom: '0.5rem',
                      }}
                    >
                      {i.title || 'Untitled interview'}
                    </Link>
                  ) : (
                    <div style={{ fontWeight: 600, fontSize: '1rem', color: '#6b7280', marginBottom: '0.5rem' }}>
                      {i.title || 'Untitled interview'}
                    </div>
                  )}
                  <div style={{ fontSize: '0.875rem', color: isPrepFailed || isAnalysisFailed ? '#dc2626' : '#6b7280', marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {showSpinner && <span style={{ display: 'inline-block', width: 12, height: 12, borderRadius: '50%', border: '2px solid #9ca3af', borderTopColor: 'transparent', animation: 'spin 0.8s linear infinite' }} />}
                    {statusLabel}
                  </div>
                  {ctaText && !showSpinner && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <Link to={ctaLink} style={{ fontSize: '0.85rem', color: isPrepFailed || isAnalysisFailed ? '#dc2626' : '#2563eb', textDecoration: 'none' }}>
                        {ctaText}
                      </Link>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {!loading && !error && interviews.length === 0 && (
          <p style={{ color: '#6b7280', marginTop: '1rem' }}>No interviews yet. Click the &quot;Create new interview&quot; card.</p>
        )}
      </main>
    </div>
  )
}
