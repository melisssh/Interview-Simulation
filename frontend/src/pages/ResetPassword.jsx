import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Header from '../components/Header'

import { API } from '../api'

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
      setError('Invalid link.')
    }
  }, [token])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!token) {
      setError('Invalid link.')
      return
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation must match.')
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
        setError(data.detail || 'Could not update password.')
        return
      }
      setMessage('Password updated. You can now log in.')
      setTimeout(() => navigate('/login'), 1500)
    } catch {
      setError('Connection error. Please try again later.')
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
      <Header links={[]} />
      <div style={{ maxWidth: 400, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem', lineHeight: 1.2 }}>
          Set new password
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Enter your new password below.
        </p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>
            New password
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={inputStyle} />
          </label>
          <label style={labelStyle}>
            Confirm new password
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={inputStyle} />
          </label>
          {message && <p style={{ color: '#059669', margin: 0, fontSize: '0.95rem' }}>{message}</p>}
          {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
          <button type="submit" disabled={loading} style={{
            padding: '0.75rem 1.5rem', background: '#111', color: '#fff', borderRadius: 8,
            border: 'none', fontWeight: 500, fontSize: '1rem',
            cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1,
          }}>
            {loading ? 'Sending...' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  )
}
