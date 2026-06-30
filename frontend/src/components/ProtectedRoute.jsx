import { Navigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'

export default function ProtectedRoute({ children }) {
  const { auth, checking } = useAuth()
  if (checking) return null
  if (!auth) return <Navigate to="/login" replace />
  return children
}
