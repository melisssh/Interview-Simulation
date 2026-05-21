"""
Content Quality Analysis Module
Analyzes the content of interview answers across multiple dimensions
"""

import os
import re
import json
import logging
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from ..analysis.llm_answer_scores import gemini_technical_score_0_100

logger = logging.getLogger(__name__)

_PLACEHOLDER_QUESTION = re.compile(
    r"^\s*(question|soru)\s*\d+\s*$",
    re.IGNORECASE,
)


def _cosine_to_relevance_score(similarity: float) -> int:
    """Map cosine in [-1, 1] to 0–100 without collapsing small positives to 0."""
    s = max(-1.0, min(1.0, float(similarity)))
    # 0 → 50 (belirsiz), 1 → 100, -1 → 0
    return int(round(max(0.0, min(100.0, 50.0 + 50.0 * s))))


class ContentAnalyzer:
    """Analyzes content quality metrics for interview answers"""

    def __init__(self):
        self.model = None
        self.util = None
        self.SentenceTransformer = None
        self.nlp = None
        self._model_loaded = False

    def _load_model(self):
        """Lazy-load SentenceTransformer by default; set USE_SENTENCE_TRANSFORMER=0 to skip (RAM)."""
        if self._model_loaded:
            return

        flag = (os.getenv("USE_SENTENCE_TRANSFORMER") or "").strip().lower()
        if flag in ("0", "false", "no", "off"):
            logger.info(
                "SentenceTransformer disabled (USE_SENTENCE_TRANSFORMER=0); "
                "using keyword matching for relevance."
            )
            self.model = None
            self.util = None
            self._model_loaded = True
            return

        try:
            from sentence_transformers import SentenceTransformer, util

            model_name = (
                os.getenv("SENTENCE_TRANSFORMER_MODEL") or "paraphrase-multilingual-MiniLM-L12-v2"
            ).strip()
            logger.info("Loading SentenceTransformer: %s (device=cpu)", model_name)
            self.model = SentenceTransformer(model_name, device="cpu")
            self.util = util
        except Exception as e:
            logger.warning(
                "SentenceTransformer failed to load (%s); using keyword fallback for relevance.",
                e,
            )
            self.model = None
            self.util = None

        self._model_loaded = True

    def calculate_relevance_score(self, question: str, answer: str) -> int:
        """
        Calculate how relevant the answer is to the question (0-100)
        Uses semantic similarity or simple keyword matching
        """
        if not question or not answer:
            return 50  # Default

        # Try embedding similarity first (default on unless USE_SENTENCE_TRANSFORMER=0)
        try:
            self._load_model()
            if self.model and self.util:
                q_text = (question or "")[:2500]
                a_text = (answer or "")[:8000]
                q_embedding = self.model.encode(
                    q_text, convert_to_tensor=True, normalize_embeddings=True
                )
                a_embedding = self.model.encode(
                    a_text, convert_to_tensor=True, normalize_embeddings=True
                )
                if q_embedding.dim() == 1:
                    q_embedding = q_embedding.unsqueeze(0)
                if a_embedding.dim() == 1:
                    a_embedding = a_embedding.unsqueeze(0)
                similarity = float(self.util.pytorch_cos_sim(q_embedding, a_embedding).item())
                score = _cosine_to_relevance_score(similarity)
                logger.info(
                    "Relevance (SentenceTransformer): %s (cosine=%.4f, mapped)",
                    score,
                    similarity,
                )
                return score
        except Exception as e:
            logger.warning("Embedding relevance failed, using keyword method: %s", e)

        # Fallback: Simple keyword-based relevance
        q_keywords = set(self.extract_keywords(question))
        a_keywords = set(self.extract_keywords(answer))

        if not q_keywords:
            return 75  # Good default if question has no keywords

        overlap = len(q_keywords & a_keywords)
        score = int(round((overlap / len(q_keywords)) * 100))

        if _PLACEHOLDER_QUESTION.match((question or "").strip()):
            # DB text like "Question 3": word overlap is meaningless; neutral base
            if overlap == 0:
                score = max(score, 48)
            logger.info(
                "Relevance (Simple): placeholder soru metni; skor=%s (overlap=%s/%s)",
                score,
                overlap,
                len(q_keywords),
            )
            return min(100, score)

        if overlap == 0 and (question or "").strip() and (answer or "").strip():
            ratio = SequenceMatcher(
                None,
                (question or "").lower()[:1200],
                (answer or "").lower()[:1200],
            ).ratio()
            fuzzy = int(round(ratio * 55))
            if fuzzy > score:
                score = fuzzy
            logger.info(
                "Relevance (Simple): overlap=0, difflib ile destek skor=%s (ratio=%.3f)",
                score,
                ratio,
            )

        logger.info(f"Relevance (Simple): {score} (overlap: {overlap}/{len(q_keywords)})")
        return score

    def extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text using simple tokenization"""
        if not text:
            return []

        try:
            stop_words = {
                'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                'should', 'may', 'might', 'shall', 'must', 'can', 'of', 'in', 'to',
                'for', 'on', 'at', 'by', 'with', 'from', 'as', 'into', 'through',
                'during', 'before', 'after', 'above', 'below', 'between', 'out', 'off',
                'over', 'under', 'again', 'further', 'then', 'once', 'and', 'or', 'but',
                'am', 'it', 'its'
            }

            # Split by space and punctuation
            import re
            words = re.findall(r'\b\w+\b', text.lower())

            # Filter: remove stop words and short words (<3 char)
            keywords = []
            for word in words:
                if word not in stop_words and len(word) >= 3:
                    keywords.append(word)

            # Remove duplicates and return
            return list(set(keywords))[:20]  # Top 20 keywords
        except Exception as e:
            logger.error(f"Keyword extraction error: {e}")
            return []

    @staticmethod
    def length_penalty(answer: str) -> int:
        """Return a penalty (0–20) based on answer length extremes.
        Ideal range: 80–800 words per answer.
        """
        word_count = len((answer or "").split())
        if word_count < 80:
            return int((80 - word_count) / 80 * 20)
        if word_count > 800:
            return min(10, int((word_count - 800) / 300 * 10))
        return 0

    def detect_star_structure(self, answer: str) -> Dict[str, bool]:
        """
        Detect STAR structure elements in answer
        Returns: {situation: bool, task: bool, action: bool, result: bool}
        """
        answer_lower = answer.lower()

        situation_keywords = [
            # EN
            "situation", "context", "at the time", "when i", "initially",
            "background", "scenario", "at that point", "there was", "we were",
            # translated from TR
            "at the start", "at that time", "during the process", "in that period",
            "i encountered", "it happened", "there were", "in the phase", "working at",
        ]
        task_keywords = [
            # EN
            "task", "responsible", "needed to", "required to", "goal was",
            "objective", "my role", "assigned to", "expected to", "had to",
            # translated from TR
            "duty", "responsibility", "was needed", "need", "target", "purpose",
            "was expected", "my duty", "i took on", "requirement", "to complete",
            "to solve", "to ensure",
        ]
        action_keywords = [
            # EN
            "i did", "we implemented", "i built", "developed", "decided to",
            "i created", "i designed", "i organized", "i analyzed", "i used",
            "i applied", "i coordinated", "i communicated", "approach was",
            # translated from TR
            "i took", "i started", "i implemented", "i decided", "i established",
            "i researched", "i held a meeting", "i preferred",
        ]
        result_keywords = [
            # EN
            "outcome", "result", "learned", "achieved", "improved", "delivered",
            "gained", "increased", "reduced", "solved", "completed", "realized",
            "accomplished", "as a result", "consequently", "in the end", "ultimately",
            # translated from TR
            "success", "i completed", "i learned", "successful", "i improved",
            "i obtained", "i provided", "i won", "i increased", "i decreased",
            "i solved", "i accomplished", "i reached", "i noticed", "i contributed",
            "efficiency", "impact", "feedback", "satisfaction",
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

    def analyze_answer(
        self,
        question: str,
        answer: str,
        domain: str = "general",
        is_behavioral: bool = False,
        language: str = "tr",
    ) -> Dict:
        """
        Comprehensive analysis of a single answer.
        content_score = (relevance + keyword + star/technical) / 3, then length penalty applied.
        """
        logger.info(f"Analyzing answer for question: {question[:50]}...")

        relevance = self.calculate_relevance_score(question, answer)
        star = self.calculate_star_score(answer) if is_behavioral else None
        technical = self.estimate_technical_accuracy(question, answer, domain, language=language)
        word_count = len((answer or "").split())

        # 2-component average: relevance + (star or technical)
        third = star if is_behavioral else technical
        scores = [s for s in [relevance, third] if s is not None]
        base_content = int(sum(scores) / len(scores)) if scores else 50

        # Length penalty: too short or too long
        penalty = self.length_penalty(answer)
        content_score = max(0, base_content - penalty)

        if penalty > 0:
            logger.info(
                "Length penalty applied: words=%d, penalty=%d, content %d→%d",
                word_count, penalty, base_content, content_score,
            )

        analysis = {
            "relevance_score": relevance,
            "star_structure_score": star,
            "technical_accuracy_score": technical,
            "answer_length_words": word_count,
            "content_score": content_score,
        }

        return analysis


# Singleton instance
_analyzer = None

def get_analyzer() -> ContentAnalyzer:
    """Get or create ContentAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ContentAnalyzer()
    return _analyzer
