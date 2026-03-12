import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

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

export default function Account() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pwMessage, setPwMessage] = useState('')
  const [pwError, setPwError] = useState('')
  const [pwLoading, setPwLoading] = useState(false)

  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const email = localStorage.getItem('email') || ''

  if (!token) {
    navigate('/login')
    return null
  }

  async function handlePasswordChange(e) {
    e.preventDefault()
    setPwError('')
    setPwMessage('')
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPwError('Lütfen tüm şifre alanlarını doldurun.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPwError('Yeni şifre ile tekrar aynı olmalı.')
      return
    }
    setPwLoading(true)
    try {
      const res = await fetch(`${API}/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setPwError(data.detail || 'Şifre güncellenemedi.')
        return
      }
      setPwMessage('Şifre güncellendi.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPwError('Bağlantı hatası. Şifre değiştirilemedi.')
    } finally {
      setPwLoading(false)
    }
  }

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
          Hesap ayarları
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1rem', lineHeight: 1.5 }}>
          Giriş email'iniz: <strong>{email}</strong>
        </p>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', marginBottom: '0.75rem' }}>
          Şifre değiştir
        </h2>
        <p style={{ fontSize: '0.95rem', color: '#6b7280', marginBottom: '1rem' }}>
          Güvenlik için önce mevcut şifrenizi, sonra yeni şifrenizi girin.
        </p>
        <form onSubmit={handlePasswordChange} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          <label style={labelStyle}>
            Mevcut şifre
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              style={inputStyle}
            />
          </label>
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
          {pwMessage && <p style={{ color: '#059669', margin: 0, fontSize: '0.95rem' }}>{pwMessage}</p>}
          {pwError && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{pwError}</p>}
          <button
            type="submit"
            disabled={pwLoading}
            style={{ ...primaryButtonStyle, opacity: pwLoading ? 0.7 : 1 }}
          >
            {pwLoading ? 'Şifre güncelleniyor...' : 'Şifreyi güncelle'}
          </button>
        </form>
      </div>
    </div>
  )
}


