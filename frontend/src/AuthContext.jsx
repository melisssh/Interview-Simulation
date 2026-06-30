import { createContext, useContext, useState, useEffect } from 'react'
import { API } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(null) // null = checking, false = not logged in, { token, email, userId } = logged in
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    // On mount, validate cookie with /me and get a fresh token for WebSocket use
    fetch(`${API}/me`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.id) {
          setAuth({ token: data.access_token, email: data.email, userId: data.id })
        } else {
          setAuth(false)
        }
      })
      .catch(() => setAuth(false))
      .finally(() => setChecking(false))
  }, [])

  function login(data) {
    setAuth({ token: data.access_token, email: data.email, userId: data.user_id })
  }

  function logout() {
    fetch(`${API}/logout`, { method: 'POST', credentials: 'include' }).catch(() => {})
    setAuth(false)
  }

  return (
    <AuthContext.Provider value={{ auth, checking, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
