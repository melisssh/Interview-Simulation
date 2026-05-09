import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API = '/api'

const ScoreBar = ({ score, label, max = 100 }) => {
  const safeScore = Number.isFinite(Number(score)) ? Number(score) : 0
  const percentage = (safeScore / max) * 100
  let color = '#dc2626'
  if (percentage >= 80) color = '#16a34a'
  else if (percentage >= 60) color = '#f59e0b'

  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
        <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: '0.9rem', fontWeight: 600, color }}>{safeScore}/{max}</span>
      </div>
      <div style={{ width: '100%', height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${percentage}%`, height: '100%', background: color, transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}

export default function InterviewResult() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const toNumber = (value) => {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  const parseMetrics = (raw) => {
    if (!raw) return {}
    if (typeof raw === 'object') return raw
    if (typeof raw === 'string') {
      try {
        const parsed = JSON.parse(raw)
        return parsed && typeof parsed === 'object' ? parsed : {}
      } catch {
        return {}
      }
    }
    return {}
  }
  const pickMetrics = (...candidates) => {
    for (const candidate of candidates) {
      const parsed = parseMetrics(candidate)
      if (parsed && Object.keys(parsed).length > 0) return parsed
    }
    return {}
  }
  const normalizedAnalysis = analysis || (interview?.feedback
    ? {
        metrics: parseMetrics(interview.feedback.metrics_json),
        summary: interview.feedback.summary,
        strengths: interview.feedback.strengths,
        improvements: interview.feedback.improvements,
      }
    : null)
  const pickScore = (...values) => {
    for (const value of values) {
      const n = toNumber(value)
      if (n !== null) return n
    }
    return null
  }
  const averageScores = (...values) => {
    const nums = values.map((v) => toNumber(v)).filter((v) => v !== null)
    if (!nums.length) return null
    return Math.round(nums.reduce((sum, n) => sum + n, 0) / nums.length)
  }
  const metricsScores = pickMetrics(
    normalizedAnalysis?.metrics,
    normalizedAnalysis?.metrics_json,
    interview?.feedback?.metrics_json,
  )
  const metricsOverallScore = pickScore(
    metricsScores.overall_score,
    metricsScores.overall,
  )
  const metricsContentScore = averageScores(
    metricsScores.content_score,
    metricsScores.relevance_score,
    metricsScores.keyword_match_score,
    metricsScores.length,
    metricsScores.filler_usage,
  )
  const metricsSpeechScore = averageScores(
    metricsScores.speech_quality_score,
    metricsScores.speech_score,
    metricsScores.speaking_rate,
    metricsScores.pause_control,
    metricsScores.fluency_score,
    metricsScores.speech_rate_score,
  )
  const derivedContentScore = pickScore(
    normalizedAnalysis?.content_quality_score,
    metricsScores.content_quality_score,
    metricsScores.content_score,
    metricsScores.relevance_score,
    metricsScores.keyword_match_score,
    metricsContentScore,
    metricsOverallScore,
  )
  const derivedSpeechScore = pickScore(
    normalizedAnalysis?.speech_quality_score,
    metricsScores.speech_quality_score,
    metricsScores.speech_score,
    metricsSpeechScore,
    metricsOverallScore,
  )
  const derivedNonverbalScore = pickScore(
    normalizedAnalysis?.nonverbal_score,
    metricsScores.nonverbal_score,
    metricsScores.body_language_score,
    metricsScores.eye_contact_score,
    metricsScores.posture_score,
    metricsOverallScore,
  )
  const derivedOverallScore = pickScore(
    normalizedAnalysis?.overall_score,
    metricsOverallScore,
    (derivedContentScore !== null && derivedSpeechScore !== null && derivedNonverbalScore !== null)
      ? Math.round((derivedContentScore + derivedSpeechScore + derivedNonverbalScore) / 3)
      : null,
    derivedContentScore,
  ) ?? 0
  const strengthsList = normalizedAnalysis?.metrics?.strengths
    || (normalizedAnalysis?.strengths ? normalizedAnalysis.strengths.split('\n').map((s) => s.trim()).filter(Boolean) : [])
  const improvementsList = normalizedAnalysis?.metrics?.improvements
    || (normalizedAnalysis?.improvements ? normalizedAnalysis.improvements.split('\n').map((s) => s.trim()).filter(Boolean) : [])
  const contentFeedback = normalizedAnalysis?.metrics?.content_feedback
    || normalizedAnalysis?.actionable_recommendations
    || normalizedAnalysis?.summary
    || ''

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    if (!id) return
<<<<<<< Updated upstream
    fetch(`${API}/interviews/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401 || res.status === 403) navigate('/login')
        if (!res.ok) throw new Error('Mülakat alınamadı')
        return res.json()
      })
      .then((data) => {
        setInterview(data)
        if (data?.feedback) {
          setChatMessages([
            { role: 'system', text: data.feedback.summary || 'Geri bildirim hazır.' },
            ...(data.feedback.strengths ? [{ role: 'system', text: '💪 Güçlü yönler: ' + data.feedback.strengths }] : []),
            ...(data.feedback.improvements ? [{ role: 'system', text: '📈 Gelişim: ' + data.feedback.improvements }] : []),
          ])
=======

    const fetchInterviewAndAnalysis = async () => {
      try {
        const interviewRes = await fetch(`${API}/interviews/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (interviewRes.status === 401 || interviewRes.status === 403) {
          navigate('/login')
          return
        }
        if (!interviewRes.ok) throw new Error('Mülakat alınamadı')
        const interviewData = await interviewRes.json()
        if (!interviewData) return

        if (interviewData.status === 'created' || interviewData.status === 'in_progress') {
          navigate(`/interview/${id}`)
          return
        }

        setInterview(interviewData)

        const analysisRes = await fetch(`${API}/interviews/${id}/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (analysisRes.status === 404) {
          setAnalysis(null)
          return
>>>>>>> Stashed changes
        }
        if (!analysisRes.ok) throw new Error('Analiz alınamadı')
        const analysisData = await analysisRes.json()
        setAnalysis(analysisData)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchInterviewAndAnalysis()
  }, [id, token, navigate])

  useEffect(() => {
    if (!token || !id || !interview) return
    if (analysis) return
    if (interview.status !== 'analyzing') return

    const pollTimer = setInterval(async () => {
      try {
        const [interviewRes, analysisRes] = await Promise.all([
          fetch(`${API}/interviews/${id}`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API}/interviews/${id}/analysis`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ])

        if (interviewRes.ok) {
          const interviewData = await interviewRes.json()
          setInterview(interviewData)
        }

        if (analysisRes.ok) {
          const analysisData = await analysisRes.json()
          setAnalysis(analysisData)
        }
      } catch {
        // polling errors are temporary; keep current UI state
      }
    }, 4000)

    return () => clearInterval(pollTimer)
  }, [id, token, interview, analysis])

  const startAnalysis = async () => {
    setAnalyzing(true)
    setError('')
    setInterview((prev) => (prev ? { ...prev, status: 'analyzing' } : prev))
    try {
      const res = await fetch(`${API}/interviews/${id}/analyze`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json()
      if (res.ok) {
        const analysisRes = await fetch(`${API}/interviews/${id}/analysis`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (analysisRes.ok) {
          const analysisData = await analysisRes.json()
          setAnalysis(analysisData)
        } else {
          setAnalysis(null)
        }
        setInterview((prev) => (prev ? { ...prev, status: 'analyzed' } : prev))
      } else {
        setError(data.detail || 'Analiz başlatılamadı')
        setInterview((prev) => (prev ? { ...prev, status: 'analysis_failed' } : prev))
      }
    } catch (err) {
      setError('Analiz hatası: ' + err.message)
      setInterview((prev) => (prev ? { ...prev, status: 'analysis_failed' } : prev))
    } finally {
      setAnalyzing(false)
    }
  }

  const headerStyle = {
    background: '#fff',
    borderBottom: '1px solid #e5e7eb',
    padding: '0.75rem 1.5rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  }

  const cardStyle = {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 12,
    padding: '1.5rem',
    marginBottom: '1.5rem',
  }

  if (!token) return null
  if (loading)
    return (
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

  if (error && !analysis)
    return (
      <div style={{ minHeight: '100vh', background: '#fff' }}>
        <header style={headerStyle}>
          <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
            Mülakat Simülasyonu
          </Link>
          <Link to="/dashboard" style={{ fontSize: '0.95rem', color: '#374151', textDecoration: 'none' }}>
            Dashboard'a dön
          </Link>
        </header>
        <div style={{ maxWidth: 800, margin: '0 auto', padding: '3rem 1.5rem' }}>
          <div style={{ ...cardStyle, background: '#fee' }}>
            <h2 style={{ color: '#dc2626', marginTop: 0 }}>Hata</h2>
            <p>{error}</p>
            <button
              onClick={() => navigate('/dashboard')}
              style={{
                padding: '0.75rem 1.5rem',
                background: '#111',
                color: '#fff',
                borderRadius: 8,
                border: 'none',
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              Dashboard'a dön
            </button>
          </div>
        </div>
      </div>
    )

  if (!interview)
    return (
      <div style={{ minHeight: '100vh', background: '#fff' }}>
        <header style={headerStyle}>
          <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
            Mülakat Simülasyonu
          </Link>
        </header>
        <div style={{ padding: '3rem 1.5rem', color: '#dc2626', textAlign: 'center' }}>Bulunamadı</div>
      </div>
    )

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

      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>
          {interview.title} – Sonuçlar
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '2rem' }}>Analiz ve geri bildirim</p>

        {!normalizedAnalysis ? (
          <div style={cardStyle}>
            {interview.status === 'analyzing' || analyzing ? (
              <p style={{ margin: 0, color: '#666' }}>Analiz işleniyor... Birkaç saniye içinde sonuçlar otomatik yenilenecek.</p>
            ) : (
              <>
                <p style={{ margin: '0 0 1rem 0', color: '#666' }}>
                  {interview.status === 'analysis_failed'
                    ? 'Analiz sırasında hata oluştu. Tekrar deneyebilirsin.'
                    : 'Analiz henüz hazır değil. Başlatmak için butona tıkla.'}
                </p>
                <button
                  onClick={startAnalysis}
                  disabled={analyzing}
                  style={{
                    padding: '0.75rem 1.5rem',
                    background: analyzing ? '#ccc' : '#111',
                    color: '#fff',
                    borderRadius: 8,
                    border: 'none',
                    fontWeight: 500,
                    cursor: analyzing ? 'not-allowed' : 'pointer',
                  }}
                >
                  {interview.status === 'analysis_failed' ? 'Analizi Tekrar Dene' : 'Analizi Başlat'}
                </button>
              </>
            )}
          </div>
        ) : (
          <>
            {/* Overall Score */}
            <div style={cardStyle}>
              <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <div
                  style={{
                    fontSize: '3rem',
                    fontWeight: 700,
                    color: derivedOverallScore >= 80 ? '#16a34a' : derivedOverallScore >= 60 ? '#f59e0b' : '#dc2626',
                  }}
                >
                  {derivedOverallScore}
                </div>
                <p style={{ fontSize: '1.1rem', color: '#666', margin: '0.5rem 0 0 0' }}>
                  {derivedOverallScore >= 80
                    ? '🌟 Mükemmel'
                    : derivedOverallScore >= 70
                    ? '👍 İyi'
                    : derivedOverallScore >= 60
                    ? '⚠️ Orta'
                    : '❌ Gelişim gerekli'}
                </p>
              </div>

              <h3 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>Skor Dağılımı</h3>
              <ScoreBar score={derivedContentScore ?? 0} label="📝 İçerik Kalitesi (Primary)" />
              <ScoreBar score={derivedSpeechScore ?? 0} label="🎤 Konuşma Kalitesi" />
              <ScoreBar score={derivedNonverbalScore ?? 0} label="👁️ Beden Dili" />
            </div>

            {/* Strengths & Improvements */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
              <div style={cardStyle}>
                <h3 style={{ marginTop: 0, color: '#16a34a' }}>✅ Güçlü Yönler</h3>
                <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#666' }}>
                  {strengthsList.length ? (
                    strengthsList.map((strength, i) => (
                      <li key={i} style={{ marginBottom: '0.5rem' }}>
                        {strength}
                      </li>
                    ))
                  ) : (
                    <li>Güçlü yön verisi bulunamadı</li>
                  )}
                </ul>
              </div>

              <div style={cardStyle}>
                <h3 style={{ marginTop: 0, color: '#f59e0b' }}>📈 Gelişim Alanları</h3>
                <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#666' }}>
                  {improvementsList.length ? (
                    improvementsList.map((improvement, i) => (
                      <li key={i} style={{ marginBottom: '0.5rem' }}>
                        {improvement}
                      </li>
                    ))
                  ) : (
                    <li>Gelişim alanı verisi bulunamadı</li>
                  )}
                </ul>
              </div>
            </div>

            {/* Detailed Feedback */}
            <div style={cardStyle}>
              <h3 style={{ marginTop: 0 }}>📋 Detaylı Geri Bildirim</h3>

              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ color: '#374151', marginBottom: '0.5rem' }}>İçerik Kalitesi</h4>
                <p style={{ color: '#666', margin: 0, whiteSpace: 'pre-wrap' }}>
                  {contentFeedback || 'İçerik geri bildirimi bulunamadı'}
                </p>
              </div>

              {normalizedAnalysis.strengths && (
                <div style={{ marginBottom: '1.5rem', padding: '1rem', background: '#e8f5e9', borderRadius: 8 }}>
                  <h4 style={{ marginTop: 0, color: '#16a34a' }}>💪 Özet</h4>
                  <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{normalizedAnalysis.strengths}</p>
                </div>
              )}

              {normalizedAnalysis.improvements && (
                <div style={{ padding: '1rem', background: '#fff3e0', borderRadius: 8 }}>
                  <h4 style={{ marginTop: 0, color: '#f59e0b' }}>🎯 Öneriler</h4>
                  <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{normalizedAnalysis.improvements}</p>
                </div>
              )}
            </div>

            {/* Recommendation */}
            <div
              style={{
                ...cardStyle,
                background:
                  normalizedAnalysis.overall_recommendation === 'Strong Yes'
                    ? '#e8f5e9'
                    : normalizedAnalysis.overall_recommendation === 'Yes'
                    ? '#e3f2fd'
                    : normalizedAnalysis.overall_recommendation === 'Maybe'
                    ? '#fff3e0'
                    : '#fee',
                border:
                  normalizedAnalysis.overall_recommendation === 'Strong Yes'
                    ? '2px solid #16a34a'
                    : normalizedAnalysis.overall_recommendation === 'Yes'
                    ? '2px solid #2196f3'
                    : normalizedAnalysis.overall_recommendation === 'Maybe'
                    ? '2px solid #f59e0b'
                    : '2px solid #dc2626',
              }}
            >
              <h3 style={{ marginTop: 0 }}>📊 Değerlendirme Özeti</h3>
              <p style={{ margin: '0 0 1rem 0', color: '#666' }}>
                <strong>Teknik Yeterlilik:</strong> {normalizedAnalysis.technical_fit || 'Bilinmiyor'}
              </p>
              <p style={{ margin: '0 0 1rem 0', color: '#666' }}>
                <strong>Komunikasyon:</strong> {normalizedAnalysis.communication_fit || 'Bilinmiyor'}
              </p>
              <p style={{ margin: '0 0 1.5rem 0', color: '#666' }}>
                <strong>Motivasyon:</strong> {normalizedAnalysis.motivation_level || 'Bilinmiyor'}
              </p>
              <p style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
                Genel Tavsiye:{' '}
                <span
                  style={{
                    color:
                      normalizedAnalysis.overall_recommendation === 'Strong Yes'
                        ? '#16a34a'
                        : normalizedAnalysis.overall_recommendation === 'Yes'
                        ? '#2196f3'
                        : normalizedAnalysis.overall_recommendation === 'Maybe'
                        ? '#f59e0b'
                        : '#dc2626',
                  }}
                >
                  {normalizedAnalysis.overall_recommendation || 'Bilinmiyor'}
                </span>
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
