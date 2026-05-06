"""
Groq STT testi — terminalden çalıştır:
  cd backend
  python test_stt.py
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

# .env yükle
load_dotenv(Path(__file__).parent / ".env")

# Groq key kontrolü
key = os.environ.get("GROQ_API_KEY", "")
if not key:
    print("❌ GROQ_API_KEY .env dosyasında bulunamadı!")
    sys.exit(1)
print(f"✅ GROQ_API_KEY bulundu: {key[:8]}...")

# Mevcut bir video dosyası seç
uploads = Path(__file__).parent / "uploads" / "interviews"
video = None
for f in sorted(uploads.rglob("*.webm")):
    video = str(f)
    break

if not video:
    print("⚠️  uploads/interviews/ altında .webm dosyası yok.")
    print("   Lütfen önce bir mülakat kaydı yapın veya video_path'i manuel girin.")
    sys.exit(1)

print(f"\n🎬 Test videosu: {video}")
print("⏳ STT çalıştırılıyor (Groq)...\n")

from app.analysis.stt import get_transcript
result = get_transcript(interview_id=0, video_path=video)

print("=" * 50)
print(f"📝 Transkript  : {result['text'][:200]}...")
print(f"🌍 Dil         : {result['language']}")
print(f"⏱  Süre        : {result['duration_seconds']} sn")
print(f"🗣  Konuşma hızı: {result['speaking_rate_wpm']} kelime/dak")
print(f"⏸  Duraklama   : {result['long_pause_count']} uzun duraklama")
if result['pauses']:
    for p in result['pauses'][:3]:
        print(f"   → {p['start']}s – {p['end']}s  ({p['duration']}s)")
print(f"🔁 Fallback    : {result['fallback_reason']}")
print("=" * 50)
