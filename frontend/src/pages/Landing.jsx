import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Header from '../components/Header'
import { useAuth } from '../AuthContext'

const styles = {
  hero: {
    maxWidth: 720,
    margin: '0 auto',
    padding: '5rem 1.5rem 4rem',
    textAlign: 'center',
  },
  badge: {
    display: 'inline-block',
    padding: '0.35rem 0.85rem',
    background: '#eff6ff',
    color: '#2563eb',
    borderRadius: 20,
    fontSize: '0.85rem',
    fontWeight: 500,
    marginBottom: '1.5rem',
  },
  heroTitle: {
    fontSize: 'clamp(2rem, 5vw, 3.25rem)',
    fontWeight: 800,
    color: '#111',
    lineHeight: 1.1,
    marginBottom: '1.25rem',
    letterSpacing: '-0.02em',
  },
  heroSubtitle: {
    fontSize: '1.15rem',
    color: '#6b7280',
    lineHeight: 1.6,
    marginBottom: '2.5rem',
    maxWidth: 560,
    marginLeft: 'auto',
    marginRight: 'auto',
  },
  heroFeatures: {
    display: 'flex',
    justifyContent: 'center',
    gap: '2rem',
    marginTop: '2rem',
    flexWrap: 'wrap',
  },
  heroFeature: {
    fontSize: '0.9rem',
    color: '#4b5563',
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
  },
  section: {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '4rem 1.5rem',
  },
  sectionTitle: {
    fontSize: '1.75rem',
    fontWeight: 700,
    color: '#111',
    textAlign: 'center',
    marginBottom: '3rem',
    letterSpacing: '-0.01em',
  },
  steps: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '1.25rem',
    alignItems: 'stretch',
  },
  stepNum: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    background: '#111',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '0.9rem',
    fontWeight: 700,
    marginBottom: '1rem',
  },
  stepTitle: {
    fontSize: '1.1rem',
    fontWeight: 600,
    color: '#111',
    marginBottom: '0.5rem',
  },
  stepDesc: {
    fontSize: '0.95rem',
    color: '#6b7280',
    lineHeight: 1.5,
  },
  featureCard: {
    padding: '1.5rem',
    borderRadius: 12,
    border: '1px solid #e5e7eb',
    transition: 'box-shadow 0.15s',
  },
  featureTitle: {
    fontSize: '1.05rem',
    fontWeight: 600,
    color: '#111',
    marginBottom: '0.4rem',
  },
  featureDesc: {
    fontSize: '0.9rem',
    color: '#6b7280',
    lineHeight: 1.5,
  },
  ctaSection: {
    textAlign: 'center',
    padding: '5rem 1.5rem',
    background: '#f9fafb',
    borderTop: '1px solid #e5e7eb',
  },
  ctaTitle: {
    fontSize: '2rem',
    fontWeight: 700,
    color: '#111',
    marginBottom: '0.75rem',
  },
  ctaSubtitle: {
    fontSize: '1.05rem',
    color: '#6b7280',
    marginBottom: '2rem',
  },
  footer: {
    padding: '2rem 1.5rem',
    textAlign: 'center',
    borderTop: '1px solid #e5e7eb',
    color: '#9ca3af',
    fontSize: '0.85rem',
  },
  footerLinks: {
    marginTop: '0.75rem',
    display: 'flex',
    justifyContent: 'center',
    gap: '1.5rem',
  },
  footerLink: {
    color: '#6b7280',
    textDecoration: 'none',
    fontSize: '0.85rem',
  },
}

export default function Landing() {
  const navigate = useNavigate()
  const { auth } = useAuth()

  useEffect(() => {
    if (auth) navigate('/dashboard', { replace: true })
  }, [auth, navigate])

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <Header links={[]} />

      {/* Hero */}
      <section style={styles.hero}>
        <span style={styles.badge}>
          🎥 AI-Powered Video Interview Simulation
        </span>
        <h1 style={styles.heroTitle}>
          Practice Job Interviews with a Real-Time AI Interviewer
        </h1>
        <p style={styles.heroSubtitle}>
          Practice video interviews with an AI interviewer — tailored to your target company and role.
        </p>
        <Link to="/register" className="landing-btn">
          Start Practicing — It&apos;s Free
        </Link>
        <div style={styles.heroFeatures}>
          {[
            ['🎥', 'Live video interviews'],
            ['🏢', 'Company-specific questions'],
            ['🔒', 'Runs locally — no cloud AI'],
          ].map(([icon, text], i) => (
            <span key={i} style={styles.heroFeature}>{icon} {text}</span>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>
          How It Works
        </h2>
        <div style={styles.steps}>
          {[
            { num: '1', title: 'Register & Upload CV', desc: 'Create an account with your email, verify it, and upload your CV as PDF. Set up your university and department info.' },
            { num: '2', title: 'Create an Interview', desc: 'Enter your target company, department, position, and sector. The AI researches the company and prepares a category structure before the interview starts.' },
            { num: '3', title: 'Run the Live Interview', desc: 'Answer the AI\'s questions on camera. Each question is generated for you specifically.' },
            { num: '4', title: 'Review Your Results', desc: 'Get scores, strengths, and improvement suggestions based on your session.' },
          ].map((step) => (
            <div key={step.num} className="step-card">
              <div style={styles.stepNum}>{step.num}</div>
              <h3 style={styles.stepTitle}>{step.title}</h3>
              <p style={styles.stepDesc}>{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section style={{ ...styles.section, background: '#fafafa', maxWidth: '100%' }}>
        <div style={{ maxWidth: 960, margin: '0 auto' }}>
          <h2 style={styles.sectionTitle}>
            Why This Platform?
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginBottom: '1.5rem' }}>
            {[
              { title: '🤖 Questions Unique to You', desc: 'Every question is generated for you during the interview.' },
              { title: '🎯 Technical or General', desc: 'Choose a technical interview (skills, projects) or a general HR interview (motivation, strengths, career).' },
              { title: '🏢 Company-Specific', desc: 'Enter any company and role. The AI prepares context before the interview starts.' },
            ].map((f, i) => (
              <div key={i} className="feature-card">
                <h3 style={styles.featureTitle}>{f.title}</h3>
                <p style={styles.featureDesc}>{f.desc}</p>
              </div>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1.5rem', maxWidth: '66%', margin: '0 auto' }}>
            {[
              { title: '💬 Detailed Feedback', desc: 'Receive written feedback after the interview covering what went well and what to improve.' },
              { title: '📊 Post-Interview Feedback', desc: 'Get scores on content, fluency, and delivery — plus written strengths and improvements.' },
            ].map((f, i) => (
              <div key={i} className="feature-card">
                <h3 style={styles.featureTitle}>{f.title}</h3>
                <p style={styles.featureDesc}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section style={styles.ctaSection}>
        <h2 style={styles.ctaTitle}>
          Ready to Practice?
        </h2>
        <p style={styles.ctaSubtitle}>
          Create your first interview in under a minute. Pick any company, any role.
        </p>
        <Link to="/register" className="landing-btn">
          Create Free Account
        </Link>
      </section>

      {/* Footer */}
      <footer style={styles.footer}>
        <p>Built by Selin Kartal & Melis Halamoğlu — Yeditepe University Computer Engineering Senior Project 2026.</p>
        <div style={styles.footerLinks}>
          <Link to="/login" style={styles.footerLink}>
            Log In
          </Link>
          <Link to="/register" style={styles.footerLink}>
            Sign Up
          </Link>
          <Link to="/forgot-password" style={styles.footerLink}>
            Forgot Password
          </Link>
        </div>
      </footer>
    </div>
  )
}
