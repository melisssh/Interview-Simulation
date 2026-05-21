import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'

import { API } from '../api'

const card = {
  maxWidth: 640,
  margin: '0 auto',
  padding: '2.5rem 2rem',
  background: '#fff',
  borderRadius: 12,
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
}

const field = {
  marginBottom: '1.25rem',
}

const inputStyle = {
  display: 'block',
  width: '100%',
  padding: '0.7rem 0.9rem',
  marginTop: '0.35rem',
  fontSize: '0.95rem',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  color: '#111',
  boxSizing: 'border-box',
  outline: 'none',
}

const labelStyle = { fontSize: '0.9rem', fontWeight: 500, color: '#374151' }

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
      setPwError('Please fill in all password fields.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPwError('New password and confirmation must match.')
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
        setPwError(data.detail || 'Could not update password.')
        return
      }
      setPwMessage('Password updated.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPwError('Connection error. Could not change password.')
    } finally {
      setPwLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header />
      <div style={{ padding: '2.5rem 1.5rem' }}>
        <div style={card}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.35rem' }}>Account settings</h1>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.75rem', lineHeight: 1.5 }}>
            Login email: <strong>{email}</strong>
          </p>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#111', marginBottom: '0.75rem' }}>Change password</h2>
          <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '1.25rem' }}>For security, enter your current password first, then your new password.</p>
          <form onSubmit={handlePasswordChange}>
            <div style={field}>
              <label style={labelStyle}>Current password</label>
              <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} style={inputStyle} />
            </div>
            <div style={field}>
              <label style={labelStyle}>New password</label>
              <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={inputStyle} />
            </div>
            <div style={field}>
              <label style={labelStyle}>New password (confirm)</label>
              <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={inputStyle} />
            </div>
            {pwMessage && <p style={{ color: '#059669', margin: 0, fontSize: '0.9rem' }}>{pwMessage}</p>}
            {pwError && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{pwError}</p>}
            <button type="submit" disabled={pwLoading} style={{
              width: '100%', padding: '0.75rem', background: '#111', color: '#fff',
              borderRadius: 8, border: 'none', fontWeight: 600, fontSize: '1rem',
              cursor: 'pointer', opacity: pwLoading ? 0.7 : 1, marginTop: '0.5rem',
            }}>{pwLoading ? 'Updating password...' : 'Update password'}</button>
          </form>
        </div>
      </div>
    </div>
  )
}
