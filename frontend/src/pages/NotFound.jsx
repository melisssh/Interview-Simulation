import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#f9f9f9' }}>
      <h1 style={{ fontSize: '4rem', margin: 0, color: '#111' }}>404</h1>
      <p style={{ fontSize: '1.2rem', color: '#6b7280', marginTop: '0.5rem' }}>
        Page not found.
      </p>
      <Link to="/" style={{ marginTop: '1.5rem', color: '#111', textDecoration: 'underline' }}>
        Go home
      </Link>
    </div>
  )
}
