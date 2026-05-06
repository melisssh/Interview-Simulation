#!/bin/bash

# MÜLAKAT SİSTEMİ TEST SCRIPT

echo "======================================"
echo "🧪 MÜLAKAT SISTEMI TEST"
echo "======================================"
echo ""

# Test 1: Ollama
echo "1️⃣ Ollama Kontrol..."
echo "   curl http://localhost:11434/api/tags"
curl -s http://localhost:11434/api/tags > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✅ Ollama çalışıyor"
else
  echo "   ❌ Ollama çalışmıyor!"
  echo "   → Çalıştır: ollama serve"
  exit 1
fi
echo ""

# Test 2: Model
echo "2️⃣ Model Kontrol..."
echo "   ollama list"
ollama list | grep llama3.2 > /dev/null
if [ $? -eq 0 ]; then
  echo "   ✅ llama3.2 model var"
else
  echo "   ❌ llama3.2 yok!"
  echo "   → Çalıştır: ollama pull llama3.2:3b"
  exit 1
fi
echo ""

# Test 3: Python Ollama
echo "3️⃣ Python Ollama Test..."
python3 << 'EOF'
try:
    import ollama
    response = ollama.chat(
        model="llama3.2:3b",
        messages=[{"role": "user", "content": "Merhaba"}]
    )
    print("   ✅ Python ollama çalışıyor")
except Exception as e:
    print(f"   ❌ Hata: {e}")
    exit(1)
EOF
echo ""

# Test 4: .env
echo "4️⃣ .env Kontrolü..."
if grep -q "OLLAMA_MODEL=llama3.2:3b" backend/.env; then
  echo "   ✅ .env ayarları OK"
else
  echo "   ❌ .env değişkenleri yanlış!"
  exit 1
fi
echo ""

# Test 5: Dependencies
echo "5️⃣ Python Paketleri..."
python3 -c "import ollama; import faster_whisper; import scipy; print('   ✅ Tüm paketler yüklü')" 2>/dev/null || {
  echo "   ❌ Paketler eksik!"
  echo "   → Çalıştır: pip install -r backend/requirements.txt --break-system-packages"
  exit 1
}
echo ""

echo "======================================"
echo "✅ TÜM TESTLER BAŞARILI!"
echo "======================================"
echo ""
echo "Şimdi şu komutları çalıştır:"
echo ""
echo "Terminal 1:"
echo "  ollama serve"
echo ""
echo "Terminal 2:"
echo "  cd backend && python -m uvicorn app.main:app --reload"
echo ""
echo "Terminal 3:"
echo "  cd frontend && npm run dev"
echo ""
echo "Sonra http://localhost:5173 aç"
