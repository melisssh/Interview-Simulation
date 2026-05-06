import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL || '/api'
const SILENCE_SEND_MS = 1200
const MIC_RMS_THRESHOLD = 0.006
const MIN_CHUNKS_TO_SEND = 3

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

export default function InterviewRun() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [aiQuestion, setAiQuestion] = useState('')
  const [questionNum, setQuestionNum] = useState(0)
  const [totalQuestions] = useState(5)
  const [wsConnected, setWsConnected] = useState(false)
  const [micStatus, setMicStatus] = useState('Hazır')
  const [phase, setPhase] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [interviewEnded, setInterviewEnded] = useState(false)
  const isProcessingRef = useRef(false)
  const interviewEndedRef = useRef(false)
  
  // ... existing state definitions ...

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

  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  const stopSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
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
      setMicStatus('Cevap çok kısa, biraz daha konuş')
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
      setMicStatus('Cevap gönderildi, AI düşünüyor...')
    } catch (e) {
      console.error('WS send failed:', e)
    }
  }, [isProcessing])

  const connectWebSocket = useCallback(() => {
    const apiUrl = API.replace('/api', '').replace(/\/$/, '')
    const hostPart = apiUrl.replace(/^http(s)?:\/\//, '')
    const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${proto}://${hostPart}/ws/interview/${id}`

    const ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      setWsConnected(true)
      ws.send(
        JSON.stringify({
          type: 'init',
          domain: interview?.domain || 'general',
          language: interview?.language || 'tr',
          max_questions: 5,
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
          setMicStatus('Soru okunuyor...')
          if (data.question && typeof window !== 'undefined' && window.speechSynthesis) {
            speechBlockedRef.current = true
            window.speechSynthesis.cancel()
            const u = new SpeechSynthesisUtterance(data.question)
            u.lang = (interview?.language || 'tr') === 'en' ? 'en-US' : 'tr-TR'
            u.rate = 0.92
            u.onend = () => {
              speechBlockedRef.current = false
              setMicStatus('Dinliyorum...')
            }
            u.onerror = () => {
              speechBlockedRef.current = false
              setMicStatus('Dinliyorum...')
            }
            window.speechSynthesis.speak(u)
          } else {
            setMicStatus('Dinliyorum...')
          }
        } else if (data.type === 'ended') {
          setInterviewEnded(true)
          interviewEndedRef.current = true
          setAiQuestion(data.question || data.message || 'Mülakat tamamlandı.')
          setMicStatus('Mülakat tamamlandı')
          setIsProcessing(false)
          isProcessingRef.current = false
          setTimeout(() => {
            stopAndUploadVideo()
          }, 1500)
        } else if (data.type === 'error') {
          setError(data.message || 'WebSocket hatası')
          setIsProcessing(false)
          isProcessingRef.current = false
        }
      } catch {
        // yoksay parse hatası
      }
    }
    ws.onclose = () => setWsConnected(false)
    ws.onerror = () => setError('WebSocket bağlantı hatası')
    wsRef.current = ws
  }, [id, interview?.domain, interview?.language, stopAndUploadVideo])

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
        setMicStatus('Konuşma algılandı')
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
    if (!token) {
      navigate('/login')
      return
    }
    if (!id) return
    fetch(`${API}/interviews/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 401 || res.status === 403) navigate('/login')
        if (!res.ok) throw new Error('Mülakat alınamadı')
        return res.json()
      })
      .then(setInterview)
      .catch(() => setError('Mülakat bilgisi alınamadı'))
      .finally(() => setLoading(false))
  }, [id, token, navigate])

  useEffect(() => {
    return () => {
      stopSpeaking()
      if (wsRef.current) {
        try {
          if (wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.close()
          }
        } catch (e) { /* yoksay */ }
      }
      if (sendTimerRef.current) clearTimeout(sendTimerRef.current)
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop() } catch { /* yoksay */ }
      }
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop())
      if (processorRef.current) { try { processorRef.current.disconnect() } catch { /* yoksay */ } }
      if (sourceRef.current) { try { sourceRef.current.disconnect() } catch { /* yoksay */ } }
      if (muteGainRef.current) { try { muteGainRef.current.disconnect() } catch { /* yoksay */ } }
      if (audioContextRef.current) { try { audioContextRef.current.close() } catch { /* yoksay */ } }
    }
  }, [])

  async function handleStart() {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }

      recordedChunksRef.current = []
      let recorder
      try {
        recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp8' })
      } catch (recErr) {
        console.error('MediaRecorder başlatılamadı:', recErr)
        setError('Tarayıcın video kaydını desteklemiyor. Lütfen Chrome veya Edge ile dene.')
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
      setError('Kamera ve mikrofon izni verilmedi. Mülakat başlatılamadı.')
    }
  }

  async function stopAndUploadVideo() {
    if (uploading || interviewEnded) return
    setUploading(true)

    const recorder = mediaRecorderRef.current
    setRecording(false)
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end' }))
      wsRef.current.close()
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

      try {
        await fetch(`${API}/interviews/${id}/video`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        })
      } catch (e) {
        console.warn('Video upload başarısız:', e)
      }
    }

    setUploading(false)
    navigate(`/interview/${id}/sonuc`)
  }

  if (!token) return null
  if (loading) return <div style={{ padding: '2rem' }}>Yükleniyor...</div>
  if (error || !interview) return <div style={{ padding: '2rem', color: 'red' }}>{error || 'Mülakat bulunamadı'}</div>

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <header style={{
        background: '#fff', borderBottom: '1px solid #e5e7eb', padding: '0.75rem 1.5rem',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <span style={{ fontSize: '0.95rem', color: '#6b7280' }}>{interview.title}</span>
      </header>

      <main style={{ maxWidth: 1100, margin: '0 auto', padding: '2rem 1.5rem', display: 'grid', gap: '1.5rem', gridTemplateColumns: '3fr 2fr' }}>
        <section style={{ background: '#000', borderRadius: 12, overflow: 'hidden', minHeight: 320 }}>
          <video ref={videoRef} style={{ width: '100%', height: '100%', objectFit: 'cover' }} autoPlay muted />
        </section>

        <section style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.75rem', border: '1px solid #e5e7eb' }}>
            <div style={{
              width: 40, height: 40, borderRadius: '50%', background: '#0f172a', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: '0.9rem',
            }}>AI</div>
            <div style={{ fontSize: '0.9rem', color: '#4b5563' }}>
              {phase === 'greeting' && 'AI sizi karşılıyor...'}
              {phase === 'questions' && 'AI sizi dinliyor. Soruyu cevaplayın, sessizlikte otomatik gönderilir.'}
              {phase === 'closing' && 'Mülakat kapanış aşamasında...'}
              {interviewEnded && 'Mülakat tamamlandı.'}
            </div>
          </div>

          <div style={{ background: '#fff', borderRadius: 12, padding: '1.5rem', border: '1px solid #e5e7eb' }}>
            <h1 style={{ fontSize: '1.3rem', fontWeight: 600, marginBottom: '0.5rem' }}>Mülakat</h1>
            <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '0.75rem' }}>
              Konuşmanızı algıladıktan ~{Math.round(SILENCE_SEND_MS / 1000)}sn sonra cevabınız otomatik gönderilir.
            </p>

            {recording && <p style={{ fontSize: '0.9rem', color: '#16a34a', marginBottom: '0.5rem' }}>● Kayıt alınıyor...</p>}
            {uploading && <p style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.5rem' }}>Video yükleniyor, lütfen sayfayı kapatma...</p>}
            {error && <p style={{ color: '#dc2626', fontSize: '0.9rem' }}>{error}</p>}

            {!recording && !interviewEnded && (
              <>
                <p style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                  Başlamadan önce kamera ve mikrofon izni isteyeceğiz.
                </p>
                <button
                  type="button"
                  onClick={handleStart}
                  style={{
                    padding: '0.75rem 1.5rem', background: '#111', color: '#fff', borderRadius: 8,
                    border: 'none', fontWeight: 500, fontSize: '1rem', cursor: 'pointer',
                  }}
                >
                  Mülakata başla
                </button>
              </>
            )}

            {recording && aiQuestion && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <p style={{ fontSize: '0.9rem', color: '#6b7280', margin: 0 }}>
                    Soru {questionNum || '—'} / {totalQuestions}
                  </p>
                  {wsConnected && <p style={{ fontSize: '0.8rem', color: '#16a34a' }}>● AI bağlı</p>}
                </div>
                <div style={{ padding: '1rem', borderRadius: 8, background: '#f3f4f6', marginBottom: '0.75rem', whiteSpace: 'pre-wrap' }}>
                  {aiQuestion}
                </div>
                <p style={{ fontSize: '0.9rem', color: '#6b7280', marginTop: '1rem' }}>
                  {isProcessing ? '⏳ AI düşünüyor...' : `🎤 ${micStatus}`}
                </p>
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                  <button
                    type="button"
                    onClick={sendPendingAudio}
                    style={{
                      padding: '0.55rem 0.9rem', background: '#16a34a', color: '#fff', borderRadius: 8,
                      border: 'none', fontWeight: 500, cursor: 'pointer', flex: 1,
                    }}
                  >
                    📤 Gönder
                  </button>
                  <button
                    type="button"
                    onClick={stopAndUploadVideo}
                    style={{
                      padding: '0.55rem 0.9rem', background: '#dc2626', color: '#fff', borderRadius: 8,
                      border: 'none', fontWeight: 500, cursor: 'pointer',
                    }}
                  >
                    Bitir
                  </button>
                </div>
              </>
            )}

            {interviewEnded && (
              <>
                <div style={{ padding: '1rem', borderRadius: 8, background: '#e8f5e9', marginBottom: '0.75rem', whiteSpace: 'pre-wrap' }}>
                  {aiQuestion}
                </div>
                <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '1rem' }}>
                  Sonuç sayfasına yönlendiriliyorsunuz...
                </p>
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
