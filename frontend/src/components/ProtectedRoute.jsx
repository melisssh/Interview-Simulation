import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { API } from '../api'

export default function ProtectedRoute({ children }) {
  const [status, setStatus] = useState('checking') // checking | ok | invalid

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setStatus('invalid')
      return
    }
    fetch(`${API}/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => {
        if (r.ok) setStatus('ok')
        else {
          localStorage.removeItem('token')
          setStatus('invalid')
        }
      })
      .catch(() => {
        localStorage.removeItem('token')
        setStatus('invalid')
      })
  }, [])

  if (status === 'checking') return null
  if (status === 'invalid') return <Navigate to="/login" replace />
  return children
}
