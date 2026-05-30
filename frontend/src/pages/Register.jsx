import { useState } from 'react'
import { Link } from 'react-router-dom'
import Header from '../components/Header'

import { API } from '../api'

export default function Register() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [registered, setRegistered] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
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
        setError(createData.error || createData.detail || 'Registration failed')
        return
      }
      setRegistered(true)
    } catch (err) {
      setError('Connection error. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = { display: 'block', width: '100%', padding: '0.75rem 1rem', marginTop: '0.375rem', fontSize: '1rem', border: '1px solid #e5e7eb', borderRadius: 8, color: '#111', boxSizing: 'border-box' }
  const labelStyle = { fontSize: '0.95rem', fontWeight: 500, color: '#374151' }

  if (registered) {
    return (
      <div style={{ minHeight: '100vh', background: '#fff' }}>
      <Header links={[]} />
        <div style={{ maxWidth: 440, margin: '0 auto', padding: '4rem 1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✉️</div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>
            Verification email sent
          </h1>
          <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1rem' }}>
            <strong>{email}</strong> We sent a verification link to your address.
          </p>
          <p style={{ fontSize: '0.95rem', color: '#6b7280', marginBottom: '1rem' }}>
            Check your inbox and click the link to verify your account. The link is valid for 5 minutes.
          </p>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '2rem' }}>
            Didn&apos;t receive it?{' '}
            <Link
              to={`/verify-email?email=${encodeURIComponent(email.trim().toLowerCase())}`}
              style={{ color: '#2563eb', textDecoration: 'none', fontWeight: 500 }}
            >
              Resend verification email
            </Link>
          </p>
          <Link to="/login" style={{
            display: 'inline-block', padding: '0.75rem 1.5rem', background: '#111', color: '#fff',
            borderRadius: 8, textDecoration: 'none', fontWeight: 500, fontSize: '1rem',
          }}>Back to login</Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <Header links={[]} />
      <div style={{ maxWidth: 400, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>Sign up</h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem' }}>Set an email and password to create an account.</p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={inputStyle} /></label>
          <label style={labelStyle}>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={inputStyle} /></label>
          {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
          <button type="submit" disabled={loading} className="primary-btn" style={{ width: '100%' }}>{loading ? 'Creating account...' : 'Sign up'}</button>
        </form>
        <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: '#6b7280' }}>Already have an account?{' '}
          <Link to="/login" style={{ color: '#111', fontWeight: 500, textDecoration: 'underline' }}>Log in</Link>
        </p>
      </div>
    </div>
  )
}
