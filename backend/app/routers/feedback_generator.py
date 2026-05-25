"""
Feedback Generator Module
Generates comprehensive interview feedback and recommendations
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackGenerator:
    """Generates comprehensive interview feedback based on metrics"""

    @staticmethod
    def generate_content_feedback(metrics: Dict) -> str:
        feedback = []

        rel_score = metrics.get("relevance_score", 0)
        if rel_score >= 90:
            feedback.append("✅ Your answers were directly on point and fully relevant.")
        elif rel_score >= 80:
            feedback.append("✅ Good relevance — answers addressed the questions well.")
        elif rel_score >= 70:
            feedback.append("⚠️ Answers were somewhat relevant but a bit scattered. Try to stay more focused.")
        elif rel_score >= 60:
            feedback.append("❌ You drifted from the question at times. Read each question more carefully.")
        else:
            feedback.append("❌ Answers were largely off-topic. Make sure to address what is actually being asked.")

        answer_length = metrics.get("answer_length_words", 0)
        if answer_length >= 150:
            feedback.append("✅ Answers were comprehensive and sufficiently detailed.")
        elif answer_length < 80:
            feedback.append("⚠️ Answers were too brief. Aim for at least 150 words per answer.")
        elif answer_length > 800:
            feedback.append("⚠️ Answers were quite long. Try to be more concise.")

        star_score = metrics.get("star_structure_score")
        if star_score is not None:
            if star_score >= 75:
                feedback.append("✅ Good use of the STAR structure (Situation → Task → Action → Result).")
            else:
                feedback.append("⚠️ Try to structure answers more clearly using STAR: Situation, Task, Action, Result.")

        tech_score = metrics.get("technical_accuracy_score")
        if tech_score is not None and metrics.get("domain") == "technical":
            if tech_score >= 90:
                feedback.append("✅ Technical knowledge was accurate and on point.")
            elif tech_score >= 75:
                feedback.append("✅ Good technical knowledge. Some details are worth reviewing further.")
            elif tech_score >= 60:
                feedback.append("⚠️ Some gaps in technical knowledge were noticeable.")
            else:
                feedback.append("❌ Technical concepts need more study and practice.")

        return "\n".join(feedback)

    @staticmethod
    def generate_speech_feedback(metrics: Dict) -> str:
        feedback = []

        wpm = metrics.get("speech_rate_wpm", 0)
        if wpm and 120 <= wpm <= 150:
            feedback.append("✅ Speaking pace is ideal ({} WPM).".format(wpm))
        elif wpm and wpm < 100:
            feedback.append("⚠️ Speaking pace is too slow ({} WPM). Try to pick up the tempo.".format(wpm))
        elif wpm and wpm > 170:
            feedback.append("⚠️ Speaking too fast ({} WPM). Slow down for clarity.".format(wpm))

        pause_score = metrics.get("pause_frequency_score", 0)
        if pause_score >= 80:
            feedback.append("✅ Speech flowed naturally with good pause control.")
        elif pause_score >= 60:
            feedback.append("⚠️ Slightly too many pauses. Think before speaking rather than mid-sentence.")
        else:
            feedback.append("❌ Too many hesitations detected. Prepare answers in advance to speak more fluently.")

        return "\n".join(feedback)

    @staticmethod
    def generate_nonverbal_feedback(metrics: Dict) -> str:
        if metrics.get("nonverbal_aggregate") is None:
            return ""

        feedback = []

        eye_contact = metrics.get("eye_contact_score", 0)
        if eye_contact >= 75:
            feedback.append("✅ Good eye contact — you came across as confident and engaging.")
        elif eye_contact >= 60:
            feedback.append("⚠️ Try to maintain more consistent eye contact with the camera.")
        else:
            feedback.append("❌ Very little eye contact detected. This can appear unconfident.")

        head_stability = metrics.get("head_stability_score", 0)
        if head_stability >= 80:
            feedback.append("✅ Head movement was stable and controlled.")
        elif head_stability >= 60:
            feedback.append("⚠️ Head moved around a bit. Try to stay still and composed.")
        else:
            feedback.append("❌ Excessive head movement detected — can be distracting.")

        posture = metrics.get("posture_score", 0)
        if posture >= 75:
            feedback.append("✅ Good posture — you sat upright throughout.")
        elif posture >= 60:
            feedback.append("⚠️ Slightly slouched. Sit up straight for a more confident look.")
        else:
            feedback.append("❌ Poor posture detected. Adjust your seating position.")

        return "\n".join(feedback)

    @staticmethod
    def generate_strengths(metrics: Dict) -> List[str]:
        strengths = []
        domain = (metrics.get("domain") or "general").lower()

        # Content
        if metrics.get("relevance_score", 0) >= 85:
            strengths.append("Answered questions directly and stayed on topic")
        if metrics.get("content_score", 0) >= 85:
            strengths.append("High content quality across answers")
        if metrics.get("answer_length_words", 0) >= 150:
            strengths.append("Answers were detailed and well-developed")

        # STAR (general/behavioral)
        star = metrics.get("star_structure_score")
        if domain != "technical" and star is not None and star >= 75:
            strengths.append("Well-structured answers using the STAR method")

        # Technical accuracy (technical domain)
        tech = metrics.get("technical_accuracy_score")
        if domain == "technical" and tech is not None and tech >= 85:
            strengths.append("Technical knowledge was accurate and on point")

        # Speech
        wpm = metrics.get("speech_rate_wpm", 0)
        if wpm and 120 <= wpm <= 150:
            strengths.append("Speaking pace was clear and easy to follow")
        if metrics.get("pause_frequency_score", 0) >= 80:
            strengths.append("Speech flowed naturally with minimal hesitations")

        # Nonverbal
        if metrics.get("eye_contact_score") and metrics["eye_contact_score"] >= 75:
            strengths.append("Maintained consistent eye contact with the camera")
        if metrics.get("posture_score") and metrics["posture_score"] >= 75:
            strengths.append("Maintained upright posture throughout the interview")

        return strengths if strengths else ["Showed genuine effort throughout the interview"]

    @staticmethod
    def generate_improvements(metrics: Dict) -> List[str]:
        domain    = (metrics.get("domain") or "general").lower()
        relevance = metrics.get("relevance_score", 0)
        star      = metrics.get("star_structure_score")
        tech      = metrics.get("technical_accuracy_score")
        pause     = metrics.get("pause_frequency_score", 0)
        eye       = metrics.get("eye_contact_score")
        posture   = metrics.get("posture_score")
        head      = metrics.get("head_stability_score")

        improvements = []
        used = set()

        # ── Phase 1: absolute failures ──
        if relevance < 60:
            improvements.append("Focus more on directly answering each question")
            used.add("relevance")
        if domain != "technical" and star is not None and star < 50:
            improvements.append("Structure answers using the STAR method: Situation, Task, Action, Result")
            used.add("star")
        if domain == "technical" and tech is not None and tech < 65:
            improvements.append("Strengthen technical knowledge — review core concepts for this domain")
            used.add("tech")
        if pause < 70:
            improvements.append("Reduce filler words and hesitations — silence is fine, keep it brief")
            used.add("pause")
        if eye is not None and eye < 50:
            improvements.append("Maintain more eye contact with the camera to appear confident")
            used.add("eye")

        # ── Phase 2: fill to minimum 2 using weakest metrics ──
        if len(improvements) < 2:
            pool = []
            if "relevance" not in used:
                pool.append((relevance, "relevance",
                    "Keep working on staying focused and directly addressing each question"))
            if "star" not in used and domain != "technical" and star is not None:
                pool.append((star, "star",
                    "Continue refining the STAR structure in your behavioral answers"))
            if "tech" not in used and domain == "technical" and tech is not None:
                pool.append((tech, "tech",
                    "Continue strengthening your technical depth and precision"))
            if "pause" not in used:
                pool.append((pause, "pause",
                    "Keep working on reducing hesitations for a smoother delivery"))
            if "eye" not in used and eye is not None:
                pool.append((eye, "eye",
                    "Build more consistent eye contact for a stronger presence"))
            if posture is not None:
                pool.append((posture, "posture",
                    "Continue working on maintaining upright, confident posture"))
            if head is not None:
                pool.append((head, "head",
                    "Try to keep your head more stable to appear composed"))

            pool.sort(key=lambda x: x[0])  # weakest first
            needed = 2 - len(improvements)
            for _, _, msg in pool[:needed]:
                improvements.append(msg)

        return improvements

    @staticmethod
    def calculate_overall_score(metrics: Dict) -> int:
        """
        3-category weighted score. Domain-aware. Nonverbal excluded if no video.
        Technical: content×0.55 + speech×0.20 + nonverbal×0.25 (video) / content×0.75 + speech×0.25 (no video)
        General:   content×0.45 + speech×0.25 + nonverbal×0.30 (video) / content×0.65 + speech×0.35 (no video)
        """
        content  = metrics.get("content_score", 50)
        speech   = metrics.get("speech_quality_score", 50)
        nonverbal = metrics.get("nonverbal_aggregate")
        domain   = (metrics.get("domain") or "general").lower()

        if domain == "technical":
            if nonverbal is not None:
                return int(content * 0.55 + speech * 0.20 + nonverbal * 0.25)
            else:
                return int(content * 0.75 + speech * 0.25)
        else:
            if nonverbal is not None:
                return int(content * 0.45 + speech * 0.25 + nonverbal * 0.30)
            else:
                return int(content * 0.65 + speech * 0.35)

    @staticmethod
    def generate_recommendation(overall_score: int) -> str:
        if overall_score >= 75:
            return "Strong Yes"
        elif overall_score >= 60:
            return "Yes"
        elif overall_score >= 45:
            return "Maybe"
        elif overall_score >= 30:
            return "No"
        else:
            return "Strong No"

    def generate_full_report(self, interview_data: Dict, metrics: Dict) -> Dict:
        """Generate complete interview feedback report"""
        logger.info("Generating full feedback report...")

        if "domain" not in metrics and interview_data.get("domain"):
            metrics = dict(metrics)
            metrics["domain"] = interview_data["domain"]

        content_feedback  = self.generate_content_feedback(metrics)
        speech_feedback   = self.generate_speech_feedback(metrics)
        nonverbal_feedback = self.generate_nonverbal_feedback(metrics)
        strengths         = self.generate_strengths(metrics)
        improvements      = self.generate_improvements(metrics)
        overall_score     = self.calculate_overall_score(metrics)
        recommendation    = self.generate_recommendation(overall_score)

        nonverbal_agg = metrics.get("nonverbal_aggregate")

        report = {
            "overall_score":    overall_score,
            "content_score":    metrics.get("content_score", 50),
            "speech_score":     metrics.get("speech_quality_score", 50),
            "nonverbal_score":  int(nonverbal_agg) if nonverbal_agg is not None else None,
            "strengths":        strengths,
            "improvements":     improvements,
            "content_feedback": content_feedback,
            "speech_feedback":  speech_feedback,
            "nonverbal_feedback": nonverbal_feedback,
            "recommendation":   recommendation,
            "metrics":          metrics,
        }

        logger.info(f"Report generated: Score={overall_score}, Recommendation={recommendation}")
        return report


_generator = None

def get_generator() -> FeedbackGenerator:
    global _generator
    if _generator is None:
        _generator = FeedbackGenerator()
    return _generator
