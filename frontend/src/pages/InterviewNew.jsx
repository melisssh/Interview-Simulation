import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from '../components/Header'

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
}

const labelStyle = { fontSize: '0.9rem', fontWeight: 500, color: '#374151' }
const DOMAIN_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'technical', label: 'Technical' },
]

export default function InterviewNew() {
  const [title, setTitle] = useState('')
  const [domain, setDomain] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [departmentName, setDepartmentName] = useState('')
  const [position, setPosition] = useState('')
  const [sector, setSector] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    const finalSector = (sector || '').trim()
    const finalCompany = (companyName || '').trim()
    const finalDepartment = (departmentName || '').trim()
    const finalPosition = (position || '').trim()
    const finalTitle = (title || '').trim()

    if (!finalTitle) {
      setError('Title is required.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API}/interviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title: finalTitle,
          domain,
          company_name: finalCompany,
          department_name: finalDepartment,
          position: finalPosition,
          sector: finalSector,
        }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Could not create interview'); return }
      navigate('/dashboard')
    } catch (err) { setError('Connection error') }
    finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header />
      <div style={{ padding: '2.5rem 1.5rem' }}>
        <div style={card}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#111', marginBottom: '0.35rem' }}>New interview</h1>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.75rem', lineHeight: 1.5 }}>Enter title, category and company info.</p>
          <form onSubmit={handleSubmit}>
            <div style={field}>
              <label style={labelStyle}>Title</label>
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Backend interview" required style={inputStyle} />
            </div>
            <div style={field}>
              <label style={labelStyle}>Category (domain)</label>
              <select value={domain} onChange={(e) => setDomain(e.target.value)} required style={inputStyle}>
                <option value="">Select</option>
                {DOMAIN_OPTIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
            <div style={field}>
              <label style={labelStyle}>Company name *</label>
              <input type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="e.g. ABC Technology" required style={inputStyle} />
            </div>
            <div style={field}>
              <label style={labelStyle}>Sector *</label>
              <select value={sector} onChange={(e) => setSector(e.target.value)} required style={inputStyle}>
                <option value="">Select</option>
                <option value="Technology / Software">Technology / Software</option>
                <option value="Finance / Banking">Finance / Banking</option>
                <option value="Healthcare / Medical">Healthcare / Medical</option>
                <option value="Education / Academia">Education / Academia</option>
                <option value="Marketing / Advertising">Marketing / Advertising</option>
                <option value="Legal / Law">Legal / Law</option>
                <option value="Engineering / Manufacturing">Engineering / Manufacturing</option>
                <option value="Retail / E-commerce">Retail / E-commerce</option>
                <option value="Consulting / HR">Consulting / HR</option>
                <option value="Media / Communications">Media / Communications</option>
                <option value="Logistics / Transportation">Logistics / Transportation</option>
                <option value="Public / Government">Public / Government</option>
                <option value="Energy / Environment">Energy / Environment</option>
                <option value="Real Estate / Construction">Real Estate / Construction</option>
                <option value="Telecommunications">Telecommunications</option>
                <option value="Tourism / Hospitality">Tourism / Hospitality</option>
                <option value="Defense / Aerospace">Defense / Aerospace</option>
                <option value="Pharmaceuticals / Biotech">Pharmaceuticals / Biotech</option>
                <option value="Automotive / Transportation">Automotive / Transportation</option>
              </select>
            </div>
            <div style={field}>
              <label style={labelStyle}>Department name *</label>
              <input type="text" value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} placeholder="e.g. Software Development" required style={inputStyle} />
            </div>
            <div style={field}>
              <label style={labelStyle}>Position (applied role) *</label>
              <input type="text" value={position} onChange={(e) => setPosition(e.target.value)} placeholder="e.g. Backend Developer" required style={inputStyle} />
            </div>
            {error && <p style={{ color: '#dc2626', margin: 0, fontSize: '0.9rem' }}>{error}</p>}
            <button type="submit" disabled={loading} style={{
              width: '100%', padding: '0.75rem', background: '#111', color: '#fff',
              borderRadius: 8, border: 'none', fontWeight: 600, fontSize: '1rem',
              cursor: 'pointer', opacity: loading ? 0.7 : 1, marginTop: '0.5rem',
            }}>{loading ? 'Creating...' : 'Start interview'}</button>
          </form>
        </div>
      </div>
    </div>
  )
}
