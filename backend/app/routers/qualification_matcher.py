"""
Qualification Matcher Module
Validates CV claims against interview answers using LLM
"""

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class QualificationMatcher:
    """Matches CV claims against interview answers"""

    def __init__(self):
        self.try_import_ollama()

    def try_import_ollama(self):
        """Import ollama for LLM evaluation"""
        try:
            import ollama
            self.ollama = ollama
            logger.info("✅ Ollama imported for qualification matching")
        except ImportError:
            logger.warning("⚠️ Ollama not available")
            self.ollama = None

    def extract_cv_claims(self, cv_text: str) -> Dict[str, List[str]]:
        """
        Extract important claims from CV text
        Returns: {projects: [...], skills: [...], experience: [...], education: [...]}
        """
        if not cv_text:
            return {"projects": [], "skills": [], "experience": [], "education": []}

        try:
            # Use simple keyword extraction for now
            claims = {
                "projects": [],
                "skills": [],
                "experience": [],
                "education": []
            }

            lines = cv_text.split("\n")
            for line in lines:
                line_lower = line.lower()

                # Simple heuristics
                if any(kw in line_lower for kw in ["proje", "project", "geliştir", "build", "oluştur"]):
                    claims["projects"].append(line.strip())
                elif any(kw in line_lower for kw in ["skill", "beceri", "python", "java", "javascript", "react", "django"]):
                    claims["skills"].append(line.strip())
                elif any(kw in line_lower for kw in ["deneyim", "experience", "yıl", "years", "çalış", "work"]):
                    claims["experience"].append(line.strip())
                elif any(kw in line_lower for kw in ["eğitim", "education", "üniversite", "university", "diploma"]):
                    claims["education"].append(line.strip())

            logger.info(f"CV Claims extracted: {len(claims['projects'])} projects, {len(claims['skills'])} skills")
            return claims
        except Exception as e:
            logger.error(f"CV claim extraction error: {e}")
            return {"projects": [], "skills": [], "experience": [], "education": []}

    def match_with_llm(self, cv_claims: str, question: str, answer: str) -> Dict:
        """
        Use LLM to validate if answer matches CV claims
        Returns: {match: bool, consistency_score: 0-100, missing_details: [...], red_flags: [...], confidence: "high"|"medium"|"low"}
        """
        if not self.ollama:
            logger.warning("Ollama not available for qualification matching")
            return {
                "match": True,
                "consistency_score": 75,
                "missing_details": [],
                "red_flags": [],
                "confidence": "low",
                "explanation": "LLM evaluation unavailable"
            }

        try:
            prompt = f"""
CV'deki bilgiler (Adayın iddia ettiği deneyim):
{cv_claims}

Mülakat Sorusu:
{question}

Mülakat Cevabı:
{answer}

---

Bunu değerlendir:
1. CV'de bu proje/deneyim belirtili mi?
2. Cevapda verilen detaylar CV'yle uyumlu mu?
3. Hangi detaylar eksik?
4. Tutarsızlıklar var mı?
5. Adayın bu deneyimi gerçekten yaşadığına inanıyor musun?

JSON formatında cevap ver:
{{
  "cv_match": true/false,
  "consistency_score": 0-100,
  "missing_details": ["...", "..."],
  "red_flags": ["...", "..."],
  "confidence": "high/medium/low",
  "explanation": "Kısa açıklama"
}}

SADECE JSON cevap ver, başka bir şey yazma!
"""

            messages = [
                {"role": "system", "content": "Sen bir mülakat değerlendirmecisisin. CV ve cevapları analiz ettin CV doğruluğunu kontrol et."},
                {"role": "user", "content": prompt}
            ]

            response = self.ollama.chat(
                model=os.getenv("OLLAMA_MODEL", "llama3.2"),
                messages=messages,
                options={
                    "temperature": 0.3,
                    "num_predict": 500
                }
            )

            result_text = response.get("message", {}).get("content", "").strip()
            logger.info(f"LLM Response: {result_text[:200]}")

            # Parse JSON response
            try:
                # Find JSON in response
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = result_text[json_start:json_end]
                    result = json.loads(json_str)
                    logger.info(f"Qualification Match Score: {result.get('consistency_score', 0)}")
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {e}")
                return {
                    "match": True,
                    "consistency_score": 65,
                    "missing_details": [],
                    "red_flags": ["LLM yanıtı parse edilemedi"],
                    "confidence": "low",
                    "explanation": "LLM evaluation failed"
                }

        except Exception as e:
            logger.error(f"LLM qualification matching error: {e}")
            return {
                "match": True,
                "consistency_score": 50,
                "missing_details": [],
                "red_flags": [str(e)],
                "confidence": "low",
                "explanation": f"Error: {str(e)}"
            }

    def validate_qualification(self, cv_text: str, question: str, answer: str) -> Dict:
        """
        Complete qualification validation workflow
        """
        logger.info("Starting qualification validation...")

        # Extract CV claims
        cv_claims = self.extract_cv_claims(cv_text)

        # Format CV claims for LLM
        cv_claims_str = json.dumps(cv_claims, ensure_ascii=False, indent=2)

        # Match with LLM
        result = self.match_with_llm(cv_claims_str, question, answer)

        return result


# Singleton instance
_matcher = None

def get_matcher() -> QualificationMatcher:
    """Get or create QualificationMatcher instance"""
    global _matcher
    if _matcher is None:
        _matcher = QualificationMatcher()
    return _matcher
