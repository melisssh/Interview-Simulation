import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

import { API } from '../api'
import TalkingAvatar from '../components/TalkingAvatar'
const SILENCE_SEND_MS = 1200
const MIC_RMS_THRESHOLD = 0.002
const MIN_CHUNKS_TO_SEND = 2

function floatChunksToBase64Int16(chunks) {
  const length = chunks.reduce((sum, arr) => sum + arr.length, 0)
  if (!length) return null
  const merged = new Float32Array(length)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  const int16 = new Int16Array(merged.length)
  for (let i = 0; i < merged.length; i++) {
    int16[i] = Math.max(-1, Math.min(1, merged[i])) * 32767
  }
  const bytes = new Uint8Array(int16.buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

const BG_IMAGES = ['/bg-office1.jpg', '/bg-office2.jpg', '/bg-office3.jpg', '/bg-office4.jpg']
const BG_URL = BG_IMAGES[Math.floor(Math.random() * BG_IMAGES.length)]

export default function InterviewRun() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)
  const [showLeaveModal, setShowLeaveModal] = useState(false)
  const [recording, setRecording] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [aiQuestion, setAiQuestion] = useState('')
  const [questionNum, setQuestionNum] = useState(0)
  const [wsConnected, setWsConnected] = useState(false)
  const [micStatus, setMicStatus] = useState('')
  const [phase, setPhase] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [interviewEnded, setInterviewEnded] = useState(false)
  const [userName, setUserName] = useState('You')
  const isProcessingRef = useRef(false)
  const interviewEndedRef = useRef(false)
  const uploadingRef = useRef(false)
  const leavingRef = useRef(false)

  const avatarRef = useRef(null)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const recordedChunksRef = useRef([])
  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const sourceRef = useRef(null)
  const processorRef = useRef(null)
  const muteGainRef = useRef(null)
  const speechBlockedRef = useRef(false)
  const sendTimerRef = useRef(null)
  const pendingChunksRef = useRef([])
  const tRef = useRef(null)
  const reconnectTimerRef = useRef(null)

  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  useEffect(() => {
    if (!recording) return
    const handleBeforeUnload = (e) => {
      e.preventDefault()
      e.returnValue = tRef.current?.leaveWarning || 'Are you sure you want to leave?'
      return e.returnValue
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [recording])

  const t = {
    loading: 'Loading...',
    notFound: 'Interview not found',
    fetchError: 'Could not fetch interview',
    fetchInfoError: 'Could not load',
    camDenied: 'Camera and microphone permission denied. Cannot start interview.',
    noVideoSupport: 'Your browser does not support video recording.',
    greeting: 'AI is greeting you...',
    listeningDesc: 'AI is listening. Answer and press send.',
    closing: 'Interview closing phase...',
    completed: 'Interview completed.',
    reading: 'AI is reading...',
    listening: '🔊 Listening...',
    speechDetected: '🎤 Speech detected',
    tooShort: 'Too short',
    sentThinking: 'Sent, processing...',
    wsError: 'Connection error',
    wsConnError: 'Could not connect to AI',
    recording: 'Recording...',
    uploading: 'Video uploading, please do not close the page...',
    ready: 'INTERVIEW READY',
    permissionDesc: 'We will ask for camera and microphone permission. Questions will appear on screen one by one while recording. You can start the interview when ready.',
    startBtn: 'Start interview',
    later: 'Later',
    preparing: 'INTERVIEW PREPARING',
    preparingDesc: 'Your interview is being prepared. Company research and question generation in progress. This may take a few seconds. Please wait...',
    preparationFailed: 'Preparation failed. Please try again.',
    backToDashboard: 'Back to dashboard',
    retryPrep: 'Retry',
    retrying: 'Retrying...',
    reconnectWarning: 'You previously left this interview. If you press start, the interview will restart from the beginning.',
    connecting: 'AI connecting, first question preparing...',
    questionLabel: 'Question #',
    aiConnected: '● AI connected',
    thinking: '⏳ AI thinking...',
    sendBtn: '📤 Send',
    redirecting: 'Redirecting to results page...',
    leaveWarning: 'If you leave the interview, you will need to start over. Are you sure?',
    leaveConfirm: 'Leave Interview',
    leaveCancel: 'Continue',
  }
  tRef.current = t

  const stopSpeaking = useCallback(() => {
    if (avatarRef.current) {
      avatarRef.current.stop()
    } else if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
    speechBlockedRef.current = false
  }, [])

  const sendPendingAudio = useCallback(() => {
    if (sendTimerRef.current) {
      clearTimeout(sendTimerRef.current)
      sendTimerRef.current = null
    }
    if (!pendingChunksRef.current.length) return
    if (pendingChunksRef.current.length < MIN_CHUNKS_TO_SEND) {
      pendingChunksRef.current = []
      return
    }
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    if (isProcessingRef.current || speechBlockedRef.current) return

    const base64 = floatChunksToBase64Int16(pendingChunksRef.current)
    pendingChunksRef.current = []
    if (!base64) return
    try {
      wsRef.current.send(JSON.stringify({ type: 'audio', audio: base64 }))
      setIsProcessing(true)
      isProcessingRef.current = true
      setMicStatus(tRef.current.sentThinking)
    } catch (e) {
      console.error('WS send failed:', e)
    }
  }, [])

  const connectWebSocket = useCallback(() => {
    const token = localStorage.getItem('token')
    const loc = window.location
    const proto = loc.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${proto}://${loc.host}/ws/interview/${id}?token=${token}`

    const ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      setWsConnected(true)
      ws.send(
        JSON.stringify({
          type: 'init',
          domain: interview?.domain || 'general',
          language: 'en',
          max_questions: 7,
        }),
      )
    }
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'question') {
          setAiQuestion(data.question || '')
          setQuestionNum(data.q_num || 1)
          setPhase(data.phase || 'questions')
          setIsProcessing(false)
          isProcessingRef.current = false
          setMicStatus(tRef.current.reading)
          if (data.question && !leavingRef.current) {
            speechBlockedRef.current = true
            if (avatarRef.current) {
              avatarRef.current.speak(data.question, () => {
                speechBlockedRef.current = false
                setMicStatus(tRef.current.listening)
              })
            } else {
              speechBlockedRef.current = false
              setMicStatus(tRef.current.listening)
            }
          } else if (!leavingRef.current) {
            setMicStatus(tRef.current.listening)
          }
        } else if (data.type === 'ended') {
          setInterviewEnded(true)
          interviewEndedRef.current = true
          setAiQuestion(data.question || data.message || tRef.current.completed)
          setMicStatus(tRef.current.completed)
          setIsProcessing(false)
          isProcessingRef.current = false
          setPhase('closing')

          const closingText = data.question || data.message || tRef.current.completed
          if (closingText && !leavingRef.current) {
            speechBlockedRef.current = true
            if (avatarRef.current) {
              avatarRef.current.speak(closingText, () => {
                speechBlockedRef.current = false
                setTimeout(() => { stopAndUploadVideo() }, 1000)
              })
            } else {
              setTimeout(() => { stopAndUploadVideo() }, 1500)
            }
          } else {
            setTimeout(() => { stopAndUploadVideo() }, 1500)
          }
        } else if (data.type === 'error') {
          setError(data.message || tRef.current.wsError)
          setIsProcessing(false)
          isProcessingRef.current = false
        }
      } catch {
        // ignore parse errors
      }
    }
    ws.onclose = () => {
      setWsConnected(false)
      if (!interviewEndedRef.current) {
        reconnectTimerRef.current = setTimeout(() => connectWebSocket(), 3000)
      }
    }
    ws.onerror = () => {
      if (!interviewEndedRef.current) {
        setError(tRef.current.wsConnError)
        ws.close()
      }
    }
    wsRef.current = ws
  }, [id, interview?.domain])

  const startAudioCapture = useCallback(() => {
    if (!streamRef.current) return
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return
    const ac = new AC({ sampleRate: 48000 })
    audioContextRef.current = ac
    const source = ac.createMediaStreamSource(streamRef.current)
    const processor = ac.createScriptProcessor(4096, 1, 1)
    const muteGain = ac.createGain()
    muteGain.gain.value = 0

    sourceRef.current = source
    processorRef.current = processor
    muteGainRef.current = muteGain
    source.connect(processor)
    processor.connect(muteGain)
    muteGain.connect(ac.destination)

    processor.onaudioprocess = (e) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
      if (speechBlockedRef.current || isProcessingRef.current || interviewEndedRef.current) return

      const input = e.inputBuffer.getChannelData(0)
      let rms = 0
      for (let i = 0; i < input.length; i++) rms += input[i] * input[i]
      rms = Math.sqrt(rms / input.length)

      if (rms > MIC_RMS_THRESHOLD) {
        pendingChunksRef.current.push(new Float32Array(input))
        setMicStatus(tRef.current.speechDetected)
        if (sendTimerRef.current) {
          clearTimeout(sendTimerRef.current)
          sendTimerRef.current = null
        }
      } else if (pendingChunksRef.current.length) {
        if (sendTimerRef.current) clearTimeout(sendTimerRef.current)
        sendTimerRef.current = setTimeout(() => {
          sendPendingAudio()
        }, SILENCE_SEND_MS)
      }
    }
  }, [sendPendingAudio])

  useEffect(() => {
    if (!token) return
    fetch(`${API}/profile`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => { if (data.full_name) setUserName(data.full_name) })
      .catch(() => {})
  }, [token])

  useEffect(() => {
    if (!token) {
      navigate('/login')
      return
    }
    if (!id) return
    fetch(`${API}/interviews/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401 || res.status === 403) { navigate('/login'); return null }
        if (!res.ok) throw new Error(t.fetchError)
        return res.json()
      })
      .then((data) => { if (data) setInterview(data) })
      .catch(() => setError(t.fetchInfoError))
      .finally(() => setLoading(false))
  }, [id, token, navigate])

  const isPreparing = interview?.status === 'preparing' || interview?.status === 'created'

  const handleRetryPrep = async () => {
    setRetrying(true)
    setError('')
    try {
      const res = await fetch(`${API}/interviews/${id}/retry-prep`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Retry failed')
        setRetrying(false)
        return
      }
      setInterview((prev) => (prev ? { ...prev, status: 'preparing', preparation_error: null } : prev))
      setRetrying(false)
    } catch {
      setError('Connection error')
      setRetrying(false)
    }
  }

  useEffect(() => {
    if (!isPreparing || !id) return
    const interval = setInterval(() => {
      fetch(`${API}/interviews/${id}`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.json())
        .then((data) => {
          setInterview(data)
          if (data.status !== 'preparing' && data.status !== 'created') clearInterval(interval)
        })
        .catch(() => {})
    }, 3000)
    return () => clearInterval(interval)
  }, [isPreparing, id, token])

  useEffect(() => {
    return () => {
      stopSpeaking()
      if (wsRef.current) {
        try {
          if (wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.close()
          }
        } catch (e) { /* ignore */ }
      }
      if (sendTimerRef.current) clearTimeout(sendTimerRef.current)
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop() } catch { /* ignore */ }
      }
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop())
      if (processorRef.current) { try { processorRef.current.disconnect() } catch { /* ignore */ } }
      if (sourceRef.current) { try { sourceRef.current.disconnect() } catch { /* ignore */ } }
      if (muteGainRef.current) { try { muteGainRef.current.disconnect() } catch { /* ignore */ } }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        try { audioContextRef.current.close() } catch { /* ignore */ }
      }
    }
  }, [])

  useEffect(() => {
    if (recording && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
      videoRef.current.play()
    }
  }, [recording])

  useEffect(() => {
    if (interview?.status === 'analyzing' || interview?.status === 'analyzed' || interview?.status === 'analysis_failed') {
      navigate(`/interview/${id}/result`)
    }
  }, [interview?.status, id, navigate])

  async function handleStart() {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      streamRef.current = stream

      recordedChunksRef.current = []
      let recorder
      try {
        recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8' })
      } catch (recErr) {
        console.error('MediaRecorder could not start:', recErr)
        setError(t.noVideoSupport)
        return
      }

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) recordedChunksRef.current.push(event.data)
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setRecording(true)

      pendingChunksRef.current = []
      connectWebSocket()
      setTimeout(() => startAudioCapture(), 500)
    } catch (e) {
      console.error('getUserMedia error:', e)
      setError(t.camDenied)
    }
  }

  async function stopAndUploadVideo() {
    if (uploadingRef.current) return
    uploadingRef.current = true
    setUploading(true)
    setRecording(false)

    const recorder = mediaRecorderRef.current
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try { wsRef.current.send(JSON.stringify({ type: 'end' })) } catch { /* ignore */ }
      try { wsRef.current.close() } catch { /* ignore */ }
    }

    if (recorder && recorder.state !== 'inactive') {
      await new Promise((resolve) => {
        recorder.onstop = () => resolve()
        try { recorder.stop() } catch { resolve() }
      })
    }

    const chunks = recordedChunksRef.current || []
    if (chunks.length) {
      const blob = new Blob(chunks, { type: 'video/webm' })
      const formData = new FormData()
      formData.append('file', blob, 'interview.webm')
      // Upload in background, navigate to dashboard without waiting
      fetch(`${API}/interviews/${id}/video`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      }).catch((e) => console.warn('Video upload failed:', e))
    }

    navigate('/dashboard')
  }

  if (!token) return null
  if (loading) return <div style={{ padding: '2rem' }}>{t.loading}</div>
  if (error || !interview) return <div style={{ padding: '2rem', color: 'red' }}>{error || t.notFound}</div>

  const isFailed = interview.status === 'preparation_failed'
  const isInProgress = interview.status === 'in_progress'
  const isAnalyzing = interview.status === 'analyzing'
  const isAnalyzed = interview.status === 'analyzed'
  const isAnalysisFailed = interview.status === 'analysis_failed'

  const cardStyle = {
    maxWidth: 420, width: '100%', margin: '0 1.5rem', padding: '2.25rem 2rem',
    borderRadius: 16, background: '#fff', boxShadow: '0 24px 60px rgba(15,23,42,0.4)', textAlign: 'center',
  }
  const outerStyle = {
    minHeight: '100vh', background: 'rgba(15,23,42,0.85)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }

  if (isPreparing) {
    return (
      <div style={outerStyle}>
        <div style={cardStyle}>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <p style={{ fontSize: '0.8rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '0.75rem' }}>{t.preparing}</p>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#111', marginBottom: '0.25rem', lineHeight: 1.2 }}>{interview.title}</h1>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.5rem' }}>{interview.domain} &middot; {interview.language}</p>
          <p style={{ fontSize: '0.95rem', color: '#4b5563', marginBottom: '1.5rem', lineHeight: 1.6 }}>{t.preparingDesc}</p>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', border: '3px solid #e5e7eb', borderTopColor: '#111', animation: 'spin 0.8s linear infinite' }} />
          </div>
        </div>
      </div>
    )
  }

  if (isFailed) {
    return (
      <div style={outerStyle}>
        <div style={cardStyle}>
          <p style={{ fontSize: '0.8rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#dc2626', marginBottom: '0.75rem' }}>&#10005;</p>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#111', marginBottom: '0.25rem', lineHeight: 1.2 }}>{interview.title}</h1>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.5rem' }}>{interview.domain} &middot; {interview.language}</p>
          <p style={{ fontSize: '0.95rem', color: '#dc2626', marginBottom: '1.5rem', lineHeight: 1.6 }}>{t.preparationFailed}</p>
          {error && <p style={{ color: '#dc2626', fontSize: '0.9rem', marginBottom: '1rem' }}>{error}</p>}
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={handleRetryPrep}
              disabled={retrying}
              style={{
                padding: '0.85rem 1.9rem', background: retrying ? '#9ca3af' : '#111', color: '#fff',
                borderRadius: 999, fontWeight: 500, fontSize: '1rem', border: 'none',
                cursor: retrying ? 'not-allowed' : 'pointer', display: 'inline-block',
              }}
            >
              {retrying ? t.retrying : t.retryPrep}
            </button>
            <Link to="/dashboard" style={{ padding: '0.85rem 1.9rem', background: '#fff', color: '#111', textDecoration: 'none', borderRadius: 999, fontWeight: 500, fontSize: '1rem', display: 'inline-block', border: '1px solid #e5e7eb' }}>{t.backToDashboard}</Link>
          </div>
        </div>
      </div>
    )
  }

  if (!recording && !interviewEnded) {
    return (
      <div style={outerStyle}>
        <div style={cardStyle}>
          <p style={{ fontSize: '0.8rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '0.75rem' }}>{t.ready}</p>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#111', marginBottom: '0.25rem', lineHeight: 1.2 }}>{interview.title}</h1>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1.5rem' }}>{interview.domain} &middot; {interview.language}</p>
          <p style={{ fontSize: '0.95rem', color: '#4b5563', marginBottom: '1.5rem', lineHeight: 1.6 }}>{t.permissionDesc}</p>
          {isInProgress && (
            <p style={{ fontSize: '0.85rem', color: '#f59e0b', marginBottom: '1rem', lineHeight: 1.5, background: '#fffbeb', padding: '0.75rem', borderRadius: 8 }}>{t.reconnectWarning}</p>
          )}
          {error && <p style={{ color: '#dc2626', fontSize: '0.9rem', marginBottom: '1rem' }}>{error}</p>}
          <button
            type="button"
            onClick={handleStart}
            style={{
              padding: '0.85rem 1.9rem', background: '#111', color: '#fff', textDecoration: 'none',
              borderRadius: 999, fontWeight: 500, fontSize: '1rem', border: 'none', cursor: 'pointer',
              display: 'inline-block', minWidth: 190,
            }}
          >
            {t.startBtn}
          </button>
          <div style={{ marginTop: '1.25rem', fontSize: '0.85rem' }}>
            <Link to="/dashboard" style={{ color: '#6b7280', textDecoration: 'underline' }}>{t.later}</Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      {recording && !interviewEnded && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, background: '#111', color: '#fff', padding: '0.5rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 100 }}>
          <span style={{ fontSize: '0.85rem' }}>● {t.recording}</span>
          <button type="button" onClick={() => setShowLeaveModal(true)} style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)', borderRadius: 6, padding: '0.3rem 0.75rem', cursor: 'pointer', fontSize: '0.85rem' }}>{t.leaveConfirm}</button>
        </div>
      )}
      <main style={{ maxWidth: 1400, margin: '0 auto', padding: recording && !interviewEnded ? '3.5rem 1rem 1.5rem' : '2rem 1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>

        {/* Video tiles — side by side like Zoom */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', height: '65vh' }}>
          {/* AI avatar tile */}
          <div style={{ position: 'relative', backgroundImage: `url(${BG_URL})`, backgroundSize: 'cover', backgroundPosition: 'center', borderRadius: 12, overflow: 'hidden' }}>
            <TalkingAvatar ref={avatarRef} style={{ width: '100%', height: '100%' }} />
            <span style={{ position: 'absolute', bottom: 10, left: 12, fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)', background: 'rgba(0,0,0,0.45)', padding: '2px 8px', borderRadius: 4 }}>
              AI Interviewer
            </span>
          </div>

          {/* User camera tile */}
          <div style={{ position: 'relative', background: '#111', borderRadius: 12, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <video
              ref={videoRef}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              autoPlay muted
            />
            {!recording && (
              <span style={{ position: 'absolute', color: 'rgba(255,255,255,0.35)', fontSize: '0.85rem' }}>Camera preview</span>
            )}
            <span style={{ position: 'absolute', bottom: 10, left: 12, fontSize: '0.75rem', color: 'rgba(255,255,255,0.7)', background: 'rgba(0,0,0,0.45)', padding: '2px 8px', borderRadius: 4 }}>
              {userName}
            </span>
          </div>
        </div>

        {/* Question / status panel */}
        <div style={{ background: '#fff', borderRadius: 12, padding: '1.25rem 1.5rem', border: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {recording && !aiQuestion && (
            <p style={{ fontSize: '0.95rem', color: '#6b7280', textAlign: 'center', margin: 0 }}>{t.connecting}</p>
          )}

          {recording && aiQuestion && (
            <>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.95rem', lineHeight: 1.7, color: '#1e293b' }}>
                {aiQuestion}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #f1f5f9', paddingTop: '0.75rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                  {isProcessing ? t.thinking : `🎤 ${micStatus}`}
                </span>
                {!interviewEnded && (
                  <button
                    type="button"
                    onClick={sendPendingAudio}
                    style={{
                      padding: '0.45rem 1rem', background: '#111', color: '#fff', borderRadius: 8,
                      border: 'none', fontWeight: 500, cursor: 'pointer', fontSize: '0.85rem',
                    }}
                  >
                    {t.sendBtn}
                  </button>
                )}
              </div>
            </>
          )}

          {uploading && <p style={{ fontSize: '0.85rem', color: '#6b7280', margin: 0 }}>{t.uploading}</p>}
          {error && <p style={{ color: '#dc2626', fontSize: '0.9rem', margin: 0 }}>{error}</p>}
        </div>
      </main>

      {showLeaveModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: '2rem', maxWidth: 400, textAlign: 'center' }}>
            <p style={{ fontSize: '1rem', fontWeight: 500, marginBottom: '1rem' }}>{t.leaveWarning}</p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button onClick={() => setShowLeaveModal(false)} style={{ padding: '0.5rem 1.25rem', borderRadius: 8, border: '1px solid #d1d5db', background: '#fff', cursor: 'pointer', fontWeight: 500 }}>{t.leaveCancel}</button>
              <button onClick={() => { leavingRef.current = true; stopSpeaking(); if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop()); if (wsRef.current) { try { wsRef.current.close() } catch {} } if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') { try { mediaRecorderRef.current.stop() } catch {} } if (audioContextRef.current) { try { audioContextRef.current.close() } catch {} } setShowLeaveModal(false); navigate('/dashboard') }} style={{ padding: '0.5rem 1.25rem', borderRadius: 8, border: 'none', background: '#dc2626', color: '#fff', cursor: 'pointer', fontWeight: 500 }}>{t.leaveConfirm}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
