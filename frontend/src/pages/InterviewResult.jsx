import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API = '/api'

export default function InterviewResult() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [chatMessage, setChatMessage] = useState('')
  const [chatMessages, setChatMessages] = useState([])
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
      .then((data) => {
        setInterview(data)
        if (data?.feedback) {
          setChatMessages([
            { role: 'system', text: data.feedback.summary || 'Geri bildirim hazır.' },
            ...(data.feedback.strengths ? [{ role: 'system', text: '💪 Güçlü yönler: ' + data.feedback.strengths }] : []),
            ...(data.feedback.improvements ? [{ role: 'system', text: '📈 Gelişim: ' + data.feedback.improvements }] : []),
          ])
        }
      })
      .catch(() => setError('Yüklenemedi'))
      .finally(() => setLoading(false))
  }, [id, token, navigate])

  async function handleSendChat(e) {
    e.preventDefault()
    if (!chatMessage.trim()) return
    const userText = chatMessage.trim()
    setChatMessage('')
    setChatMessages((prev) => [...prev, { role: 'user', text: userText }])
    try {
      const res = await fetch(`${API}/interviews/${id}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userText }),
      })
      const data = await res.json()
      const reply = res.ok ? (data.reply || 'Yanıt alınamadı.') : (data.detail || 'Bir hata oluştu.')
      setChatMessages((prev) => [...prev, { role: 'system', text: reply }])
    } catch {
      setChatMessages((prev) => [...prev, { role: 'system', text: 'Bağlantı hatası. Tekrar deneyin.' }])
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

  const hasFeedback = interview.feedback && (interview.feedback.summary || interview.feedback.strengths || interview.feedback.improvements)

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
          {interview.title} – Sonuç
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>Analiz ve geri bildirim</p>

      <section style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Konuşma metni</h2>
        {interview.transcript ? (
          <div style={{ background: '#f5f5f5', padding: '1rem', borderRadius: 8, whiteSpace: 'pre-wrap', fontSize: '0.95rem' }}>
            {interview.transcript}
          </div>
        ) : (
          <p style={{ color: '#888', margin: 0, fontStyle: 'italic' }}>Analiz bekleniyor. Video yüklenip işlendikten sonra burada görünecek.</p>
        )}
      </section>

      <section style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Geri bildirim</h2>
        {hasFeedback ? (
          <div style={{ background: '#e8f5e9', padding: '1rem', borderRadius: 8, border: '1px solid #c8e6c9' }}>
            {interview.feedback.summary && <p style={{ margin: '0 0 0.5rem 0' }}><strong>Özet:</strong> {interview.feedback.summary}</p>}
            {interview.feedback.strengths && <p style={{ margin: '0 0 0.5rem 0' }}><strong>Güçlü yönler:</strong> {interview.feedback.strengths}</p>}
            {interview.feedback.improvements && <p style={{ margin: 0 }}><strong>Gelişim:</strong> {interview.feedback.improvements}</p>}
            {interview.feedback.scores_json && (
              <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#555' }}>
                Skorlar: {typeof interview.feedback.scores_json === 'string' ? interview.feedback.scores_json : JSON.stringify(interview.feedback.scores_json)}
              </p>
            )}
          </div>
        ) : (
          <p style={{ color: '#888', margin: 0, fontStyle: 'italic' }}>Analiz bekleniyor. Geri bildirim hazır olduğunda burada görünecek.</p>
        )}
      </section>

      <section style={{ borderTop: '1px solid #eee', paddingTop: '1rem' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Sohbet</h2>
        <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '0.75rem' }}>
          Geri bildirime dayalı sorularınızı yazın (örn. &quot;Bu konuda nasıl gelişebilirim?&quot;).
        </p>
        <div style={{ background: '#fafafa', border: '1px solid #eee', borderRadius: 8, padding: '0.75rem', minHeight: 120 }}>
          {chatMessages.map((m, i) => (
            <div
              key={i}
              style={{
                marginBottom: '0.5rem',
                padding: '0.5rem 0.75rem',
                borderRadius: 8,
                background: m.role === 'user' ? '#e3f2fd' : '#fff',
                marginLeft: m.role === 'user' ? '2rem' : 0,
                marginRight: m.role === 'user' ? 0 : '2rem',
              }}
            >
              {m.role === 'user' && <span style={{ fontSize: '0.85rem', color: '#666' }}>Siz: </span>}
              {m.text}
            </div>
          ))}
        </div>
        <form onSubmit={handleSendChat} style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
          <input
            type="text"
            value={chatMessage}
            onChange={(e) => setChatMessage(e.target.value)}
            placeholder="Mesajınızı yazın..."
            style={{
              flex: 1,
              padding: '0.75rem 1rem',
              fontSize: '1rem',
              border: '1px solid #e5e7eb',
              borderRadius: 8,
              color: '#111',
            }}
          />
          <button
            type="submit"
            style={{
              padding: '0.75rem 1.5rem',
              background: '#111',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontWeight: 500,
              fontSize: '1rem',
              cursor: 'pointer',
            }}
          >
            Gönder
          </button>
        </form>
      </section>
      </div>
    </div>
  )
}
