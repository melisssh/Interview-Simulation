"""
Ollama + Faster Whisper + TTS Mülakat Sistemi
Türkçe/İngilizce desteği, Spanglish önlemesi
"""

import sounddevice as sd
import scipy.io.wavfile as wav
import subprocess
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# .env yükle
load_dotenv(Path(__file__).parent / ".env")

try:
    from faster_whisper import WhisperModel
    print("✅ Faster Whisper yüklü")
except ImportError:
    print("❌ Faster Whisper yok: pip install faster-whisper")
    sys.exit(1)

try:
    import ollama
    print("✅ Ollama Python kütüphanesi yüklü")
except ImportError:
    print("❌ Ollama kütüphanesi yok: pip install ollama")
    sys.exit(1)

try:
    import sounddevice
    print("✅ sounddevice yüklü")
except ImportError:
    print("❌ sounddevice yok: pip install sounddevice scipy")
    sys.exit(1)


# ===== KONFIGÜRASYON =====
OLLAMA_MODEL = "llama3.2:3b"
AUDIO_FORMAT = "float32"
SAMPLE_RATE = 16000
RECORD_DURATION = 10
TEMP_AUDIO_FILE = "cevap.wav"

# React Frontend'den gelecek form verileri (test için)
form_verileri = {
    "full_name": "Selin",
    "university": "Yıldız Teknik Üniversitesi",
    "department": "Bilgisayar Mühendisliği",
    "class_year": "4",
    "domain": "Yazılım Geliştirme",
    "language": "tr",  # "tr" veya "en"
    "companyName": "Trendyol",
    "departmentName": "Core Backend Ekibi",
    "position": "Backend Developer"
}

print("\n" + "="*60)
print("🎤 MÜLAKAT SİSTEMİ - OLLAMA + WHISPER + TTS")
print("="*60)
print(f"Model: {OLLAMA_MODEL}")
print(f"Aday: {form_verileri['full_name']}")
print(f"Dil: {'Türkçe' if form_verileri['language'] == 'tr' else 'English'}")
print("="*60 + "\n")


# ===== STT (Faster Whisper) =====
def transcribe_audio(audio_file: str, language: str = "tr") -> str:
    """
    Ses dosyasını transkribe et
    """
    try:
        lang_map = {"tr": "Turkish", "en": "English"}
        whisper_lang = lang_map.get(language, "Turkish")

        print(f"   📝 Transkripsiyon ({whisper_lang})...", end="", flush=True)

        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_file, language=whisper_lang)

        text = "".join([segment.text for segment in segments]).strip()

        if text:
            print(f" ✅")
            return text
        else:
            print(f" ⚠️ (Ses algılanmadı)")
            return ""

    except Exception as e:
        print(f" ❌ ({e})")
        return ""


# ===== TTS (System) =====
def sesli_konus(metin: str, dil: str = "tr") -> bool:
    """
    macOS say komutu ile seslendir
    """
    try:
        if not metin.strip():
            return False

        ses_map = {
            "tr": "Yelda",      # Türkçe
            "en": "Samantha"    # İngilizce
        }
        voice = ses_map.get(dil, "Yelda")

        print(f"\n🔊 İK Uzmanı: \"{metin[:80]}...\"")

        # macOS
        subprocess.run(
            ["say", "-v", voice, metin],
            check=True,
            timeout=60,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL
        )
        return True

    except FileNotFoundError:
        print(f"   ⚠️  'say' komutu bulunamadı (macOS değil mi?)")
        print(f"   → Yazı olarak gösteriliyor: {metin[:100]}...")
        return False
    except Exception as e:
        print(f"   ⚠️  TTS hatası: {e}")
        return False


# ===== Ses Kaydı =====
def ses_kaydet(sure: int = RECORD_DURATION, dosya: str = TEMP_AUDIO_FILE) -> bool:
    """
    Mikrofondan ses kaydet
    """
    try:
        fs = SAMPLE_RATE
        print(f"\n🎙️  Dinliyorum ({sure} saniye)...", end="", flush=True)

        # Ses kayıt
        recording = sd.rec(int(sure * fs), samplerate=fs, channels=1, dtype=AUDIO_FORMAT)
        sd.wait()

        # WAV dosyasına yaz
        wav.write(dosya, fs, recording)

        print(f" ✅")
        return True

    except Exception as e:
        print(f" ❌ ({e})")
        return False


# ===== Ollama LLM =====
def ollama_cevap_al(konusma_gecmisi: list) -> str:
    """
    Ollama'dan LLM yanıtı al
    """
    try:
        print(f"   🤖 Ollama düşünüyor...", end="", flush=True)

        response = ollama.chat(model=OLLAMA_MODEL, messages=konusma_gecmisi)
        ai_cevap = response.get("message", {}).get("content", "").strip()

        if ai_cevap:
            print(f" ✅")
            return ai_cevap
        else:
            print(f" ⚠️ (Boş cevap)")
            return ""

    except ConnectionRefusedError:
        print(f" ❌")
        print(f"\n❌ Ollama'ya bağlanılamadı!")
        print(f"   Lütfen başka bir terminal'de çalıştır: ollama serve")
        return ""
    except Exception as e:
        print(f" ❌ ({e})")
        return ""


# ===== Ana Mülakat Döngüsü =====
def mulakati_baslat():
    """
    Tam mülakat simülasyonu
    """
    dil = form_verileri['language']

    # Dile göre sistem talimatı
    if dil == "tr":
        sistem_talimati = f"""
Sen {form_verileri['companyName']} şirketinin İnsan Kaynakları Uzmanısın.
Aday: {form_verileri['full_name']}, {form_verileri['department']}, {form_verileri['class_year']}. sınıf.
Pozisyon: {form_verileri['position']}

KESİN KURALLAR:
1. %100 TÜRKÇE KONUŞ! Tek bir İngilizce kelime kullanma.
2. Adayın cevabını dinle, mantıklı bir mülakat sorusu sor.
3. Soruları kısa, açık ve profesyonel tut.
4. Her sorudan sonra cevaba göre geri bildirim ver.
"""
        ilk_soru = f"Merhaba {form_verileri['full_name']}, {form_verileri['companyName']} mülakatına hoş geldin. Lütfen bize kendinden ve eğitiminden bahsetsene?"

    else:
        sistem_talimati = f"""
You are an HR Specialist at {form_verileri['companyName']}.
Candidate: {form_verileri['full_name']}, {form_verileri['department']}, Year {form_verileri['class_year']}.
Position: {form_verileri['position']}

STRICT RULES:
1. SPEAK ONLY IN ENGLISH! No Turkish words.
2. Listen to the candidate's answer and ask one logical follow-up question.
3. Keep questions short, clear, and professional.
4. Give feedback based on their answer.
"""
        ilk_soru = f"Hello {form_verileri['full_name']}, welcome to the {form_verileri['companyName']} interview. Could you tell us about yourself and your background?"

    # Konuşma geçmişi başlat
    konusma_gecmisi = [
        {'role': 'system', 'content': sistem_talimati}
    ]

    print(f"\n{'='*60}")
    print(f"Mülakat Başlamak Üzere...")
    print(f"{'='*60}\n")

    # İlk soruyu sor
    sesli_konus(ilk_soru, dil)
    konusma_gecmisi.append({'role': 'assistant', 'content': ilk_soru})

    # 3 tur mülakat
    for tur in range(1, 4):
        print(f"\n{'─'*60}")
        print(f"SORU {tur}/3")
        print(f"{'─'*60}")

        # Ses kaydet
        if not ses_kaydet(RECORD_DURATION):
            print("⚠️  Ses kaydı başarısız, devam ediliyor...")
            continue

        # Transkribe et
        user_text = transcribe_audio(TEMP_AUDIO_FILE, dil)

        if not user_text:
            print(f"\n⚠️  Ses algılanamadı, lütfen daha yüksek ses ile konuş.")
            continue

        # Aday cevabını göster
        print(f"\n😊 {form_verileri['full_name']}: \"{user_text}\"")

        # Konuşma geçmişine ekle
        konusma_gecmisi.append({'role': 'user', 'content': user_text})

        # Ollama'dan yanıt al
        ai_cevap = ollama_cevap_al(konusma_gecmisi)

        if not ai_cevap:
            print(f"\n❌ Ollama yanıt veremedi, devam ediliyor...")
            continue

        # AI cevabını seslendir
        sesli_konus(ai_cevap, dil)

        # Konuşma geçmişine ekle
        konusma_gecmisi.append({'role': 'assistant', 'content': ai_cevap})

    # Mülakat bitişi
    print(f"\n\n{'='*60}")
    print("✅ MÜLAKAT BAŞARILI TAMAMLANDI!")
    print(f"{'='*60}")

    # Geçici dosyayı sil
    try:
        if os.path.exists(TEMP_AUDIO_FILE):
            os.remove(TEMP_AUDIO_FILE)
    except:
        pass


# ===== Ana Program =====
if __name__ == "__main__":
    print("\n⏳ Whisper modeli yükleniyor (ilk sefer yavaş olabilir)...")

    # Modeli önceden yükle
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        print("✅ Whisper modeli hazır\n")
    except Exception as e:
        print(f"❌ Whisper modeli yüklenemedi: {e}")
        sys.exit(1)

    # Mülakat başlat
    mulakati_baslat()
