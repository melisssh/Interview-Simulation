import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from 'react'

const AVATARS = ['/avaturn.glb', '/brunette.glb', '/avaturn2.glb', '/avaturn3.glb', '/avaturn4.glb']
const AVATAR_URL = AVATARS[Math.floor(Math.random() * AVATARS.length)]
const MODULE_URL = window.location.origin + '/talkinghead.mjs'
const TTS_ENDPOINT = '/api/tts'  // backend proxy → Google Cloud TTS (fixes OGG-OPUS encoding)
const TTS_VOICE = 'en-US-Wavenet-C'  // female Wavenet voice, 1M chars/month free

// Simple 2D CSS avatar used when WebGL is unavailable
function FallbackAvatar({ speaking }) {
  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)',
      gap: '1rem',
    }}>
      {/* Head */}
      <div style={{
        position: 'relative',
        width: 140,
        height: 160,
      }}>
        {/* Face circle */}
        <div style={{
          width: 140,
          height: 160,
          borderRadius: '50%',
          background: 'linear-gradient(160deg, #f5cba7 0%, #e8b88a 100%)',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          position: 'relative',
          overflow: 'hidden',
        }}>
          {/* Hair */}
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 55,
            background: '#3d2314',
            borderRadius: '50% 50% 0 0 / 60% 60% 0 0',
          }} />
          {/* Left eye */}
          <div style={{
            position: 'absolute',
            top: 60,
            left: 30,
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: '#2c1810',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff', marginLeft: 3, marginTop: -3 }} />
          </div>
          {/* Right eye */}
          <div style={{
            position: 'absolute',
            top: 60,
            right: 30,
            width: 18,
            height: 18,
            borderRadius: '50%',
            background: '#2c1810',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff', marginLeft: 3, marginTop: -3 }} />
          </div>
          {/* Nose */}
          <div style={{
            position: 'absolute',
            top: 88,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 10,
            height: 14,
            borderLeft: '4px solid transparent',
            borderRight: '4px solid transparent',
            borderBottom: '8px solid rgba(0,0,0,0.15)',
          }} />
          {/* Mouth — animates when speaking */}
          <div style={{
            position: 'absolute',
            bottom: 28,
            left: '50%',
            transform: 'translateX(-50%)',
            width: speaking ? 36 : 30,
            height: speaking ? 14 : 6,
            borderRadius: speaking ? '0 0 18px 18px' : '0 0 8px 8px',
            background: speaking ? '#c0392b' : '#a0522d',
            transition: 'all 0.08s ease',
            overflow: 'hidden',
          }}>
            {speaking && (
              <div style={{
                position: 'absolute',
                top: 2,
                left: '50%',
                transform: 'translateX(-50%)',
                width: 28,
                height: 8,
                borderRadius: '50%',
                background: '#7b241c',
              }} />
            )}
          </div>
          {/* Cheek blush left */}
          <div style={{
            position: 'absolute',
            top: 80,
            left: 10,
            width: 22,
            height: 12,
            borderRadius: '50%',
            background: 'rgba(255,150,120,0.25)',
          }} />
          {/* Cheek blush right */}
          <div style={{
            position: 'absolute',
            top: 80,
            right: 10,
            width: 22,
            height: 12,
            borderRadius: '50%',
            background: 'rgba(255,150,120,0.25)',
          }} />
        </div>
        {/* Neck */}
        <div style={{
          position: 'absolute',
          bottom: -28,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 36,
          height: 30,
          background: '#e8b88a',
        }} />
      </div>
      {/* Shoulders / body */}
      <div style={{
        width: 180,
        height: 80,
        background: 'linear-gradient(180deg, #2d4a8a 0%, #1e3a6e 100%)',
        borderRadius: '40% 40% 0 0',
        marginTop: 0,
        boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
      }} />
      {/* Speaking indicator */}
      {speaking && (
        <div style={{
          display: 'flex',
          gap: 5,
          alignItems: 'flex-end',
          height: 20,
          marginTop: -10,
        }}>
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} style={{
              width: 4,
              borderRadius: 2,
              background: '#60a5fa',
              animationName: 'soundbar',
              animationDuration: `${0.4 + i * 0.08}s`,
              animationTimingFunction: 'ease-in-out',
              animationIterationCount: 'infinite',
              animationDirection: 'alternate',
              height: `${8 + (i % 3) * 6}px`,
            }} />
          ))}
        </div>
      )}
      <style>{`
        @keyframes soundbar {
          from { transform: scaleY(0.3); }
          to   { transform: scaleY(1.0); }
        }
      `}</style>
    </div>
  )
}

const TalkingAvatar = forwardRef(function TalkingAvatar({ style }, ref) {
  const containerRef = useRef(null)
  const headRef = useRef(null)
  const safetyTimerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [speaking, setSpeaking] = useState(false)

  useEffect(() => {
    let cancelled = false
    let head = null

    async function init() {
      try {
        const { TalkingHead } = await import(/* @vite-ignore */ MODULE_URL)
        if (cancelled) return

        head = new TalkingHead(containerRef.current, {
          ttsEndpoint: TTS_ENDPOINT,
          ttsLang: 'en-US',
          ttsVoice: TTS_VOICE,
          jwtGet: () => localStorage.getItem('token') || '',
          cameraView: 'upper',
          cameraY: 0,
          cameraRotateEnable: false,
          markerShow: false,
          lightAmbientColor: 0xffffff,
          lightAmbientIntensity: 2,
        })
        headRef.current = head

        await new Promise((resolve, reject) => {
          head.showAvatar(
            {
              url: AVATAR_URL,
              body: 'F',
              avatarMood: 'neutral',
              ttsLang: 'en-US',
              ttsVoice: TTS_VOICE,
            },
            resolve,
            reject,
          )
        })

        if (cancelled) return
        setStatus('ready')
      } catch (err) {
        console.warn('TalkingAvatar: could not load 3D avatar, using 2D fallback.', err)
        if (!cancelled) setStatus('fallback')
      }
    }

    init()
    return () => {
      cancelled = true
      if (head) { try { head.stop?.() } catch { /* ignore */ } }
    }
  }, [])

  useImperativeHandle(ref, () => ({
    speak(text, onEnd) {
      if (headRef.current && status === 'ready') {
        // Safety: if TalkingHead promise never resolves, unblock mic after estimated duration
        const safetyMs = Math.max(6000, text.length * 70)
        let done = false
        safetyTimerRef.current = setTimeout(() => {
          if (!done) { done = true; setSpeaking(false); onEnd?.() }
        }, safetyMs)
        const finish = () => {
          if (!done) { done = true; clearTimeout(safetyTimerRef.current); safetyTimerRef.current = null; setSpeaking(false); onEnd?.() }
        }
        headRef.current.speakText(text, { ttsLang: 'en-US', ttsRate: 0.92 })
          .then(finish).catch(finish)
        return
      }
      // Fallback: plain Web Speech API
      setSpeaking(true)
      window.speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(text)
      u.lang = 'en-US'
      u.rate = 0.92
      u.onend = () => { setSpeaking(false); onEnd?.() }
      u.onerror = () => { setSpeaking(false); onEnd?.() }
      window.speechSynthesis.speak(u)
    },
    stop() {
      if (safetyTimerRef.current) { clearTimeout(safetyTimerRef.current); safetyTimerRef.current = null }
      setSpeaking(false)
      if (headRef.current) { try { headRef.current.stopSpeaking?.() } catch { /* ignore */ } }
      window.speechSynthesis.cancel()
    },
  }), [status])

  if (status === 'fallback') {
    return (
      <div style={{ ...style, overflow: 'hidden' }}>
        <FallbackAvatar speaking={speaking} />
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      style={{
        ...style,
        background: 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {status === 'loading' && (
        <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: '0.8rem' }}>Loading avatar...</span>
      )}
    </div>
  )
})

export default TalkingAvatar
