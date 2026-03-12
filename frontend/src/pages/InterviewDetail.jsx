import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API = '/api'

export default function InterviewDetail() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    if (!id) return
    fetch(`${API}/interviews/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401 || res.status === 403) navigate('/login')
        if (!res.ok) throw new Error('Mülakat alınamadı')
        return res.json()
      })
      .then(setInterview)
      .catch(() => setError('Yüklenemedi'))
      .finally(() => setLoading(false))
  }, [id, token, navigate])

  const headerStyle = {
    background: '#fff',
    borderBottom: '1px solid #e5e7eb',
    padding: '0.75rem 1.5rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  }

  if (!token) return null
  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <header style={headerStyle}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <Link to="/dashboard" style={{ fontSize: '0.95rem', color: '#374151', textDecoration: 'none' }}>
          Dashboard'a dön
        </Link>
      </header>
      <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: '#6b7280' }}>Yükleniyor...</div>
    </div>
  )
  if (error || !interview) return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <header style={headerStyle}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <Link to="/dashboard" style={{ fontSize: '0.95rem', color: '#374151', textDecoration: 'none' }}>
          Dashboard'a dön
        </Link>
      </header>
      <div style={{ padding: '3rem 1.5rem', color: '#dc2626', textAlign: 'center' }}>{error || 'Bulunamadı'}</div>
    </div>
  )

  const hasResult = interview.transcript || (interview.feedback && (interview.feedback.summary || interview.feedback.strengths || interview.feedback.improvements))

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <header style={headerStyle}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <Link to="/dashboard" style={{ fontSize: '0.95rem', color: '#374151', textDecoration: 'none' }}>
          Dashboard'a dön
        </Link>
      </header>
      <div style={{ maxWidth: 640, margin: '0 auto', padding: '3rem 1.5rem', background: '#fff', minHeight: 'calc(100vh - 57px)', boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          {interview.title}
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          {interview.domain} · {interview.language} · {interview.status}
        </p>

        <section>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#374151', marginBottom: '0.75rem' }}>Mülakat soruları</h2>
          {interview.questions?.length ? (
            <ol style={{ paddingLeft: '1.25rem', margin: 0 }}>
              {interview.questions.map((q, i) => (
                <li key={i} style={{ marginBottom: '0.75rem', color: '#111', lineHeight: 1.5 }}>{q.text}</li>
              ))}
            </ol>
          ) : (
            <p style={{ color: '#6b7280', margin: 0 }}>Bu mülakat için henüz soru atanmamış.</p>
          )}
        </section>

        <p style={{ marginTop: '1.5rem', padding: '1rem', background: '#f5f5f5', borderRadius: 8, fontSize: '0.95rem', color: '#6b7280', lineHeight: 1.5 }}>
          Mülakat bittikten sonra video yüklenip analiz edilecek. Analiz ve geri bildirim <strong>Sonuç</strong> sayfasında paylaşılacak; bu ekran sadece sorular içindir.
        </p>

        <p style={{ marginTop: '1.5rem' }}>
          <Link
            to={`/interview/${id}/run`}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#111',
              color: '#fff',
              textDecoration: 'none',
              borderRadius: 8,
              display: 'inline-block',
              fontWeight: 500,
              fontSize: '1rem',
            }}
          >
            Mülakata başla
          </Link>
        </p>

        {hasResult ? (
          <p style={{ marginTop: '1.5rem' }}>
            <Link
              to={`/interview/${id}/sonuc`}
              style={{
                padding: '0.75rem 1.5rem',
                background: '#111',
                color: '#fff',
                textDecoration: 'none',
                borderRadius: 8,
                display: 'inline-block',
                fontWeight: 500,
                fontSize: '1rem',
              }}
            >
              Sonuçları gör (analiz ve geri bildirim)
            </Link>
          </p>
        ) : (
          <p style={{ marginTop: '1.5rem', color: '#6b7280', fontSize: '0.95rem' }}>
            Analiz hazır olduğunda &quot;Sonuçları gör&quot; butonu burada görünecek.
          </p>
        )}
      </div>
    </div>
  )
}
