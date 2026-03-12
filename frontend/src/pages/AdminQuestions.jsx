import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const API = '/api'

export default function AdminQuestions() {
  const [questions, setQuestions] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [text, setText] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [language, setLanguage] = useState('tr')
  const [difficulty, setDifficulty] = useState('')

  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) return
    Promise.all([
      fetch(`${API}/categories`).then((r) => r.json()),
      fetch(`${API}/questions`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((r) => {
        if (r.status === 403) {
          throw new Error('Yalnızca adminler erişebilir.')
        }
        return r.json()
      }),
    ])
      .then(([cats, qs]) => {
        setCategories(Array.isArray(cats) ? cats : [])
        setQuestions(Array.isArray(qs) ? qs : [])
      })
      .catch((e) => setError(e.message || 'Liste alınamadı'))
      .finally(() => setLoading(false))
  }, [token])

  async function handleCreate(e) {
    e.preventDefault()
    setError('')
    if (!text || !categoryId) {
      setError('Soru metni ve kategori zorunlu.')
      return
    }
    try {
      const res = await fetch(`${API}/questions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          text,
          category_id: Number(categoryId),
          language,
          difficulty: difficulty ? Number(difficulty) : null,
          is_active: 1,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Soru eklenemedi.')
        return
      }
      setQuestions((prev) => [...prev, data])
      setText('')
      setCategoryId('')
      setDifficulty('')
    } catch {
      setError('Soru eklenemedi.')
    }
  }

  if (!token) {
    return <div style={{ padding: '2rem' }}>Önce giriş yap.</div>
  }

  if (loading) return <div style={{ padding: '2rem' }}>Yükleniyor...</div>

  if (error && questions.length === 0) {
    return <div style={{ padding: '2rem', color: '#dc2626' }}>{error}</div>
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <header style={{
        background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        padding: '0.75rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu – Admin
        </Link>
        <Link to="/dashboard" style={{ fontSize: '0.95rem', color: '#374151', textDecoration: 'none' }}>
          Dashboard'a dön
        </Link>
      </header>

      <main style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1.5rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '1.5rem', color: '#111' }}>
          Soru yönetimi
        </h1>

        <section style={{ marginBottom: '2rem', background: '#fff', padding: '1.25rem', borderRadius: 12 }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>Yeni soru ekle</h2>
          <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <label style={{ fontSize: '0.9rem' }}>
              Soru metni
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={3}
                style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
            </label>
            <label style={{ fontSize: '0.9rem' }}>
              Kategori
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', borderRadius: 8, border: '1px solid #e5e7eb' }}
              >
                <option value="">Seçin</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} – {c.description}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ fontSize: '0.9rem' }}>
              Dil
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', borderRadius: 8, border: '1px solid #e5e7eb' }}
              >
                <option value="tr">Türkçe</option>
                <option value="en">English</option>
              </select>
            </label>
            <label style={{ fontSize: '0.9rem' }}>
              Zorluk (1–5, opsiyonel)
              <input
                type="number"
                min="1"
                max="5"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                style={{ width: '100%', marginTop: '0.25rem', padding: '0.5rem', borderRadius: 8, border: '1px solid #e5e7eb' }}
              />
            </label>
            {error && (
              <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>
            )}
            <button
              type="submit"
              style={{
                marginTop: '0.5rem',
                padding: '0.75rem 1.5rem',
                background: '#111',
                color: '#fff',
                borderRadius: 8,
                border: 'none',
                fontWeight: 500,
                fontSize: '1rem',
                cursor: 'pointer',
              }}
            >
              Soru ekle
            </button>
          </form>
        </section>

        <section style={{ background: '#fff', padding: '1.25rem', borderRadius: 12 }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>Mevcut sorular</h2>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <th align="left">ID</th>
                  <th align="left">Metin</th>
                  <th align="left">Kategori</th>
                  <th align="left">Dil</th>
                  <th align="left">Zorluk</th>
                  <th align="left">Aktif</th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                    <td>{q.id}</td>
                    <td>{q.text}</td>
                    <td>{q.category_id}</td>
                    <td>{q.language}</td>
                    <td>{q.difficulty ?? '-'}</td>
                    <td>{q.is_active ? 'Evet' : 'Hayır'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

