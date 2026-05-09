import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

<<<<<<< Updated upstream
const API = '/api'
=======
const API = import.meta.env.VITE_API_URL || '/api'
const SILENCE_SEND_MS = 2200
const LOW_MODE_SILENCE_SEND_MS = 3000
const MIC_RMS_THRESHOLD = 0.006
const MIN_CHUNKS_TO_SEND = 3
const LOW_MODE_MIN_CHUNKS_TO_SEND = 5

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
>>>>>>> Stashed changes

export default function InterviewRun() {
  const { id } = useParams()
  const [interview, setInterview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
<<<<<<< Updated upstream
  const [currentIndex, setCurrentIndex] = useState(-1) // -1: daha başlamadı
  const [finishing, setFinishing] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
=======
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
  const [performanceMode, setPerformanceMode] = useState(() => {
    if (typeof window === 'undefined') return 'normal'
    return localStorage.getItem('interviewPerformanceMode') || 'normal'
  })
  const [silentTestMode, setSilentTestMode] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('interviewSilentTestMode') === 'true'
  })
  const isProcessingRef = useRef(false)
  const interviewEndedRef = useRef(false)
  const intentionalCloseRef = useRef(false)

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
  const autoAnswerTimerRef = useRef(null)
  const pendingChunksRef = useRef([])
>>>>>>> Stashed changes

  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const silenceWindowMs = performanceMode === 'low' ? LOW_MODE_SILENCE_SEND_MS : SILENCE_SEND_MS
  const minChunksToSend = performanceMode === 'low' ? LOW_MODE_MIN_CHUNKS_TO_SEND : MIN_CHUNKS_TO_SEND

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('interviewPerformanceMode', performanceMode)
    }
  }, [performanceMode])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('interviewSilentTestMode', silentTestMode ? 'true' : 'false')
    }
  }, [silentTestMode])

<<<<<<< Updated upstream
=======
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
    if (pendingChunksRef.current.length < minChunksToSend) {
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
  }, [minChunksToSend])

  const connectWebSocket = useCallback(() => {
    const apiUrl = API.replace('/api', '').replace(/\/$/, '')
    const hostPart = apiUrl.replace(/^http(s)?:\/\//, '')
    const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${proto}://${hostPart}/ws/interview/${id}`

    const ws = new WebSocket(wsUrl)
    intentionalCloseRef.current = false
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
          if (silentTestMode && wsRef.current?.readyState === WebSocket.OPEN) {
            if (autoAnswerTimerRef.current) clearTimeout(autoAnswerTimerRef.current)
            autoAnswerTimerRef.current = setTimeout(() => {
              if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
              if (interviewEndedRef.current || isProcessingRef.current) return
              try {
                wsRef.current.send(JSON.stringify({
                  type: 'test_answer',
                  text: `Sessiz test cevabı ${data.q_num || questionNum || 1}`,
                }))
                setIsProcessing(true)
                isProcessingRef.current = true
                setMicStatus('Sessiz test cevabı gönderildi...')
              } catch (e) {
                console.error('Test answer send failed:', e)
              }
            }, 900)
            return
          }

          if (performanceMode !== 'low' && data.question && typeof window !== 'undefined' && window.speechSynthesis) {
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
          intentionalCloseRef.current = true
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
    ws.onclose = () => {
      setWsConnected(false)
      if (!intentionalCloseRef.current && !interviewEndedRef.current) {
        setError('WebSocket bağlantısı beklenmedik şekilde kapandı')
      }
    }
    ws.onerror = () => {
      if (!intentionalCloseRef.current && !interviewEndedRef.current) {
        setError('WebSocket bağlantı hatası')
      }
    }
    wsRef.current = ws
  }, [id, interview?.domain, interview?.language, performanceMode, silentTestMode, questionNum])

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
        }, silenceWindowMs)
      }
    }
  }, [sendPendingAudio, silenceWindowMs])

>>>>>>> Stashed changes
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
    // Sayfa kapanırken stream varsa durdur
    return () => {
<<<<<<< Updated upstream
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
=======
      intentionalCloseRef.current = true
      stopSpeaking()
      if (wsRef.current) {
        try {
          if (wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.close()
          }
        } catch (e) { /* yoksay */ }
      }
      if (sendTimerRef.current) clearTimeout(sendTimerRef.current)
      if (autoAnswerTimerRef.current) clearTimeout(autoAnswerTimerRef.current)
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop() } catch { /* yoksay */ }
      }
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop())
      if (processorRef.current) { try { processorRef.current.disconnect() } catch { /* yoksay */ } }
      if (sourceRef.current) { try { sourceRef.current.disconnect() } catch { /* yoksay */ } }
      if (muteGainRef.current) { try { muteGainRef.current.disconnect() } catch { /* yoksay */ } }
      if (audioContextRef.current) { try { audioContextRef.current.close() } catch { /* yoksay */ } }
>>>>>>> Stashed changes
    }
  }, [])

  async function handleStart() {
    setError('')
    try {
<<<<<<< Updated upstream
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      })
=======
      const mediaConstraints = performanceMode === 'low'
        ? {
            video: {
              width: { ideal: 640 },
              height: { ideal: 360 },
              frameRate: { ideal: 15, max: 20 },
            },
            audio: !silentTestMode,
          }
        : {
            video: {
              width: { ideal: 1280 },
              height: { ideal: 720 },
              frameRate: { ideal: 30, max: 30 },
            },
            audio: !silentTestMode,
          }
      let stream
      try {
        stream = await navigator.mediaDevices.getUserMedia(mediaConstraints)
      } catch (mediaErr) {
        if (performanceMode === 'low') {
          console.warn('Low mode media constraints failed, falling back to default:', mediaErr)
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: !silentTestMode })
        } else {
          throw mediaErr
        }
      }
>>>>>>> Stashed changes
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
      }
<<<<<<< Updated upstream
      setCurrentIndex(0)
=======

      recordedChunksRef.current = []
      let recorder
      try {
        recorder = new MediaRecorder(stream, {
          mimeType: 'video/webm;codecs=vp8',
          videoBitsPerSecond: performanceMode === 'low' ? 450000 : 1500000,
        })
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
      if (!silentTestMode) {
        setTimeout(() => startAudioCapture(), 500)
      } else {
        setMicStatus('Sessiz test modu aktif')
      }
>>>>>>> Stashed changes
    } catch (e) {
      console.error('Media start error:', e)
      setError('Kamera ve mikrofon izni verilmedi. Mülakat başlatılamadı.')
    }
  }

<<<<<<< Updated upstream
  async function handleNext() {
    if (!interview?.questions) return
    const nextIndex = currentIndex + 1
    if (nextIndex < interview.questions.length) {
      setCurrentIndex(nextIndex)
    } else {
      // Mülakat bitti
      setFinishing(true)
=======
  async function stopAndUploadVideo() {
    if (uploading || interviewEnded) return
    intentionalCloseRef.current = true
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

>>>>>>> Stashed changes
      try {
        await fetch(`${API}/interviews/${id}/status`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ status: 'completed' }),
        })
      } catch {
        // hata olsa bile kullanıcıya çok yansıtma, loglamak yeter
      } finally {
        // Kamerayı kapat
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop())
        }
        setTimeout(() => {
          navigate(`/interview/${id}/sonuc`)
        }, 1500)
      }
    }
  }

  if (!token) return null
  if (loading) return <div style={{ padding: '2rem' }}>Yükleniyor...</div>
  if (error || !interview) return <div style={{ padding: '2rem', color: 'red' }}>{error || 'Mülakat bulunamadı'}</div>

  const questions = interview.questions || []
  const total = questions.length
  const currentQuestion = currentIndex >= 0 && currentIndex < total ? questions[currentIndex] : null

  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <header style={{
        background: '#fff',
        borderBottom: '1px solid #e5e7eb',
        padding: '0.75rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Link to="/dashboard" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111', textDecoration: 'none' }}>
          Mülakat Simülasyonu
        </Link>
        <span style={{ fontSize: '0.95rem', color: '#6b7280' }}>
          {interview.title}
        </span>
      </header>

      <main style={{ maxWidth: 960, margin: '0 auto', padding: '2rem 1.5rem', display: 'grid', gap: '1.5rem', gridTemplateColumns: '2fr 3fr' }}>
        {/* Sol: video alanı */}
        <section style={{ background: '#000', borderRadius: 12, overflow: 'hidden', minHeight: 240 }}>
          <video
            ref={videoRef}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            autoPlay
            muted
          />
        </section>

        {/* Sağ: sorular */}
        <section style={{ background: '#fff', borderRadius: 12, padding: '1.5rem' }}>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            Mülakat
          </h1>
          <p style={{ fontSize: '0.95rem', color: '#6b7280', marginBottom: '1rem' }}>
            Sorular sırayla gösterilecek. Her soruya kameraya bakarak yanıt ver.
          </p>

<<<<<<< Updated upstream
          {error && <p style={{ color: '#dc2626', fontSize: '0.9rem' }}>{error}</p>}
=======
          <div style={{ background: '#fff', borderRadius: 12, padding: '1.5rem', border: '1px solid #e5e7eb' }}>
            <h1 style={{ fontSize: '1.3rem', fontWeight: 600, marginBottom: '0.5rem' }}>Mülakat</h1>
            <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '0.75rem' }}>
              {silentTestMode
                ? 'Sessiz test modunda sorular otomatik olarak test cevabı ile ilerletilir.'
                : `Konuşmanızı algıladıktan ~${Math.round(silenceWindowMs / 1000)}sn sonra cevabınız otomatik gönderilir.`}
            </p>
>>>>>>> Stashed changes

          {currentIndex === -1 && (
            <>
              <p style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                Başlamadan önce kamera ve mikrofon izni isteyeceğiz.
              </p>
              <button
                type="button"
                onClick={handleStart}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#111',
                  color: '#fff',
                  borderRadius: 8,
                  border: 'none',
                  fontWeight: 500,
                  fontSize: '1rem',
                  cursor: 'pointer',
                }}
              >
                Mülakata başla
              </button>
            </>
          )}

<<<<<<< Updated upstream
          {currentIndex >= 0 && currentQuestion && (
            <>
              <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '0.5rem' }}>
                Soru {currentIndex + 1} / {total}
              </p>
              <div style={{ padding: '1rem', borderRadius: 8, background: '#f3f4f6', marginBottom: '1rem' }}>
                {currentQuestion.text}
              </div>
              <button
                type="button"
                onClick={handleNext}
                disabled={finishing}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#111',
                  color: '#fff',
                  borderRadius: 8,
                  border: 'none',
                  fontWeight: 500,
                  fontSize: '1rem',
                  cursor: finishing ? 'not-allowed' : 'pointer',
                  opacity: finishing ? 0.7 : 1,
                }}
              >
                {currentIndex === total - 1 ? 'Mülakatı bitir' : 'Sonraki soru'}
              </button>
              {finishing && (
                <p style={{ marginTop: '0.75rem', fontSize: '0.9rem', color: '#6b7280' }}>
                  Mülakat tamamlandı, sonuç sayfasına yönlendiriliyorsunuz…
=======
            {!recording && !interviewEnded && (
              <>
                <div style={{ marginBottom: '1rem', padding: '0.75rem', background: '#f9fafb', borderRadius: 8, border: '1px solid #e5e7eb' }}>
                  <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#4b5563', fontWeight: 600 }}>
                    Performans Modu
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      type="button"
                      onClick={() => setPerformanceMode('normal')}
                      style={{
                        padding: '0.45rem 0.8rem',
                        borderRadius: 8,
                        border: '1px solid #d1d5db',
                        background: performanceMode === 'normal' ? '#111' : '#fff',
                        color: performanceMode === 'normal' ? '#fff' : '#111',
                        cursor: 'pointer',
                      }}
                    >
                      Normal
                    </button>
                    <button
                      type="button"
                      onClick={() => setPerformanceMode('low')}
                      style={{
                        padding: '0.45rem 0.8rem',
                        borderRadius: 8,
                        border: '1px solid #d1d5db',
                        background: performanceMode === 'low' ? '#111' : '#fff',
                        color: performanceMode === 'low' ? '#fff' : '#111',
                        cursor: 'pointer',
                      }}
                    >
                      Düşük Kaynak
                    </button>
                  </div>
                  <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
                    {performanceMode === 'low'
                      ? 'Daha düşük video kalite ve daha seyrek ses gönderimi ile cihaz yükünü azaltır.'
                      : 'Standart kalite ve daha hızlı cevap akışı.'}
                  </p>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', fontSize: '0.9rem', color: '#374151' }}>
                  <input
                    type="checkbox"
                    checked={silentTestMode}
                    onChange={(e) => setSilentTestMode(e.target.checked)}
                  />
                  Sessiz test modu (konuşmadan otomatik cevapla)
                </label>
                <p style={{ marginBottom: '1rem', fontSize: '0.95rem' }}>
                  {silentTestMode
                    ? 'Başlamadan önce kamera izni isteyeceğiz. Mikrofon gerekmez.'
                    : 'Başlamadan önce kamera ve mikrofon izni isteyeceğiz.'}
>>>>>>> Stashed changes
                </p>
              )}
            </>
          )}

<<<<<<< Updated upstream
          {currentIndex >= 0 && !currentQuestion && (
            <p>Mülakat soruları yüklenemedi.</p>
          )}
=======
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
                  {!silentTestMode && (
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
                  )}
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
>>>>>>> Stashed changes
        </section>
      </main>
    </div>
  )
}

