import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Header from '../components/Header'
import { useAuth } from '../AuthContext'
import { API } from '../api'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [needsVerification, setNeedsVerification] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { auth, login } = useAuth()

  const verifyEmailHref = email.trim()
    ? `/verify-email?email=${encodeURIComponent(email.trim().toLowerCase())}`
    : '/verify-email'

  useEffect(() => {
    if (auth) navigate('/dashboard', { replace: true })
  }, [auth, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setNeedsVerification(false)
    setLoading(true)
    try {
      const res = await fetch(`${API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        const detail = data.detail || 'Login failed'
        setError(detail)
        if (res.status === 403) setNeedsVerification(true)
        return
      }
      login(data)
      const profileRes = await fetch(`${API}/profile`, { credentials: 'include' })
      if (!profileRes.ok) {
        navigate('/dashboard')
        return
      }
      const profileData = await profileRes.json()
      if (!profileData?.full_name) {
        navigate('/profile')
        return
      }
      navigate('/dashboard')
    } catch (err) {
      setError('Connection error. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = { display: 'block', width: '100%', padding: '0.75rem 1rem', marginTop: '0.375rem', fontSize: '1rem', border: '1px solid #e5e7eb', borderRadius: 8, color: '#111', boxSizing: 'border-box' }
  const labelStyle = { fontSize: '0.95rem', fontWeight: 500, color: '#374151' }

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <Header links={[]} />
      <div style={{ maxWidth: 400, margin: '0 auto', padding: '3rem 1.5rem' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>Log in</h1>
        <p style={{ fontSize: '1rem', color: '#6b7280', marginBottom: '1.5rem' }}>Log in to your account and continue your interviews.</p>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <label style={labelStyle}>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={inputStyle} /></label>
          <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '0.85rem' }}>
            <Link to="/forgot-password" style={{ color: '#2563eb', textDecoration: 'none' }}>Forgot password?</Link>
          </div>
          <label style={labelStyle}>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={inputStyle} /></label>
          {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
          {needsVerification && (
            <p style={{ margin: 0, fontSize: '0.9rem', color: '#374151' }}>
              <Link to={verifyEmailHref} style={{ color: '#2563eb', textDecoration: 'none', fontWeight: 500 }}>
                Resend verification email
              </Link>
            </p>
          )}
          <button type="submit" disabled={loading} className="primary-btn" style={{ width: '100%' }}>{loading ? 'Logging in...' : 'Log in'}</button>
        </form>
        <p style={{ marginTop: '1.5rem', fontSize: '0.95rem', color: '#6b7280' }}>Don&apos;t have an account?{' '}
          <Link to="/register" style={{ color: '#111', fontWeight: 500, textDecoration: 'underline' }}>Sign up</Link>
        </p>
      </div>
    </div>
  )
}
