import os
import json
import re
import logging
from typing import List, Dict

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)


def _ollama_chat(messages: list[dict], model: str | None = None):
    if not ollama:
        raise RuntimeError("Ollama python paketi yüklü değil")

    target_model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    host = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "").strip()
    options = {
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
        "top_p": float(os.getenv("OLLAMA_TOP_P", "0.9")),
        "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "300")),
    }

    if host and hasattr(ollama, "Client"):
        client = ollama.Client(host=host)
        return client.chat(model=target_model, messages=messages, options=options)
    return ollama.chat(model=target_model, messages=messages, options=options)


def _parse_questions_json(raw: str) -> List[Dict]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 3:
            raw = parts[1]
        raw = raw.replace("json", "", 1).strip()
    if "[" in raw and "]" in raw:
        a = raw.find("[")
        b = raw.rfind("]")
        if a != -1 and b != -1 and b > a:
            raw = raw[a : b + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    cleaned: List[Dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        cleaned.append({"text": text})
    return cleaned


def _salvage_questions_from_text(raw: str) -> List[Dict]:
    text = (raw or "").strip()
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[Dict] = []
    for ln in lines:
        if ln.startswith("#") or ln.startswith("**") and ln.endswith("**"):
            continue
        ln = re.sub(r"^\d+[\.\)]\s*", "", ln)
        ln = re.sub(r"^[-*]\s*", "", ln)
        ln = re.sub(r"^\*\*(.*?)\*\*:\s*", "", ln)
        ln = re.sub(r"^\*\*(.*?)\*\*\s*", "", ln)
        ln = " ".join(ln.split()).strip()
        if len(ln) >= 8 and ("?" in ln or len(ln.split()) >= 5):
            out.append({"text": ln})
    return out


def _text_wrong_language(text: str, language: str) -> bool:
    low = (text or "").lower()
    if language == "tr":
        return any(tok in low for tok in ["tell me", "could you", "what ", "describe ", "example"])
    return any(tok in low for tok in ["nasıl", "neden", "örnek", "mısın", "misin", "teşekkür", "merhaba"])


def _validate_questions(questions: List[Dict], language: str, n_questions: int) -> List[Dict]:
    cleaned: List[Dict] = []
    seen: set[str] = set()
    for item in questions:
        text = (item.get("text") or "").strip()
        if len(text) < 8:
            continue
        text = " ".join(text.split())
        norm = re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ ]+", "", text.lower())
        if norm in seen:
            continue
        if _text_wrong_language(text, language):
            continue
        seen.add(norm)
        cleaned.append({"text": text[:1024]})
        if len(cleaned) >= n_questions:
            break
    return cleaned


def generate_questions(
    *,
    position: str,
    company_name: str | None,
    department_name: str | None,
    domain: str,
    language: str,
    cv_text: str | None,
    profile_university: str | None,
    profile_department: str | None,
    profile_class_year: str | None,
    n_questions: int = 6,
) -> List[Dict]:
    if not ollama:
        logger.error("Ollama not available")
        return []

    trimmed_cv = (cv_text or "")[:3000]

    system_content = (
        "Sen bir mülakat asistanısın.\n"
        "- Verilen pozisyon, şirket, departman ve aday bilgilerine göre MÜLAKAT SORULARI üretirsin.\n"
        "- Sorular pozisyona ve adayın seviyesine uygun, net, tekrar etmeyen ve gerçekçi olmalıdır.\n"
        "- CEVABIN SADECE GEÇERLİ JSON LİSTESİ OLMALI.\n"
        "- Markdown code block, açıklama, başlık veya ek metin yazma.\n"
        '- Tam format: [{"text":"..."}]'
    )

    user_content = f"""
Pozisyon: {position}
Şirket: {company_name or '-'}
Departman: {department_name or '-'}
Kategori (domain): {domain}
Dil: {language}

Aday bilgileri (profil):
- Üniversite: {profile_university or '-'}
- Bölüm: {profile_department or '-'}
- Sınıf/Yıl: {profile_class_year or '-'}

Adayın CV metni (özet):
{trimmed_cv or '-'}

İSTEKLER:
- Toplam {n_questions} adet mülakat sorusu üret.
- Eğer domain TEKNİK ise:
  - Soruların TAMAMI teknik olsun (programlama, veri yapıları, veritabanı, kullanılan teknolojiler, projeler vb.).
- Eğer domain GENEL / DAVRANIŞSAL ise:
  - Soruların TAMAMI davranışsal / soft-skill odaklı olsun (takım çalışması, iletişim, zorluklarla başa çıkma, geri bildirim, motivasyon vb.).
- Sorular DİL alanına göre yazılsın (örneğin 'tr' ise tamamen Türkçe).

ÇIKTI FORMATIN:
Sadece aşağıdaki yapıda GEÇERLİ BİR JSON LİSTESİ döndür:

[
  {{
    "text": "Soru metni burada"
  }},
  ...
]

JSON dışında hiçbir şey yazma.
"""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    try:
        response = _ollama_chat(messages=messages, model=model_name)
        raw_text = response.get("message", {}).get("content", "") or "[]"
        parsed = _parse_questions_json(raw_text)
        if not parsed:
            parsed = _salvage_questions_from_text(raw_text)
        valid = _validate_questions(parsed, language, n_questions)
        if valid:
            return valid
        logger.warning("Ollama invalid question output (try1): %s", raw_text[:300])
    except Exception as e:
        logger.error(f"OLLAMA QUESTION GENERATION ERROR (try1): {repr(e)}")

    repair_messages = messages + [
        {
            "role": "user",
            "content": (
                f"Önceki çıktı geçersizdi. Şimdi SADECE geçerli JSON döndür.\n"
                f"Tam olarak {n_questions} öğe üret.\n"
                'Format: [{"text":"..."}]\n'
                "JSON dışında tek kelime bile yazma."
            ),
        }
    ]
    try:
        response2 = _ollama_chat(messages=repair_messages, model=model_name)
        raw2 = response2.get("message", {}).get("content", "") or "[]"
        parsed2 = _parse_questions_json(raw2)
        if not parsed2:
            parsed2 = _salvage_questions_from_text(raw2)
        valid2 = _validate_questions(parsed2, language, n_questions)
        if valid2:
            return valid2
        logger.warning("Ollama invalid question output (try2): %s", raw2[:300])
        return []
    except Exception as e:
        logger.error(f"OLLAMA QUESTION GENERATION ERROR (try2): {repr(e)}")
        return []


def fallback_questions(domain: str, language: str, n: int) -> List[Dict]:
    tr_general = [
        "Kendinizi ve bugüne kadarki eğitim/deneyim yolculuğunuzu kısaca anlatır mısınız?",
        "Takım içinde yaşadığınız bir anlaşmazlığı nasıl yönettiğinize dair somut bir örnek verebilir misiniz?",
        "Zor bir hedefe yetişmek için önceliklendirmeyi nasıl yaptığınızı anlatır mısınız?",
        "Aldığınız en zor geri bildirim neydi ve bununla nasıl gelişim sağladınız?",
        "Bu pozisyon için sizi öne çıkaran güçlü yönünüz nedir?",
        "Bu role başlarsanız ilk 90 günde hangi katkıları sunmayı hedeflersiniz?",
    ]
    tr_technical = [
        "Son dönemde geliştirdiğiniz bir projeyi teknik mimarisiyle anlatır mısınız?",
        "Bir performans darboğazını nasıl tespit edip iyileştirdiğinize örnek verebilir misiniz?",
        "Bir hata/incident sonrası root-cause analizini nasıl yürüttünüz?",
        "Veritabanı tasarımında ölçeklenebilirlik için hangi kararları aldınız?",
        "Kod kalitesini korumak için ekip içinde hangi pratikleri uyguluyorsunuz?",
        "Yeni bir teknolojiye hızlı adapte olduğunuz bir örnek paylaşır mısınız?",
    ]
    en_general = [
        "Could you briefly introduce yourself and your relevant background?",
        "Tell me about a time you handled a conflict within a team.",
        "How do you prioritize when several deadlines collide?",
        "What is the toughest feedback you have received, and how did you use it?",
        "What is your strongest value for this role?",
        "If you joined this role, what impact would you target in your first 90 days?",
    ]
    en_technical = [
        "Can you walk me through a recent project and its technical architecture?",
        "Describe a performance bottleneck you identified and fixed.",
        "Tell me about a production issue and how you performed root-cause analysis.",
        "How do you make database design decisions for scalability?",
        "What engineering practices do you use to keep code quality high?",
        "Share an example of learning a new technology quickly for delivery.",
    ]

    is_technical = (domain or "").lower() == "technical"
    is_en = (language or "").lower() == "en"
    pool = en_technical if (is_en and is_technical) else (
        en_general if is_en else (tr_technical if is_technical else tr_general)
    )
    return [{"text": q} for q in pool[: max(1, min(n, len(pool)))]]


def chat_response(transcript: str, summary: str, strengths: str, improvements: str, user_message: str, language: str = "tr") -> str:
    if not ollama:
        return f"Geri bildiriminize göre: {summary or 'Henüz analiz yok.'}"

    try:
        lang_instruction = "Kısa, yapıcı ve TÜRKÇE yanıt ver." if language == "tr" else "Reply briefly and helpfully in ENGLISH."
        system_content = (
            f"Sen bir mülakat koçusun. {lang_instruction}"
        )
        user_content = (
            f"Geri bildirim özeti: {summary}\nGüçlü yönler: {strengths}\nGelişim: {improvements}\n\n"
            f"Konuşma metni (transcript): {transcript[:2000] if transcript else 'Yok'}\n\n"
            f"Kullanıcı soruyor: {user_message}"
        )
        response = _ollama_chat(
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
        )
        return response.get("message", {}).get("content", "") or "Yanıt oluşturulamadı."
    except Exception as e:
        logger.error(f"Ollama chat error: {e}")
        return (
            f"AI yanıtı alınamadı. Özet: {summary or 'Henüz analiz yok.'} "
            f"Gelişim: {improvements or '—'}"
        )
