import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'

const API = '/api'

export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Şifre en az 8 karakter olmalı.')
      return
    }
    setLoading(true)
    try {
      const normalizedEmail = email.trim().toLowerCase()
      const createRes = await fetch(`${API}/create-user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, password }),
      })
      const createData = await createRes.json()
      if (!createRes.ok || createData.error) {
        setError(createData.error || createData.detail || 'Kayıt başarısız')
        return
      }
      const loginRes = await fetch(`${API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail, password }),
      })
      const loginData = await loginRes.json()
      if (!loginRes.ok) {
        setError(loginData.detail || 'Kayıt oldu ama giriş yapılamadı. Giriş sayfasından deneyin.')
        return
      }
      localStorage.setItem('token', loginData.access_token)
      localStorage.setItem('user_id', String(loginData.user_id))
      localStorage.setItem('email', loginData.email)
      navigate('/profile')
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
          to="/login"
          style={{
            padding: '0.5rem 1rem',
            background: '#111',
            color: '#fff',
            borderRadius: 8,
            textDecoration: 'none',
            fontSize: '0.95rem',
          }}
        >
          Giriş yap
        </Link>
      </header>
      <div style={{ maxWidth: 400, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          Kayıt ol
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Ücretsiz hesap oluştur, mülakat simülasyonlarına başla.
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
            {loading ? 'Kaydediliyor...' : 'Kayıt ol'}
          </button>
        </form>
        <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: '#6b7280' }}>
          Zaten hesabın var mı?{' '}
          <Link to="/login" style={{ color: '#111', fontWeight: 500, textDecoration: 'underline' }}>
            Giriş yap
          </Link>
        </p>
      </div>
    </div>
  )
}
