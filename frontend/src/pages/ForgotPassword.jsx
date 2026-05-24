import { useState } from 'react'
import Header from '../components/Header'

import { API } from '../api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const res = await fetch(`${API}/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok && data.detail) {
        setError(data.detail)
      } else {
        setMessage('If an account exists with this email, we have sent a password reset link.')
      }
    } catch {
      setError('Could not send request. Please try again later.')
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
          Forgot your password?
        </h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.5 }}>
          Enter the email you used to register. We will send a password reset link.
        </p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={inputStyle} />
          </label>
          {message && <p style={{ color: '#059669', margin: 0, fontSize: '0.95rem' }}>{message}</p>}
          {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
          <button type="submit" disabled={loading} className="primary-btn" style={{ width: '100%' }}>
            {loading ? 'Sending...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  )
}
