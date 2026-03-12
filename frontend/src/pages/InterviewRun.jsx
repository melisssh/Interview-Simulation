import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API = '/api'

export default function InterviewRun() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [currentIndex, setCurrentIndex] = useState(-1) // -1: daha başlamadı
  const [finishing, setFinishing] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

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
      .catch(() => setError('Mülakat bilgisi alınamadı'))
      .finally(() => setLoading(false))
  }, [id, token, navigate])

  useEffect(() => {
    // Sayfa kapanırken stream varsa durdur
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [])

  async function handleStart() {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
      setCurrentIndex(0)
    } catch (e) {
      setError('Kamera ve mikrofon izni verilmedi. Mülakat başlatılamadı.')
    }
  }

  async function handleNext() {
    if (!interview?.questions) return
    const nextIndex = currentIndex + 1
    if (nextIndex < interview.questions.length) {
      setCurrentIndex(nextIndex)
    } else {
      // Mülakat bitti
      setFinishing(true)
      try {
        await fetch(`${API}/interviews/${id}/status`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ status: 'completed' }),
        })
      } catch {
        // hata olsa bile kullanıcıya çok yansıtma, loglamak yeter
      } finally {
        // Kamerayı kapat
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop())
        }
        setTimeout(() => {
          navigate(`/interview/${id}/sonuc`)
        }, 1500)
      }
    }
  }

  if (!token) return null
  if (loading) return <div style={{ padding: '2rem' }}>Yükleniyor...</div>
  if (error || !interview) return <div style={{ padding: '2rem', color: 'red' }}>{error || 'Mülakat bulunamadı'}</div>

  const questions = interview.questions || []
  const total = questions.length
  const currentQuestion = currentIndex >= 0 && currentIndex < total ? questions[currentIndex] : null

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <header style={{
        background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        padding: '0.75rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <span style={{ fontSize: '0.95rem', color: '#6b7280' }}>
          {interview.title}
        </span>
      </header>

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '2rem 1.5rem', display: 'grid', gap: '1.5rem', gridTemplateColumns: '2fr 3fr' }}>
        {/* Sol: video alanı */}
        <section style={{ background: '#000', borderRadius: 12, overflow: 'hidden', minHeight: 240 }}>
          <video
            ref={videoRef}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            autoPlay
            muted
          />
        </section>

        {/* Sağ: sorular */}
        <section style={{ background: '#fff', borderRadius: 12, padding: '1.5rem' }}>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            Mülakat
          </h1>
          <p style={{ fontSize: '0.95rem', color: '#6b7280', marginBottom: '1rem' }}>
            Sorular sırayla gösterilecek. Her soruya kameraya bakarak yanıt ver.
          </p>

          {error && <p style={{ color: '#dc2626', fontSize: '0.9rem' }}>{error}</p>}

          {currentIndex === -1 && (
            <>
              <p style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                Başlamadan önce kamera ve mikrofon izni isteyeceğiz.
              </p>
              <button
                type="button"
                onClick={handleStart}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#111',
                  color: '#fff',
                  borderRadius: 8,
                  border: 'none',
                  fontWeight: 500,
                  fontSize: '1rem',
                  cursor: 'pointer',
                }}
              >
                Mülakata başla
              </button>
            </>
          )}

          {currentIndex >= 0 && currentQuestion && (
            <>
              <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '0.5rem' }}>
                Soru {currentIndex + 1} / {total}
              </p>
              <div style={{ padding: '1rem', borderRadius: 8, background: '#f3f4f6', marginBottom: '1rem' }}>
                {currentQuestion.text}
              </div>
              <button
                type="button"
                onClick={handleNext}
                disabled={finishing}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#111',
                  color: '#fff',
                  borderRadius: 8,
                  border: 'none',
                  fontWeight: 500,
                  fontSize: '1rem',
                  cursor: finishing ? 'not-allowed' : 'pointer',
                  opacity: finishing ? 0.7 : 1,
                }}
              >
                {currentIndex === total - 1 ? 'Mülakatı bitir' : 'Sonraki soru'}
              </button>
              {finishing && (
                <p style={{ marginTop: '0.75rem', fontSize: '0.9rem', color: '#6b7280' }}>
                  Mülakat tamamlandı, sonuç sayfasına yönlendiriliyorsunuz…
                </p>
              )}
            </>
          )}

          {currentIndex >= 0 && !currentQuestion && (
            <p>Mülakat soruları yüklenemedi.</p>
          )}
        </section>
      </main>
    </div>
  )
}

