import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'

const API = '/api'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (!token) {
      setError('Geçersiz bağlantı.')
    }
  }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!token) {
      setError('Geçersiz bağlantı.')
      return
    }
    if (newPassword.length < 8) {
      setError('Şifre en az 8 karakter olmalı.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Yeni şifre ile tekrar aynı olmalı.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Şifre güncellenemedi.')
        return
      }
      setMessage('Şifre güncellendi. Şimdi giriş yapabilirsiniz.')
      setTimeout(() => navigate('/login'), 1500)
    } catch {
      setError('Bağlantı hatası. Daha sonra tekrar deneyin.')
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
      <header
        style={{
          padding: '1rem 1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #e5e7eb',
        }}
      >
        <Link to="/" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <Link
          to="/login"
          style={{
            padding: '0.5rem 1rem',
            border: '1px solid #111',
            borderRadius: 8,
            color: '#111',
            textDecoration: 'none',
            fontSize: '0.95rem',
          }}
        >
          Giriş yap
        </Link>
      </header>
      <div style={{ maxWidth: 400, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          Yeni şifre belirle
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Aşağıya yeni şifreni yaz.
        </p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>
            Yeni şifre
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              style={inputStyle}
            />
          </label>
          <label style={labelStyle}>
            Yeni şifre (tekrar)
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={inputStyle}
            />
          </label>
          {message && (
            <p style={{ color: '#059669', margin: 0, fontSize: '0.95rem' }}>
              {message}
            </p>
          )}
          {error && (
            <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>
              {error}
            </p>
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
            {loading ? 'Gönderiliyor...' : 'Şifreyi güncelle'}
          </button>
        </form>
      </div>
    </div>
  )
}

