import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'

const API = '/api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Giriş başarısız')
        return
      }
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user_id', String(data.user_id))
      localStorage.setItem('email', data.email)
      if (typeof data.is_admin !== 'undefined') {
        localStorage.setItem('is_admin', String(data.is_admin))
      } else {
        localStorage.removeItem('is_admin')
      }
      // Profil dolu mu kontrol et; boşsa önce profile yönlendir (zorunlu doldurma)
      const profileRes = await fetch(`${API}/profile`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      const profileData = await profileRes.json()
      if (!profileData?.full_name) {
        navigate('/profile')
        return
      }
      navigate('/dashboard')
    } catch (err) {
      setError('Bağlantı hatası. Backend çalışıyor mu?')
    } finally {
      setLoading(false)
    }
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

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <header style={{
        padding: '1rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #e5e7eb',
      }}>
        <Link to="/" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <Link
          to="/register"
          style={{
            padding: '0.5rem 1rem',
            border: '1px solid #111',
            borderRadius: 8,
            color: '#111',
            textDecoration: 'none',
            fontSize: '0.95rem',
          }}
        >
          Kayıt ol
        </Link>
      </header>
      <div style={{ maxWidth: 400, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          Giriş yap
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Hesabına giriş yapıp mülakatlarına devam et.
        </p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={inputStyle}
            />
          </label>
          <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '0.85rem' }}>
            <Link to="/forgot-password" style={{ color: '#2563eb', textDecoration: 'none' }}>
              Şifreni mi unuttun?
            </Link>
          </div>
          <label style={labelStyle}>
            Şifre
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={inputStyle}
            />
          </label>
          {error && (
            <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '0.75rem 1.5rem',
              background: '#111',
              color: '#fff',
              borderRadius: 8,
              border: 'none',
              fontWeight: 500,
              fontSize: '1rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Giriş yapılıyor...' : 'Giriş yap'}
          </button>
        </form>
        <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: '#6b7280' }}>
          Hesabın yoksa{' '}
          <Link to="/register" style={{ color: '#111', fontWeight: 500, textDecoration: 'underline' }}>
            Kayıt ol
          </Link>
        </p>
      </div>
    </div>
  )
}
