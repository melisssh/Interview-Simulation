import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'

const API = '/api'

const headerStyle = {
  background: '#fff',
  borderBottom: '1px solid #e5e7eb',
  padding: '0.75rem 1.5rem',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
}
const inputStyle = {
  display: 'block',
  width: '100%',
  padding: '0.75rem 1rem',
  marginTop: '0.375rem',
  fontSize: '1rem',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  color: '#111',
  boxSizing: 'border-box',
}
const labelStyle = { fontSize: '0.95rem', fontWeight: 500, color: '#374151' }
const primaryButtonStyle = {
  padding: '0.75rem 1.5rem',
  background: '#111',
  color: '#fff',
  borderRadius: 8,
  border: 'none',
  fontWeight: 500,
  fontSize: '1rem',
  cursor: 'pointer',
}

export default function InterviewNew() {
  const [title, setTitle] = useState('')
  const [domain, setDomain] = useState('')
  const [language, setLanguage] = useState('tr')
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    fetch(`${API}/categories`)
      .then((res) => res.json())
      .then(setCategories)
      .catch(() => setError('Kategoriler alınamadı'))
  }, [token, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API}/interviews`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title, domain, language }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Mülakat oluşturulamadı')
        return
      }
      navigate(`/interview/${data.id}`)
    } catch (err) {
      setError('Bağlantı hatası')
    } finally {
      setLoading(false)
    }
  }

  if (!token) return null

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
      <div style={{ maxWidth: 440, margin: '0 auto', padding: '3rem 1.5rem', background: '#fff', boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          Yeni mülakat
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Başlık ve kategori seçin, mülakatı başlatın.
        </p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>
            Başlık
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Örn: Backend mülakatı"
              required
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Kategori (domain)
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              required
              style={inputStyle}
            >
              <option value="">Seçin</option>
              {categories.map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name} – {c.description}
                </option>
              ))}
            </select>
          </label>
          <label style={labelStyle}>
            Dil
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              style={inputStyle}
            >
              <option value="tr">Türkçe</option>
              <option value="en">English</option>
            </select>
          </label>
          {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
          <button type="submit" disabled={loading} style={{ ...primaryButtonStyle, opacity: loading ? 0.7 : 1 }}>
            {loading ? 'Oluşturuluyor...' : 'Mülakatı başlat'}
          </button>
        </form>
      </div>
    </div>
  )
}
