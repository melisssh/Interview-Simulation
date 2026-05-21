import { Component } from 'react'
import { Link } from 'react-router-dom'

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f9fafb' }}>
      <div style={{ maxWidth: 400, width: '100%', margin: '0 1.5rem', textAlign: 'center' }}>
        <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#fef2f2', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#111', marginBottom: '0.5rem' }}>
          Something went wrong
        </h1>
        <p style={{ fontSize: '0.95rem', color: '#6b7280', marginBottom: '1.5rem', lineHeight: 1.6 }}>
          An unexpected error occurred. Please refresh the page and try again.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <button
            onClick={() => { resetErrorBoundary(); window.location.reload() }}
            style={{ padding: '0.65rem 1.5rem', background: '#111', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 500, cursor: 'pointer', fontSize: '0.95rem' }}
          >
            Refresh
          </button>
          <Link
            to="/dashboard"
            style={{ padding: '0.65rem 1.5rem', background: '#fff', color: '#374151', border: '1px solid #d1d5db', borderRadius: 8, fontWeight: 500, textDecoration: 'none', fontSize: '0.95rem' }}
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  )
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} resetErrorBoundary={() => this.setState({ hasError: false, error: null })} />
    }
    return this.props.children
  }
}
