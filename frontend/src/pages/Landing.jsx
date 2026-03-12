import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      {/* Üst bar: logo sol, Kayıt ol + Giriş yap sağ */}
      <header style={{
        padding: '1rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #e5e7eb',
      }}>
        <span style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111' }}>
          Mülakat Simülasyonu
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Link
            to="/register"
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #111',
              borderRadius: 8,
              color: '#111',
              textDecoration: 'none',
              fontSize: '0.95rem',
            }}
          >
            Kayıt ol
          </Link>
          <Link
            to="/login"
            style={{
              padding: '0.5rem 1rem',
              background: '#111',
              color: '#fff',
              borderRadius: 8,
              textDecoration: 'none',
              fontSize: '0.95rem',
            }}
          >
            Giriş yap
          </Link>
        </div>
      </header>

      {/* Ana alan: başlık + açıklama + buton */}
      <main style={{
        maxWidth: 640,
        margin: '0 auto',
        padding: '4rem 1.5rem',
        textAlign: 'center',
      }}>
        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: 700,
          color: '#111',
          marginBottom: '1rem',
          lineHeight: 1.2,
        }}>
          Mülakatınızı{' '}
          <span style={{ background: 'linear-gradient(90deg, #2563eb, #059669)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
            Geliştirin
          </span>
        </h1>
        <p style={{
          fontSize: '1.125rem',
          color: '#6b7280',
          lineHeight: 1.6,
          marginBottom: '2rem',
        }}>
          Yapay zeka destekli mülakat simülasyonu. Sorulara cevap verin, geri bildirim ve gelişim önerileri alın.
        </p>
        <Link
          to="/register"
          style={{
            display: 'inline-block',
            padding: '0.75rem 1.5rem',
            background: '#111',
            color: '#fff',
            borderRadius: 8,
            textDecoration: 'none',
            fontWeight: 500,
            fontSize: '1rem',
          }}
        >
          Başla
        </Link>
      </main>
    </div>
  )
}
