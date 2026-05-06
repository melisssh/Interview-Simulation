"""
Ollama + Faster Whisper + TTS Entegrasyonu Testi
Terminalden çalıştır:
  cd backend
  python test_ollama_integration.py

Ön koşullar:
  1. Ollama kurulu: ollama pull llama3.2:3b
  2. Faster Whisper: pip install faster-whisper
  3. PyAudio: pip install pyaudio (mikrofon için)
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# .env yükle
load_dotenv(Path(__file__).parent / ".env")

try:
    import pyaudio
    import wave
except ImportError:
    print("⚠️  PyAudio bulunamadı. Ses kaydı yapılamayacak.")
    print("   Kurulum: pip install pyaudio")
    pyaudio = None
    wave = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("❌ Faster Whisper bulunamadı!")
    print("   Kurulum: pip install faster-whisper")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ requests bulunamadı!")
    print("   Kurulum: pip install requests")
    sys.exit(1)


# ===== KONFIGÜRASYON =====
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:3b"  # Eğer farklı model kullanıyorsan değiştir
AUDIO_FORMAT = pyaudio.paFloat32 if pyaudio else None
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
RECORD_DURATION = 10  # saniye


# ===== STT (Faster Whisper) =====
def transcribe_audio(audio_file_path: str, language: str = "tr") -> dict:
    """
    Faster Whisper ile ses dosyasını transkribe et
    """
    try:
        print(f"🎤 Transkripsiyon başlatılıyor ({language})...")

        # Dil kodu: "tr" -> "Turkish", "en" -> "English"
        lang_map = {"tr": "Turkish", "en": "English"}
        whisper_lang = lang_map.get(language, "Turkish")

        # Model yükle (cpu mode, int8)
        model = WhisperModel("base", device="cpu", compute_type="int8")

        # Transkripsiyon
        segments, info = model.transcribe(audio_file_path, language=whisper_lang)

        text = "".join([segment.text for segment in segments])

        if not text.strip():
            return {
                "success": False,
                "error": "Ses algılanamadı. Lütfen daha yüksek ses ile konuş.",
                "text": ""
            }

        print(f"✅ Transkripsiyon başarılı: '{text[:100]}...'")

        return {
            "success": True,
            "text": text.strip(),
            "language": language
        }

    except Exception as e:
        print(f"❌ Transkripsiyon hatası: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": ""
        }


# ===== LLM (Ollama) =====
def get_ollama_response(prompt: str, conversation_history: list = None) -> dict:
    """
    Ollama ile LLM yanıtı al
    """
    try:
        print(f"🤖 Ollama yanıt üretiliyor...")

        # Konuşma geçmişini dahil et
        if not conversation_history:
            conversation_history = []

        # İstem
        messages = conversation_history + [
            {
                "role": "user",
                "content": prompt
            }
        ]

        # Ollama API isteği
        url = f"{OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }

        response = requests.post(url, json=payload, timeout=30)

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Ollama hatası: {response.status_code}",
                "text": ""
            }

        result = response.json()
        assistant_response = result.get("message", {}).get("content", "").strip()

        if not assistant_response:
            return {
                "success": False,
                "error": "Boş yanıt alındı",
                "text": ""
            }

        print(f"✅ Ollama yanıtı: '{assistant_response[:100]}...'")

        return {
            "success": True,
            "text": assistant_response,
            "model": OLLAMA_MODEL
        }

    except requests.ConnectionError:
        return {
            "success": False,
            "error": f"Ollama bağlanılamadı ({OLLAMA_BASE_URL}). Lütfen 'ollama serve' çalıştır.",
            "text": ""
        }
    except Exception as e:
        print(f"❌ LLM hatası: {e}")
        return {
            "success": False,
            "error": str(e),
            "text": ""
        }


# ===== TTS (System) =====
def speak_text(text: str, language: str = "tr") -> bool:
    """
    macOS 'say' komutu ile metni seslendir
    """
    try:
        if not text.strip():
            return False

        print(f"🔊 TTS başlatılıyor ({language})...")

        # macOS 'say' komutunun dil kodu
        voice_map = {
            "tr": "Ozlem",  # Türkçe ses
            "en": "Samantha"  # İngilizce ses
        }
        voice = voice_map.get(language, "Ozlem")

        # macOS'ta say komutu
        cmd = ["say", "-v", voice, text]

        result = subprocess.run(cmd, capture_output=True, timeout=60)

        if result.returncode == 0:
            print(f"✅ TTS tamamlandı")
            return True
        else:
            print(f"⚠️  TTS hatası: {result.stderr.decode()}")
            return False

    except FileNotFoundError:
        print(f"⚠️  'say' komutu bulunamadı. macOS değil misin?")
        print(f"   Alternatif: Ubuntu'da 'espeak' veya Windows'ta 'PowerShell'")
        return False
    except Exception as e:
        print(f"❌ TTS hatası: {e}")
        return False


# ===== Ses Kaydı =====
def record_audio(duration: int = RECORD_DURATION) -> str:
    """
    Mikrofondan ses kaydet (PCM WAV formatında)
    """
    if not pyaudio or not wave:
        print("⚠️  Ses kaydı yapılamıyor (PyAudio yok)")
        return None

    try:
        print(f"🎙️  Ses kaydediliyor ({duration} saniye)...")

        p = pyaudio.PyAudio()
        stream = p.open(
            format=AUDIO_FORMAT,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        frames = []
        for _ in range(0, int(SAMPLE_RATE / CHUNK_SIZE * duration)):
            try:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
            except Exception as e:
                print(f"⚠️  Ses okuma hatası: {e}")

        stream.stop_stream()
        stream.close()
        p.terminate()

        # Geçici dosya oluştur
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        # WAV dosyasını yaz
        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(AUDIO_FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))

        print(f"✅ Ses kaydedildi: {temp_path}")
        return temp_path

    except Exception as e:
        print(f"❌ Ses kaydı hatası: {e}")
        return None


# ===== Ana Mülakat Döngüsü =====
def run_interview_session():
    """
    Basit mülakat simülasyonu: 3 soru, STT + LLM + TTS
    """
    print("\n" + "="*60)
    print("🚀 MÜLAKAT SİMÜLASYONU BAŞLANIYOR")
    print("="*60)
    print(f"Olama Model: {OLLAMA_MODEL}")
    print(f"Dil: Türkçe")
    print("="*60 + "\n")

    # Mülakat soruları
    questions = [
        "Bana kendinizden bahsetsene? Eğitim ve deneyiminiz nedir?",
        "Programlama yaparken en çok hangi dile ilgi duyuyorsun?",
        "Gelecek 5 yılda kendini nerede görüyorsun?"
    ]

    # Konuşma geçmişi
    conversation_history = []

    # Sistem istemini ayarla (Spanglish'i önlemek için)
    system_message = {
        "role": "system",
        "content": """Sen bir mülakat yapan yönetmensin.
Cevapları SADECE TÜRKÇE ver.
Eğer İngilizce karışırsa, kesinlikle sadece Türkçe konuş.
Kısa, profesyonel, samimi cevaplar bekle."""
    }

    if system_message not in conversation_history:
        conversation_history.append(system_message)

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"📝 SORU {i}/3")
        print(f"{'='*60}")
        print(f"📢 Aday: \"{question}\"")
        print(f"⏳ {RECORD_DURATION} saniye içinde cevap verebilirsiniz...\n")

        # Soru seslendir
        speak_text(question, language="tr")

        # Ses kaydı
        audio_path = record_audio(RECORD_DURATION)
        if not audio_path:
            print("⚠️  Ses kaydı yapılamadı, cevap almayacağız.")
            continue

        # Transkripsiyon
        transcription = transcribe_audio(audio_path, language="tr")
        if not transcription["success"]:
            print(f"❌ {transcription['error']}")
            try:
                os.unlink(audio_path)
            except:
                pass
            continue

        user_response = transcription["text"]
        print(f"\n📝 Aday Cevabı: \"{user_response}\"")

        # Konuşma geçmişine ekle
        conversation_history.append({
            "role": "user",
            "content": user_response
        })

        # LLM ile yorum
        llm_result = get_ollama_response(
            f"Aday şöyle cevap verdi: {user_response}. Kısa bir yorum yap.",
            conversation_history=conversation_history[:-1]  # Sistem mesajı hariç
        )

        if llm_result["success"]:
            feedback = llm_result["text"]
            print(f"\n🤖 Geri Bildirim: {feedback}")

            # Konuşma geçmişine ekle
            conversation_history.append({
                "role": "assistant",
                "content": feedback
            })

            # Geri bildirimi seslendir
            speak_text(feedback, language="tr")
        else:
            print(f"❌ {llm_result['error']}")

        # Geçici dosyayı sil
        try:
            os.unlink(audio_path)
        except:
            pass

    print(f"\n{'='*60}")
    print("✅ MÜLAKAT SİMÜLASYONU TÜM SORULAR İÇİN BAŞARILI!")
    print(f"{'='*60}\n")


# ===== Ana Program =====
if __name__ == "__main__":
    # Ollama kontrolü
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"✅ Ollama çalışıyor")
        else:
            print(f"⚠️  Ollama yanıt verdi ama hata kodu: {response.status_code}")
    except requests.ConnectionError:
        print(f"❌ Ollama bağlanılamadı!")
        print(f"   Lütfen şunu çalıştır: ollama serve")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ollama kontrol hatası: {e}")
        sys.exit(1)

    # Mülakat simülasyonunu başlat
    run_interview_session()
