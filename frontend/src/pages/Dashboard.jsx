import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const API = '/api'

export default function Dashboard() {
  const [interviews, setInterviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const email = localStorage.getItem('email') || ''
  const isAdmin = localStorage.getItem('is_admin') === '1'

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    fetch(`${API}/profile`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((profile) => {
        if (!profile?.full_name) {
          navigate('/profile')
          return
        }
        return fetch(`${API}/interviews`, { headers: { Authorization: `Bearer ${token}` } })
      })
      .then((res) => {
        if (!res || !res.json) return
        if (res.status === 401) { navigate('/login'); return }
        return res.json()
      })
      .then((data) => {
        if (Array.isArray(data)) setInterviews(data)
      })
      .catch(() => setError('Liste alınamadı'))
      .finally(() => setLoading(false))
  }, [token, navigate])

  if (!token) return null

  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    const d = new Date(dateStr)
    return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Bu mülakatı silmek istediğine emin misin?')) return
    try {
      const res = await fetch(`${API}/interviews/${id}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        // Basit hata mesajı
        setError(data.detail || 'Mülakat silinemedi')
        return
      }
      setInterviews((prev) => prev.filter((item) => item.id !== id))
    } catch {
      setError('Mülakat silinirken hata oluştu')
    }
  }

  const userInitial = (email && email[0]) ? email[0].toUpperCase() : 'K'

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('email')
    navigate('/')
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      {/* Üst bar: logo sol, profil sağ */}
      <header style={{
        background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        padding: '0.75rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {isAdmin && (
            <Link to="/admin/sorular" style={{ textDecoration: 'none', color: '#374151', fontSize: '0.9rem' }}>
              Admin
            </Link>
          )}
          <Link to="/profile" style={{ textDecoration: 'none', color: '#374151', fontSize: '0.9rem' }}>Profil</Link>
          <button
            type="button"
            onClick={logout}
            style={{
              padding: '0.35rem 0.75rem',
              border: '1px solid #e5e7eb',
              borderRadius: 8,
              background: '#fff',
              color: '#374151',
              fontSize: '0.9rem',
              cursor: 'pointer',
            }}
          >
            Çıkış
          </button>
          <Link
            to="/account"
            style={{
              width: 36,
              height: 36,
              borderRadius: '50%',
              background: '#2563eb',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 600,
              textDecoration: 'none',
            }}
            title={email}
          >
            {userInitial}
          </Link>
        </div>
      </header>

      {/* İkinci bar: filtre + sıralama + Yeni oluştur */}
      <div style={{
        background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        padding: '0.75rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ padding: '0.35rem 0.75rem', borderRadius: 999, background: '#e5e7eb', fontWeight: 500, fontSize: '0.9rem' }}>
            Mülakatlarım
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>En yeni</span>
          <Link
            to="/interview/new"
            style={{
              padding: '0.5rem 1rem',
              background: '#111',
              color: '#fff',
              textDecoration: 'none',
              borderRadius: 8,
              fontWeight: 500,
              fontSize: '0.9rem',
            }}
          >
            + Yeni oluştur
          </Link>
        </div>
      </div>

      {/* Ana içerik: başlık + kart grid */}
      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '1.5rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '1.25rem', color: '#111' }}>
          Mülakatlarım
        </h1>

        {loading && <p style={{ color: '#6b7280' }}>Yükleniyor...</p>}
        {error && <p style={{ color: '#dc2626' }}>{error}</p>}

        {!loading && !error && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: '1rem',
          }}>
            {/* İlk kart: Yeni mülakat oluştur */}
            <Link
              to="/interview/new"
              style={{
                border: '2px dashed #d1d5db',
                borderRadius: 12,
                padding: '1.5rem',
                minHeight: 160,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#fff',
                textDecoration: 'none',
                color: '#6b7280',
                transition: 'border-color 0.2s',
              }}
              onMouseOver={(e) => { e.currentTarget.style.borderColor = '#9ca3af'; e.currentTarget.style.color = '#374151'; }}
              onMouseOut={(e) => { e.currentTarget.style.borderColor = '#d1d5db'; e.currentTarget.style.color = '#6b7280'; }}
            >
              <span style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>+</span>
              <span style={{ fontWeight: 500 }}>Yeni mülakat oluştur</span>
            </Link>

            {interviews.map((i) => (
              <div
                key={i.id}
                style={{
                  background: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: 12,
                  padding: '1.25rem',
                  minHeight: 160,
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                }}
              >
                <button
                  type="button"
                  onClick={() => handleDelete(i.id)}
                  style={{
                    position: 'absolute',
                    top: 8,
                    right: 8,
                    border: 'none',
                    background: 'transparent',
                    color: '#9ca3af',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                  }}
                  title="Mülakatı sil"
                >
                  Sil
                </button>
                <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '0.25rem' }}>
                  {formatDate(i.created_at)}
                </div>
                <Link
                  to={`/interview/${i.id}/sonuc`}
                  style={{
                    fontWeight: 600,
                    fontSize: '1rem',
                    color: '#111',
                    textDecoration: 'none',
                    marginBottom: '0.5rem',
                  }}
                >
                  {i.title || 'İsimsiz mülakat'}
                </Link>
                <div style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 'auto' }}>
                  {i.domain} · {i.language} · {i.status}
                </div>
                <div style={{ marginTop: '0.75rem' }}>
                  <Link to={`/interview/${i.id}/sonuc`} style={{ fontSize: '0.85rem', color: '#2563eb', textDecoration: 'none' }}>Sonuça git →</Link>
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && !error && interviews.length === 0 && (
          <p style={{ color: '#6b7280', marginTop: '1rem' }}>Henüz mülakat yok. &quot;Yeni mülakat oluştur&quot; kartına tıklayın.</p>
        )}
      </main>
    </div>
  )
}
