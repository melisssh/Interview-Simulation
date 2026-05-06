# 🎯 MÜLAKAT SİSTEMİ - TAM AKIŞ

## 📊 SİSTEM BÖLÜMLERI

### 1️⃣ **INTERVIEW CREATION (REST API)**

**Path:** `POST /interviews`

**Frontend → Backend:**
```json
{
  "title": "Backend mülakat",
  "domain": "general",           // "general" veya "technical"
  "language": "tr",              // "tr" veya "en"
  "company_name": "Trendyol",
  "department_name": "Backend",
  "position": "Backend Dev"
}
```

**Backend Yapıyor:**
1. User profili kontrol (CV lazım) → 400 Error yoksa
2. Interview tablosuna kaydet
3. `generate_questions_with_ai()` çağrı
4. Ollama'ya sor: "5-7 soru oluştur"
5. Sorular JSON parse ediliyor
6. `InterviewQuestion` tablosuna kaydet
7. Response: `{"id": 123, ...}`

**Frontend:**
- "Oluşturuluyor..." loading göster (2-5 saniye)
- Hata? Error message göster
- Başarılı? `/interview/123` (detail sayfası)

---

### 2️⃣ **REAL-TIME INTERVIEW (WebSocket)**

**Path:** `WS /ws/interview/123`

**Flow:**

```
1. Frontend WebSocket aç
   ↓
2. {"type": "init", "domain": "general", "max_questions": 5}
   Backend Ollama: ilk soruyu oluştur
   ← {"type": "question", "question": "...", "q_num": 1}
   ↓
3. User cevap veriyor (microphone)
   Frontend audio kaydı başlat
   ↓
4. {"type": "audio", "audio": "base64_wav"}
   Backend:
     - Audio → Faster Whisper → Transkripsiyon
     - Transkripsiyon + history → Ollama
     - Ollama yeni soru oluştur
   ← {"type": "question", "question": "...", "q_num": 2}
   ↓
5. Repeat 3-4 (5 soruya kadar)
   ↓
6. 5. soru bitti
   ← {"type": "ended"}
   Frontend: Sonuç sayfasına git
```

---

## ⚙️ **BACKEND AYARLARI**

### `.env` Dosyası
```bash
# ✅ Zorunlu:
DATABASE_URL=postgresql+psycopg://...
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
FRONTEND_BASE_URL=http://localhost:5173

# ⚠️ Problem varsa kontrol et:
# - DATABASE_URL doğru mu? (Supabase)
# - OLLAMA çalışıyor mu? (localhost:11434)
# - FRONTEND_BASE_URL doğru mu?
```

### Python Dependencies
```bash
# ✅ Var olması lazım:
ollama>=0.1.0              # Ollama API
faster-whisper>=1.0.0      # STT
scipy                      # Audio
sounddevice               # Microphone
```

---

## 🖥️ **FRONTEND AYARLARI**

### `.env.local` Dosyası
```bash
VITE_API_URL=http://localhost:8000
```

**Kontrolü:**
```bash
cat frontend/.env.local | grep VITE_API_URL
# Çıkmalı: VITE_API_URL=http://localhost:8000
```

---

## 🧪 **TESTING CHECKLIST**

### ✅ Ön Hazırlık

- [ ] Ollama çalışıyor mı?
  ```bash
  curl http://localhost:11434/api/tags
  # JSON döndürmeli, hata yok
  ```

- [ ] Model var mı?
  ```bash
  ollama list | grep llama3.2
  # llama3.2:3b görülmeli
  ```

- [ ] .env dosyası doğru mu?
  ```bash
  grep OLLAMA backend/.env
  # OLLAMA_BASE_URL=http://localhost:11434
  # OLLAMA_MODEL=llama3.2:3b
  ```

### ✅ Backend Test

- [ ] Backend başlıyor mı?
  ```bash
  cd backend
  python -m uvicorn app.main:app --reload
  # INFO: Uvicorn running on http://0.0.0.0:8000
  ```

- [ ] Database bağlantısı OK?
  ```bash
  curl http://localhost:8000/categories
  # JSON array döndürmeli
  ```

### ✅ Frontend Test

- [ ] Frontend başlıyor mı?
  ```bash
  cd frontend
  npm run dev
  # Local: http://localhost:5173
  ```

- [ ] http://localhost:5173 yüklendiğinde login sayfası görünüyor mü?

### ✅ Login & Profile

- [ ] Yeni kullanıcı oluşturabildin mi?
  - Email: test@example.com
  - Password: password123

- [ ] Dashboard açıldı mı?

- [ ] Profil sayfasından CV yükleyebildin mi?
  - Herhangi bir dosya (PDF, Word, etc.)

### ✅ Mülakat Oluşturma

- [ ] "Yeni mülakat" formunu doldurabildin mi?
  - Başlık: "Test"
  - Kategori: "general"
  - Dil: "tr"
  - Şirket: "Test"
  - Departman: "Test"
  - Pozisyon: "Test"

- [ ] "Mülakatı başlat" butonuna bastığında "Oluşturuluyor..." yazı görünüyor mu?

- [ ] 2-5 saniye sonra detay sayfası açıldı mı?

- [ ] Sorular göründü mü? (5-7 soru)

### ✅ Real-Time Mülakat

- [ ] WebSocket açıldı mı? (Browser Console F12 → Network → WS)

- [ ] Mikrofon izni sorusu geldi mi?

- [ ] "Dinliyorum..." butonu göründü mü?

- [ ] Ses kaydedilebildi mi? (konuş, sesli oku)

- [ ] Transkripsiyon göründü mü?

- [ ] Yeni soru oluştu mu?

- [ ] 5 soru bitti mi?

- [ ] Sonuç sayfasına gitti mi?

---

## 🚨 **HATA GİDERME**

### Error: "Mülakat soruları oluşturulamadı"

**Nedeni:** Ollama yanıt vermiyor

**Çözüm:**
```bash
# 1. Ollama çalışıyor mu?
curl http://localhost:11434/api/tags

# 2. Model yüklü mü?
ollama list

# 3. Ollama test et
curl -X POST http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2:3b",
    "messages": [{"role": "user", "content": "Merhaba"}]
  }'
```

### Error: "WebSocket connection failed"

**Nedeni:** Backend WebSocket desteği yok

**Çözüm:**
```bash
# Backend logs'unu kontrol et
# Terminal'de hata var mı?
# WS bağlantısı kabul ediliyor mu?
```

### Error: "Mikrofon erişimi reddedildi"

**Nedeni:** Browser izni yok

**Çözüm:**
- Settings → Privacy → Microphone → Allow
- Sayfayı yenile (F5)

### Error: "Audio kaydı başarısız"

**Nedeni:** sounddevice kurulu değil

**Çözüm:**
```bash
pip install --break-system-packages sounddevice
```

---

## 📝 **ÖZET: MÜLAKAT AKIŞI**

```
USER: http://localhost:5173 aç
  ↓
  Login / Register
  ↓
  Dashboard
  ↓
  "Yeni mülakat" → Form doldur
  ↓
BACKEND: Ollama → 5-7 soru oluştur
  ↓
  Interview detail sayfası (sorular göster)
  ↓
  "Mülakatı başlat"
  ↓
WEBSOCKET: Real-time interview
  ↓
  1. Audio kaydı
  2. STT (Faster Whisper)
  3. LLM (Ollama) yeni soru
  4. Repeat 5x
  ↓
  Sonuç sayfası
```

---

## ✅ **PRODUCTION READY**

- ✅ Tüm eski API'ler silinmiş
- ✅ Pure Ollama (local, free)
- ✅ WebSocket real-time
- ✅ Faster Whisper STT
- ✅ System TTS
- ✅ Error handling
- ✅ Database integrasyon

---

**DURUM: ✅ Hazır!**

Şimdi test et! 👍
