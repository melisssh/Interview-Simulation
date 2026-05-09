"""
Content Quality Analysis Module
Analyzes the content of interview answers across multiple dimensions
"""

import os
import json
import logging
from typing import Dict, List, Optional

from ..analysis.llm_answer_scores import gemini_technical_score_0_100

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyzes content quality metrics for interview answers"""

    def __init__(self):
        self.model = None
        self.util = None
        self.SentenceTransformer = None
        self.nlp = None
        self._model_loaded = False

    def _load_model(self):
        """Lazy-load SentenceTransformer only when needed"""
        # OPTIMIZATION: SentenceTransformer devre dışı (RAM tasarrufu)
        # Fallback keyword matching kullanılacak
        if self._model_loaded:
            return

        logger.info("⚠️ SentenceTransformer devre dışı (RAM tasarrufu) - keyword matching kullanılıyor")
        self.model = None
        self._model_loaded = True

    def calculate_relevance_score(self, question: str, answer: str) -> int:
        """
        Calculate how relevant the answer is to the question (0-100)
        Uses semantic similarity or simple keyword matching
        """
        if not question or not answer:
            return 50  # Default

        # Try ML model first (lazy-loaded)
        try:
            self._load_model()
            if self.model and self.util:
                q_embedding = self.model.encode(question, convert_to_tensor=True)
                a_embedding = self.model.encode(answer, convert_to_tensor=True)
                similarity = self.util.pytorch_cos_sim(q_embedding, a_embedding).item()
                score = max(0, min(100, int(similarity * 100)))
                logger.info(f"Relevance (ML): {score} (similarity: {similarity:.2f})")
                return score
        except Exception as e:
            logger.warning(f"ML relevance failed, using simple method: {e}")

        # Fallback: Simple keyword-based relevance
        q_keywords = set(self.extract_keywords(question))
        a_keywords = set(self.extract_keywords(answer))

        if not q_keywords:
            return 75  # Good default if question has no keywords

        overlap = len(q_keywords & a_keywords)
        score = int((overlap / len(q_keywords)) * 100)
        logger.info(f"Relevance (Simple): {score} (overlap: {overlap}/{len(q_keywords)})")
        return score

    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text using simple tokenization"""
        if not text:
            return []

        try:
            # Basit Türkçe stop words listesi
            stop_words = {
                've', 'veya', 'ama', 'ne', 'mi', 'mi', 'mi', 'gibi', 'için', 'ile', 'var', 'yok',
                'bir', 'bir', 'bu', 'o', 'şu', 'ben', 'sen', 'o', 'biz', 'siz', 'onlar',
                'benim', 'senin', 'onun', 'bizim', 'sizin', 'onların',
                'am', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
                'to', 'for', 'from', 'with', 'by', 'of', 'as', 'was', 'were', 'be', 'been'
            }

            # Split by space and punctuation
            import re
            words = re.findall(r'\b\w+\b', text.lower())

            # Filter: remove stop words ve kısa words (<3 char)
            keywords = []
            for word in words:
                if word not in stop_words and len(word) >= 3:
                    keywords.append(word)

            # Remove duplicates and return
            return list(set(keywords))[:20]  # Top 20 keywords
        except Exception as e:
            logger.error(f"Keyword extraction hatası: {e}")
            return []

    def calculate_keyword_match(self, question: str, answer: str) -> int:
        """
        Calculate how many keywords from question appear in answer (0-100)
        """
        q_keywords = set(self.extract_keywords(question))
        a_keywords = set(self.extract_keywords(answer))

        if not q_keywords:
            return 100

        matched = len(q_keywords & a_keywords)
        score = int((matched / len(q_keywords)) * 100)
        logger.info(f"Keyword Match: {score}% ({matched}/{len(q_keywords)})")
        return score

    def calculate_completeness_score(self, question: str, answer: str) -> int:
        """
        Estimate answer completeness
        - Longer answers = more complete (up to a point)
        - More keywords = more complete
        - Semantic coverage
        """
        # Heuristic: answer uzunluğuna ve keyword'lere bakıyoruz
        a_length = len(answer.split())
        keyword_score = self.calculate_keyword_match(question, answer)

        # Soru tipine göre beklenen minimum kelime sayısı
        # Technical: 200+, Behavioral: 150+, General: 100+
        min_words = 150

        if a_length < 50:
            length_score = 20
        elif a_length < min_words:
            length_score = 50 + (a_length - 50) / (min_words - 50) * 30
        elif a_length < 400:
            length_score = 90
        else:
            length_score = 80  # Çok uzun cevaplar biraz penalti

        completeness = int((keyword_score * 0.6 + length_score * 0.4))
        logger.info(f"Completeness: {completeness} (length: {length_score}, keywords: {keyword_score})")
        return completeness

    def detect_star_structure(self, answer: str) -> Dict[str, bool]:
        """
        Detect STAR structure elements in answer
        Returns: {situation: bool, task: bool, action: bool, result: bool}
        """
        answer_lower = answer.lower()

        # Simple keyword matching for STAR detection
        situation_keywords = [
            "durum", "başında", "zaman", "bağlamı", "ne", "neydi",
            "situation", "context", "at the time", "when i", "initially",
        ]
        task_keywords = [
            "görev", "sorumluluk", "üstlenme", "gerekti", "ihtiyaç",
            "task", "responsible", "needed to", "required to", "goal was",
        ]
        action_keywords = [
            "yaptım", "aldım", "yapmak", "adım", "çalıştık", "geliştirdik", "oluştur",
            "i did", "we implemented", "i built", "developed", "decided to", "approach was",
        ]
        result_keywords = [
            "sonuç", "başarı", "tamamladık", "öğrendim", "başarılı", "iyileştir",
            "outcome", "result", "learned", "achieved", "improved", "delivered",
        ]

        situation = any(kw in answer_lower for kw in situation_keywords)
        task = any(kw in answer_lower for kw in task_keywords)
        action = any(kw in answer_lower for kw in action_keywords)
        result = any(kw in answer_lower for kw in result_keywords)

        logger.info(f"STAR: S={situation}, T={task}, A={action}, R={result}")
        return {
            "situation": situation,
            "task": task,
            "action": action,
            "result": result
        }

    def calculate_star_score(self, answer: str) -> int:
        """
        Calculate STAR structure score (0-100)
        """
        star = self.detect_star_structure(answer)
        present_count = sum(star.values())
        score = int((present_count / 4) * 100)
        logger.info(f"STAR Score: {score}")
        return score

    def calculate_sentiment_score(self, text: str) -> int:
        """
        Simple sentiment analysis (-100 to 100)
        -100: very negative, 0: neutral, 100: very positive
        Uses keyword-based approach (ML model disabled for RAM optimization)
        """
        # OPTIMIZATION: Sentiment transformer devre dışı (RAM tasarrufu)
        # Fallback keyword-based approach used
        logger.info("⚠️ Sentiment transformer devre dışı (RAM tasarrufu) - keyword matching kullanılıyor")

        # Fallback: keyword-based sentiment
        text_lower = text.lower()

        positive_words = {
            'başarı', 'başarılı', 'harika', 'güzel', 'mükemmel', 'iyi', 'çok iyi',
            'öğrendim', 'geliştirdim', 'oluşturdum', 'tamamladım', 'başarıyla',
            'memnun', 'mutlu', 'hoşlanıyorum', 'seviyorum', 'ilgi', 'heyecanlı'
        }
        negative_words = {
            'zor', 'zorluk', 'sorun', 'problem', 'başarısız', 'kötü', 'hata',
            'korka', 'endişe', 'üzüldü', 'hayal kırıklığı', 'uzaklaş', 'kaçma'
        }

        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)

        if pos_count + neg_count == 0:
            score = 0
        else:
            score = int(((pos_count - neg_count) / (pos_count + neg_count)) * 100)
            score = max(-100, min(100, score))

        logger.info(f"Sentiment (Keyword): {score} (pos={pos_count}, neg={neg_count})")
        return score

    def _technical_overlap_score(self, question: str, answer: str) -> int:
        """Keyword overlap + length depth when no LLM result."""
        qk = set(self.extract_keywords(question))
        ak = set(self.extract_keywords(answer))
        if not qk:
            return int(max(0, min(100, 40 + min(35, len(ak) // 2))))
        overlap = len(qk & ak)
        ratio = overlap / max(1, len(qk))
        w = len(answer.split())
        depth = min(38, w // 4)
        return int(max(0, min(100, ratio * 70 + depth)))

    def estimate_technical_accuracy(
        self,
        question: str,
        answer: str,
        domain: str = "general",
        language: str = "tr",
    ) -> int:
        dom = (domain or "general").lower()
        if dom == "technical":
            g = gemini_technical_score_0_100(question, answer, language=language)
            if g is not None:
                logger.info("Technical accuracy from Gemini: %s", g)
                return g
        return self._technical_overlap_score(question, answer)

    def calculate_qualification_match(self, answer: str, cv_text: Optional[str]) -> int:
        """0–100: lexical overlap between answer and CV (no CV → 0)."""
        if not cv_text or not cv_text.strip() or not (answer or "").strip():
            return 0
        cv_kw = set(self.extract_keywords(cv_text))
        a_kw = set(self.extract_keywords(answer))
        if not cv_kw and not a_kw:
            return 0
        union = cv_kw | a_kw
        if not union:
            return 0
        jacc = len(cv_kw & a_kw) / len(union)
        return int(max(0, min(100, round(100 * min(1.0, jacc * 1.35)))))

    def analyze_answer(
        self,
        question: str,
        answer: str,
        domain: str = "general",
        is_behavioral: bool = False,
        cv_text: Optional[str] = None,
        language: str = "tr",
    ) -> Dict:
        """
        Comprehensive analysis of a single answer
        """
        logger.info(f"Analyzing answer for question: {question[:50]}...")

        analysis = {
            "relevance_score": self.calculate_relevance_score(question, answer),
            "keyword_match_score": self.calculate_keyword_match(question, answer),
            "completeness_score": self.calculate_completeness_score(question, answer),
            "star_structure_score": self.calculate_star_score(answer) if is_behavioral else None,
            "technical_accuracy_score": self.estimate_technical_accuracy(
                question, answer, domain, language=language
            ),
            "qualification_match_score": self.calculate_qualification_match(answer, cv_text),
            "sentiment_score": self.calculate_sentiment_score(answer),
            "answer_length_words": len(answer.split()),
        }

        # Calculate content score
        scores_to_average = [s for s in [
            analysis["relevance_score"],
            analysis["keyword_match_score"],
            analysis["completeness_score"],
            analysis["star_structure_score"] if is_behavioral else analysis["technical_accuracy_score"]
        ] if s is not None]

        analysis["content_score"] = int(sum(scores_to_average) / len(scores_to_average)) if scores_to_average else 50

        return analysis


# Singleton instance
_analyzer = None

def get_analyzer() -> ContentAnalyzer:
    """Get or create ContentAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ContentAnalyzer()
    return _analyzer
