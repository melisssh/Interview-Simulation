import { useState, useEffect } from 'react'
import { useSearchParams, Link, useNavigate } from 'react-router-dom'
import Header from '../components/Header'

import { API } from '../api'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [resendEmail, setResendEmail] = useState('')
  const [resendMsg, setResendMsg] = useState('')

  const token = searchParams.get('token')

  useEffect(() => {
    if (!token) {
      setStatus('idle')
      return
    }
    fetch(`${API}/verify-email`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}))
        if (res.ok) {
          setStatus('success')
          setMessage(data.detail || 'Email verified successfully.')
        } else {
          setStatus('error')
          setMessage(data.detail || 'Verification failed.')
        }
      })
      .catch(() => {
        setStatus('error')
        setMessage('Connection error.')
      })
  }, [token])

  async function handleResend(e) {
    e.preventDefault()
    setResendMsg('')
    try {
      const res = await fetch(`${API}/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resendEmail.trim().toLowerCase() }),
      })
      const data = await res.json()
      setResendMsg(data.detail || 'Verification link sent.')
    } catch {
      setResendMsg('Connection error.')
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <Header links={[]} />
      <div style={{ maxWidth: 440, margin: '0 auto', padding: '4rem 1.5rem', textAlign: 'center' }}>
        {status === 'loading' && (
          <div>
            <p style={{ fontSize: '1.2rem', color: '#6b7280' }}>Verifying email...</p>
          </div>
        )}
        {status === 'success' && (
          <div>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✓</div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>Email verified</h1>
            <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '2rem' }}>{message}</p>
            <Link to="/login" style={{
              display: 'inline-block', padding: '0.75rem 1.5rem', background: '#111', color: '#fff',
              borderRadius: 8, textDecoration: 'none', fontWeight: 500, fontSize: '1rem',
            }}>Log in</Link>
          </div>
        )}
        {status === 'error' && (
          <div>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✕</div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>Verification failed</h1>
            <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1rem' }}>{message}</p>
            {message.includes('expired') && (
              <div style={{ marginTop: '2rem', textAlign: 'left' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>Get a new verification link</h3>
                <form onSubmit={handleResend} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <input
                    type="email"
                    value={resendEmail}
                    onChange={(e) => setResendEmail(e.target.value)}
                    required
                    placeholder="Your email address"
                    style={{
                      display: 'block', width: '100%', padding: '0.75rem 1rem', fontSize: '1rem',
                      border: '1px solid #e5e7eb', borderRadius: 8, color: '#111', boxSizing: 'border-box',
                    }}
                  />
                  <button type="submit" style={{
                    padding: '0.75rem 1.5rem', background: '#111', color: '#fff', borderRadius: 8,
                    border: 'none', fontWeight: 500, fontSize: '1rem', cursor: 'pointer',
                  }}>Resend</button>
                </form>
                {resendMsg && <p style={{ color: '#059669', marginTop: '0.5rem', fontSize: '0.9rem' }}>{resendMsg}</p>}
              </div>
            )}
            <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: '#6b7280' }}>
              <Link to="/login" style={{ color: '#111', fontWeight: 500, textDecoration: 'underline' }}>
                Back to login
              </Link>
            </p>
          </div>
        )}
        {status === 'idle' && (
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>Get a new verification link</h1>
            <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '2rem' }}>Enter your registered email address.</p>
            <form onSubmit={handleResend} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: 340, margin: '0 auto' }}>
              <input
                type="email"
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                required
                placeholder="Your email address"
                style={{
                  display: 'block', width: '100%', padding: '0.75rem 1rem', fontSize: '1rem',
                  border: '1px solid #e5e7eb', borderRadius: 8, color: '#111', boxSizing: 'border-box',
                }}
              />
              <button type="submit" style={{
                padding: '0.75rem 1.5rem', background: '#111', color: '#fff', borderRadius: 8,
                border: 'none', fontWeight: 500, fontSize: '1rem', cursor: 'pointer',
              }}>Send verification link</button>
            </form>
            {resendMsg && <p style={{ color: '#059669', marginTop: '0.5rem', fontSize: '0.9rem' }}>{resendMsg}</p>}
          </div>
        )}
      </div>
    </div>
  )
}
