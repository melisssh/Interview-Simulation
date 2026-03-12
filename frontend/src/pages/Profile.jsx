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

export default function Profile() {
  const [full_name, setFullName] = useState('')
  const [university, setUniversity] = useState('')
  const [department, setDepartment] = useState('')
  const [class_year, setClassYear] = useState('')
  const [cvFile, setCvFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [cvUploading, setCvUploading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    fetch(`${API}/profile`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (res.status === 401) { navigate('/login'); return }
        return res.json()
      })
      .then((data) => {
        if (data && typeof data === 'object') {
          setFullName(data.full_name || '')
          setUniversity(data.university || '')
          setDepartment(data.department || '')
          setClassYear(data.class_year || '')
        }
      })
      .catch(() => setError('Profil yüklenemedi'))
      .finally(() => setLoading(false))
  }, [token, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setSaving(true)
    try {
      const res = await fetch(`${API}/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          full_name: full_name || null,
          university: university || null,
          department: department || null,
          class_year: class_year || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Kaydedilemedi')
        return
      }
      setMessage('Profil kaydedildi.')
      setTimeout(() => navigate('/dashboard'), 1000)
    } catch (err) {
      setError('Bağlantı hatası')
    } finally {
      setSaving(false)
    }
  }

  async function handleCvUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setCvUploading(true)
    setError('')
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API}/profile/cv`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'CV yüklenemedi')
        return
      }
      setMessage('CV yüklendi.')
    } catch (err) {
      setError('CV yüklenemedi')
    } finally {
      setCvUploading(false)
    }
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
      <div style={{ maxWidth: 500, margin: '0 auto', padding: '3rem 1.5rem', background: '#fff', minHeight: 'calc(100vh - 57px)', boxSizing: 'border-box' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          Profil
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Bu bilgiler mülakat sorularına katkı sağlar. Kayıt sonrası profili doldurmanız gerekir.
        </p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>
            Ad Soyad *
            <input
              type="text"
              value={full_name}
              onChange={(e) => setFullName(e.target.value)}
              required
              placeholder="Adınız soyadınız"
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Üniversite
            <input
              type="text"
              value={university}
              onChange={(e) => setUniversity(e.target.value)}
              placeholder="Üniversite adı"
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Bölüm
            <input
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              placeholder="Bölüm"
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Sınıf
            <input
              type="text"
              value={class_year}
              onChange={(e) => setClassYear(e.target.value)}
              placeholder="Örn. 3, 4. sınıf"
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            CV (PDF veya dosya)
            <input
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={handleCvUpload}
              disabled={cvUploading}
              style={inputStyle}
            />
            {cvUploading && <span style={{ fontSize: '0.9rem', color: '#6b7280', marginTop: '0.25rem', display: 'block' }}>Yükleniyor...</span>}
          </label>
          {message && <p style={{ color: '#059669', margin: 0, fontSize: '0.95rem' }}>{message}</p>}
          {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
          <button type="submit" disabled={saving} style={{ ...primaryButtonStyle, opacity: saving ? 0.7 : 1 }}>
            {saving ? 'Kaydediliyor...' : 'Kaydet'}
          </button>
        </form>
      </div>
    </div>
  )
}
