import { Routes, Route } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import InterviewNew from './pages/InterviewNew'
import Profile from './pages/Profile'
import Account from './pages/Account'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import AdminQuestions from './pages/AdminQuestions'
import InterviewDetail from './pages/InterviewDetail'
import InterviewResult from './pages/InterviewResult'
import InterviewRun from './pages/InterviewRun'

export default function App() {
  return (
    <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/interview/new" element={<InterviewNew />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/account" element={<Account />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/admin/sorular" element={<AdminQuestions />} />
        <Route path="/interview/:id/run" element={<InterviewRun />} />
        <Route path="/interview/:id" element={<InterviewDetail />} />
        <Route path="/interview/:id/sonuc" element={<InterviewResult />} />
        <Route path="/" element={<Landing />} />
    </Routes>
  )
}
