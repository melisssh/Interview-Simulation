import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import { UNIVERSITIES, filterUniversities } from '../data/universities'
import { DEPARTMENTS, filterDepartments } from '../data/departments'

import { API } from '../api'

const card = {
  maxWidth: 640,
  margin: '0 auto',
  padding: '2.5rem 2rem',
  background: '#fff',
  borderRadius: 12,
  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
}

const field = {
  marginBottom: '1.25rem',
}

const inputStyle = {
  display: 'block',
  width: '100%',
  padding: '0.7rem 0.9rem',
  marginTop: '0.35rem',
  fontSize: '0.95rem',
  border: '1px solid #e5e7eb',
  borderRadius: 8,
  color: '#111',
  boxSizing: 'border-box',
  outline: 'none',
  transition: 'border-color 0.15s',
}

const labelStyle = { fontSize: '0.9rem', fontWeight: 500, color: '#374151' }

function Autocomplete({ value, onChange, options, placeholder, moreResultsText }) {
  const [show, setShow] = useState(false)
  const [input, setInput] = useState(value)
  const ref = useRef(null)

  useEffect(() => { setInput(value) }, [value])

  const filtered = options(input)
  const items = filtered.items || []
  const hasMore = filtered.hasMore || false

  function handleClickOutside(e) {
    if (ref.current && !ref.current.contains(e.target)) setShow(false)
  }
  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <input
        type="text"
        value={input}
        onChange={(e) => { setInput(e.target.value); onChange(e.target.value); setShow(true) }}
        onFocus={() => setShow(true)}
        placeholder={placeholder}
        style={inputStyle}
      />
      {show && items.length > 0 && (
        <ul style={{
          position: 'absolute', top: '100%', left: 0, right: 0,
          maxHeight: 200, overflowY: 'auto', margin: 0, padding: 0,
          background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
          zIndex: 100, listStyle: 'none',
        }}>
          {items.map((opt) => (
            <li
              key={opt}
              onMouseDown={() => { setInput(opt); onChange(opt); setShow(false) }}
              style={{
                padding: '0.5rem 1rem', cursor: 'pointer', fontSize: '0.9rem',
                borderBottom: '1px solid #f3f4f6',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f5f5')}
              onMouseLeave={(e) => (e.currentTarget.style.background = '#fff')}
            >
              {opt}
            </li>
          ))}
          {hasMore && (
            <li style={{
              padding: '0.4rem 1rem', fontSize: '0.8rem', color: '#9ca3af',
              borderTop: '1px solid #e5e7eb', textAlign: 'center',
            }}>
              {moreResultsText}
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

export default function Profile() {
  const [full_name, setFullName] = useState('')
  const [university, setUniversity] = useState('')
  const [department, setDepartment] = useState('')
  const [class_year, setClassYear] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [cvUploading, setCvUploading] = useState(false)
  const [cvPath, setCvPath] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    fetch(`${API}/profile`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        if (res.status === 401) { navigate('/login'); return }
        return res.json()
      })
      .then((data) => {
        if (data && typeof data === 'object') {
          setFullName(data.full_name || '')
          setUniversity(data.university || '')
          setDepartment(data.department || '')
          setClassYear(data.class_year || '')
          setCvPath(data.cv_filename || '')
        }
      })
      .catch(() => setError('Failed to load profile'))
      .finally(() => setLoading(false))
  }, [token, navigate])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setMessage('')
    setSaving(true)
    try {
      const res = await fetch(`${API}/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          full_name: (full_name || '').trim(),
          university: (university || '').trim(),
          department: (department || '').trim(),
          class_year: class_year || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Failed to save')
        return
      }
      setMessage('Profile saved.')
      setTimeout(() => navigate('/dashboard'), 1000)
    } catch (err) {
      setError('Connection error')
    } finally {
      setSaving(false)
    }
  }

  async function handleCvUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setCvUploading(true)
    setError('')
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API}/profile/cv`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'CV upload failed')
        return
      }
      setMessage('CV uploaded.')
      setCvPath(data.original_name || 'cv.pdf')
    } catch (err) {
      setError('CV upload failed')
    } finally {
      setCvUploading(false)
    }
  }

  if (!token) return null
  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header />
      <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: '#6b7280' }}>Loading...</div>
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header />
      <div style={{ padding: '2.5rem 1.5rem' }}>
        <div style={card}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.35rem' }}>Profile</h1>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.75rem', lineHeight: 1.5 }}>All fields are required. You can create interviews after uploading your CV.</p>
          <form onSubmit={handleSubmit}>
            <div style={field}>
              <label style={labelStyle}>Full Name *</label>
              <input type="text" value={full_name} onChange={(e) => setFullName(e.target.value)} required placeholder="Your full name" style={inputStyle} />
            </div>
            <div style={field}>
              <label style={labelStyle}>School (university) *</label>
              <Autocomplete value={university} onChange={setUniversity} options={filterUniversities} placeholder="Type university name" moreResultsText="Type more for more results..." />
            </div>
            <div style={field}>
              <label style={labelStyle}>Department *</label>
              <Autocomplete value={department} onChange={setDepartment} options={filterDepartments} placeholder="Type department name" moreResultsText="Type more for more results..." />
            </div>
            <div style={field}>
              <label style={labelStyle}>Class *</label>
              <select value={class_year} onChange={(e) => setClassYear(e.target.value)} required style={inputStyle}>
                <option value="">Select</option>
                <option value="1">1st Year</option>
                <option value="2">2nd Year</option>
                <option value="3">3rd Year</option>
                <option value="4">4th Year</option>
                <option value="5">5th Year</option>
                <option value="6">6th Year</option>
                <option value="Graduate">Graduate</option>
                <option value="Master's Degree">Master&apos;s</option>
                <option value="PhD">PhD</option>
              </select>
            </div>
            <div style={field}>
              <label style={labelStyle}>CV (PDF) * – You need to upload a CV to create interviews.</label>
              <input type="file" accept=".pdf" onChange={handleCvUpload} disabled={cvUploading} style={inputStyle} />
              {cvUploading && <span style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem', display: 'block' }}>Uploading...</span>}
              {cvPath && !cvUploading && (
                <span style={{ fontSize: '0.85rem', color: '#059669', marginTop: '0.25rem', display: 'block' }}>
                  ✓ {cvPath}
                </span>
              )}
            </div>
            {message && <p style={{ color: '#059669', margin: 0, fontSize: '0.9rem' }}>{message}</p>}
            {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
            <button type="submit" disabled={saving} style={{
              width: '100%', padding: '0.75rem', background: '#111', color: '#fff',
              borderRadius: 8, border: 'none', fontWeight: 600, fontSize: '1rem',
              cursor: 'pointer', opacity: saving ? 0.7 : 1, marginTop: '0.5rem',
            }}>{saving ? 'Saving...' : 'Save'}</button>
          </form>
        </div>
      </div>
    </div>
  )
}
