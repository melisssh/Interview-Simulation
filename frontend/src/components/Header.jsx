import { Link, useNavigate, useLocation } from 'react-router-dom'

const styles = {
  header: {
    background: '#fff',
    borderBottom: '1px solid #e5e7eb',
    padding: '0.75rem 1.5rem',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    position: 'sticky',
    top: 0,
    zIndex: 50,
  },
  logo: { fontSize: '1.25rem', fontWeight: 700, color: '#111', textDecoration: 'none' },
  right: { display: 'flex', alignItems: 'center', gap: '0.75rem' },
  langBtn: {
    padding: '0.4rem 0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: 6,
    background: '#fff',
    color: '#374151',
    fontSize: '0.85rem',
    fontWeight: 500,
    cursor: 'pointer',
  },
  link: { color: '#374151', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 500 },
  linkActive: { color: '#111', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 600 },
}

export default function Header({ links }) {
  const navigate = useNavigate()
  const location = useLocation()
  const isLoggedIn = !!localStorage.getItem('token')

  function handleLogout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('email')
    localStorage.removeItem('is_admin')
    navigate('/login')
  }

  return (
    <header style={styles.header}>
      {isLoggedIn ? (
        <span style={styles.logo}>Interview Simulation</span>
      ) : (
        <Link to="/" style={styles.logo}>Interview Simulation</Link>
      )}
      <div style={styles.right}>
        {links && links.map((link) => (
          <Link key={link.to} to={link.to} style={link.active ? styles.linkActive : styles.link}>
            {link.label}
          </Link>
        ))}
        {!links && (
          <>
            <Link to="/dashboard" style={location.pathname === '/dashboard' ? styles.linkActive : styles.link}>Dashboard</Link>
            <Link to="/profile" style={location.pathname === '/profile' ? styles.linkActive : styles.link}>Profile</Link>
            <Link to="/account" style={location.pathname === '/account' ? styles.linkActive : styles.link}>Account</Link>
          </>
        )}
        {isLoggedIn && (
          <button onClick={handleLogout} style={{ ...styles.langBtn, borderColor: '#ef4444', color: '#ef4444' }}>
            Logout
          </button>
        )}
        {!isLoggedIn && (
          <>
            <Link to="/login" style={styles.link}>Log In</Link>
            <Link to="/register" style={{ ...styles.link, background: '#111', color: '#fff', padding: '0.4rem 0.75rem', borderRadius: 6 }}>Sign Up</Link>
          </>
        )}
      </div>
    </header>
  )
}
