import { useEffect, useRef, forwardRef, useImperativeHandle, useState } from 'react'

const AVATARS = ['/avaturn.glb', '/brunette.glb', '/avaturn2.glb', '/avaturn3.glb', '/avaturn4.glb']
const AVATAR_URL = AVATARS[Math.floor(Math.random() * AVATARS.length)]
const MODULE_URL = window.location.origin + '/talkinghead.mjs'
const TTS_ENDPOINT = '/api/tts'  // backend TTS endpoint; falls back to browser speech if no audio
const TTS_VOICE = 'en-US-Wavenet-C'

const TalkingAvatar = forwardRef(function TalkingAvatar({ style }, ref) {
  const containerRef = useRef(null)
  const headRef = useRef(null)
  const safetyTimerRef = useRef(null)
  const [status, setStatus] = useState('loading')
  const [speaking, setSpeaking] = useState(false)
  const ttsAvailableRef = useRef(null) // null=unknown, true=has audio, false=empty

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

  const _speakWithBrowserTTS = (text, onEnd) => {
    setSpeaking(true)
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'
    u.rate = 0.92
    u.onend = () => { setSpeaking(false); onEnd?.() }
    u.onerror = () => { setSpeaking(false); onEnd?.() }
    window.speechSynthesis.speak(u)
  }

  useImperativeHandle(ref, () => ({
    speak(text, onEnd) {
      if (headRef.current && status === 'ready') {
        // If TTS endpoint has no audio (Windows), use Web Speech API directly
        if (ttsAvailableRef.current === false) {
          _speakWithBrowserTTS(text, onEnd)
          return
        }

        const safetyMs = Math.max(6000, text.length * 70)
        let done = false
        safetyTimerRef.current = setTimeout(() => {
          if (!done) { done = true; setSpeaking(false); onEnd?.() }
        }, safetyMs)
        const finish = () => {
          if (!done) { done = true; clearTimeout(safetyTimerRef.current); safetyTimerRef.current = null; setSpeaking(false); onEnd?.() }
        }

        // First time: probe TTS to see if audio is available
        if (ttsAvailableRef.current === null) {
          const token = localStorage.getItem('token') || ''
          fetch(TTS_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ input: { text: 'hi' }, voice: { languageCode: 'en-US', name: TTS_VOICE }, audioConfig: { audioEncoding: 'MP3' } }),
          })
            .then(r => r.json())
            .then(data => {
              ttsAvailableRef.current = !!(data.audioContent && data.audioContent.length > 10)
              if (!ttsAvailableRef.current) {
                // TTS has no audio — switch to Web Speech API
                clearTimeout(safetyTimerRef.current)
                _speakWithBrowserTTS(text, onEnd)
              } else {
                headRef.current.speakText(text, { ttsLang: 'en-US', ttsRate: 0.92 })
                  .then(finish).catch(finish)
              }
            })
            .catch(() => {
              ttsAvailableRef.current = false
              clearTimeout(safetyTimerRef.current)
              _speakWithBrowserTTS(text, onEnd)
            })
          return
        }

        headRef.current.speakText(text, { ttsLang: 'en-US', ttsRate: 0.92 })
          .then(finish).catch(finish)
        return
      }
      // Fallback: plain Web Speech API
      _speakWithBrowserTTS(text, onEnd)
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
      <div style={{ ...style, background: '#000', overflow: 'hidden' }}>
        {speaking && (
          <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.85rem' }}>
            AI speaking...
          </span>
        )}
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
