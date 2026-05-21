import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Header from '../components/Header'

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
  ctaBtn: {
    display: 'inline-block',
    padding: '0.85rem 2rem',
    background: '#111',
    color: '#fff',
    borderRadius: 10,
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: '1.05rem',
    transition: 'transform 0.15s',
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
    maxWidth: 960,
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
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '2rem',
  },
  step: {
    padding: '2rem',
    background: '#f9fafb',
    borderRadius: 12,
    border: '1px solid #e5e7eb',
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
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '1.5rem',
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

  useEffect(() => {
    if (localStorage.getItem('token')) {
      navigate('/dashboard', { replace: true })
    }
  }, [navigate])

  return (
    <div style={{ minHeight: '100vh', background: '#fff' }}>
      <Header links={[]} />

      {/* Hero */}
      <section style={styles.hero}>
        <span style={styles.badge}>
          ✨ AI-Powered Practice
        </span>
        <h1 style={styles.heroTitle}>
          Ace Your Next Interview with Confidence
        </h1>
        <p style={styles.heroSubtitle}>
          Practice real interview scenarios with AI. Get instant feedback, improve your answers, and land your dream job.
        </p>
        <Link to="/register" style={styles.ctaBtn}>
          Start Practicing — It&apos;s Free
        </Link>
        <div style={styles.heroFeatures}>
          {[
            ['🎙️', 'Voice-based AI interviews'],
            ['📊', 'Real-time scoring'],
            ['🏢', 'Industry-specific questions'],
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
            { num: '1', title: 'Create Account', desc: 'Sign up in seconds with your email. Set up your profile and upload your CV.' },
            { num: '2', title: 'Start Interview', desc: 'Choose your industry, role, and language. Our AI adapts questions to your background.' },
            { num: '3', title: 'Get Feedback', desc: 'Receive detailed scoring, strengths, and improvement suggestions after each session.' },
          ].map((step) => (
            <div key={step.num} style={styles.step}>
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
            Why Interview Sim?
          </h2>
          <div style={styles.featuresGrid}>
            {[
              { title: '🎯 Role-Specific', desc: 'Technical deep-dives or HR behavioral questions — tailored to your target role.' },
              { title: '🌍 Multi-Language', desc: 'Practice in Turkish or English. Perfect for international job applications.' },
              { title: '📄 CV-Aware', desc: 'AI reads your CV and asks about your real projects, skills, and experience.' },
              { title: '📊 Smart Scoring', desc: 'Get scored on content, clarity, confidence, and language quality.' },
              { title: '🏢 13 Industries', desc: 'From tech to finance, healthcare to law — questions match your sector.' },
              { title: '🔒 Private', desc: 'Your data stays local. No cloud APIs — everything runs on your machine.' },
            ].map((f, i) => (
              <div key={i} style={styles.featureCard}>
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
          Join now and experience your first AI-powered mock interview.
        </p>
        <Link to="/register" style={styles.ctaBtn}>
          Create Free Account
        </Link>
      </section>

      {/* Footer */}
      <footer style={styles.footer}>
        <p>Built for students and professionals preparing for real interviews.</p>
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
