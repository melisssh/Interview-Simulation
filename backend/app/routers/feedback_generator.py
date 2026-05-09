"""
Feedback Generator Module
Generates comprehensive interview feedback and recommendations
"""

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackGenerator:
    """Generates comprehensive interview feedback based on metrics"""

    @staticmethod
    def generate_content_feedback(metrics: Dict) -> str:
        """Generate specific feedback for content quality"""
        feedback = []

        # Relevance feedback
        rel_score = metrics.get("relevance_score", 0)
        if rel_score >= 90:
            feedback.append("✅ Soruya tam ve doğrudan cevap vermişsin. Odaklanman mükemmel.")
        elif rel_score >= 80:
            feedback.append("✅ Soruya iyi cevap verdim. Çoğunlukla ilgili.")
        elif rel_score >= 70:
            feedback.append("⚠️ Soruyla ilgili ama biraz dağınık. Daha odaklanmış cevap vermeyi dene.")
        elif rel_score >= 60:
            feedback.append("❌ Sorudan biraz sapmışsın. Soruyu daha dikkatli oku ve doğrudan cevapla.")
        else:
            feedback.append("❌ Cevap sorudan oldukça sapıyor. Soruda istenen şeye cevap ver.")

        # Keyword matching feedback
        kw_score = metrics.get("keyword_match_score", 0)
        if kw_score >= 80:
            feedback.append("✅ Sorudaki önemli kavramları iyi ele almışsın.")
        elif kw_score >= 60:
            feedback.append("⚠️ Bazı önemli kelimeleri cevapında kullan. Soruyu daha kapsamlı tara.")
        else:
            feedback.append("❌ Sorunun temel kavramlarını ele almamışsın. Eksik detaylar var.")

        # Completeness feedback
        comp_score = metrics.get("completeness_score", 0)
        answer_length = metrics.get("answer_length_words", 0)
        if comp_score >= 85 and answer_length >= 150:
            feedback.append("✅ Cevabın kapsamlı ve yeterli detayda. Tebrikler!")
        elif answer_length < 80:
            feedback.append("⚠️ Biraz daha detaylı cevap verebilirdin. En az 150 kelime hedefle.")
        elif answer_length > 500:
            feedback.append("⚠️ Cevap biraz uzun. Kısa ve öz tutmayı dene.")

        # STAR feedback (behavioral soruları için)
        star_score = metrics.get("star_structure_score")
        if star_score is not None:
            if star_score >= 90:
                feedback.append("✅ STAR yapısını harika kullandın (Situation → Task → Action → Result).")
            elif star_score >= 75:
                feedback.append("✅ STAR yapısını kullanmışsın. Tüm bölümleri biraz daha detaylı yap.")
            else:
                feedback.append("⚠️ Cevapında Situation, Task, Action ve Result bölümlerini daha açık göster.")

        # Technical accuracy feedback (teknik soruları için)
        tech_score = metrics.get("technical_accuracy_score")
        if tech_score is not None:
            if tech_score >= 90:
                feedback.append("✅ Teknik bilgin mükemmel. Konsept ve uygulamayı çok iyi anlamışsın.")
            elif tech_score >= 75:
                feedback.append("✅ Teknik bilgin iyi. Bazı detayları araştırmaya değer.")
            elif tech_score >= 60:
                feedback.append("⚠️ Teknik bilginde eksiklikler var. Konu üzerinde biraz daha çalışmalısın.")
            else:
                feedback.append("❌ Teknik kavramları daha iyi öğrenmen gerek. Konu malzemesini gözden geçir.")

        return "\n".join(feedback)

    @staticmethod
    def generate_speech_feedback(metrics: Dict) -> str:
        """Generate feedback for speech quality"""
        feedback = []

        # Speech rate
        wpm = metrics.get("speech_rate_wpm", 0)
        if 120 <= wpm <= 150:
            feedback.append("✅ Konuşma hızın mükemmel ({} WPM). Dinlemesi kolay.".format(wpm))
        elif wpm < 100:
            feedback.append("⚠️ Biraz yavaş konuşuyorsun ({} WPM). Tempo artır.".format(wpm))
        elif wpm > 170:
            feedback.append("⚠️ Çok hızlı konuşuyorsun ({} WPM). Yavaşla, daha anlaşılır ol.".format(wpm))

        # Pause and filler words
        pause_score = metrics.get("pause_frequency_score", 0)
        if pause_score >= 80:
            feedback.append("✅ Konuşmanız doğal akış var. Duraksama ve fillers iyi.")
        elif pause_score >= 60:
            feedback.append("⚠️ Biraz çok duraksama ve 'um/uh' sözcükleri var. Düşün sonra konuş.")
        else:
            feedback.append("❌ Çok sık duraksama yapıyorsun. Cevapları önceden düşün.")

        # Volume stability
        vol_score = metrics.get("volume_stability_score", 0)
        if vol_score >= 85:
            feedback.append("✅ Ses seviyeni iyi kontrol ediyorsun. Tutarlı ve profesyonel.")
        elif vol_score >= 70:
            feedback.append("⚠️ Ses seviyesi biraz dalgalı. Daha sabit bir ton dene.")
        else:
            feedback.append("❌ Ses seviyesi çok değişken. Mikrofon ve ses ayarlarını kontrol et.")

        # Tone variation
        tone_score = metrics.get("tone_variation_score", 0)
        if tone_score >= 50:
            feedback.append("✅ Konuşmanız renkli ve ilginç. Tone variation iyi.")
        elif tone_score >= 30:
            feedback.append("⚠️ Biraz monoton. Önemli kelimeleri vurgula, ton değiştir.")
        else:
            feedback.append("❌ Monoton konuşuyorsun. Ton varyasyonu artır, daha dinamik ol.")

        return "\n".join(feedback)

    @staticmethod
    def generate_nonverbal_feedback(metrics: Dict) -> str:
        """Generate feedback for non-verbal communication"""
        feedback = []

        # Eye contact
        eye_contact = metrics.get("eye_contact_score", 0)
        if eye_contact >= 75:
            feedback.append("✅ Kameraya bakışın iyi. Samimi ve güvenli görünüyorsun.")
        elif eye_contact >= 60:
            feedback.append("⚠️ Kameraya daha sık bakabilirsin. Göz iletişimi önemli.")
        else:
            feedback.append("❌ Kameraya çok az bakıyorsun. Güvensiz görünüyorsun.")

        # Head stability
        head_stability = metrics.get("head_stability_score", 0)
        if head_stability >= 80:
            feedback.append("✅ Başını sabit tutuyorsun. Kontrolüne ve profesyonel.")
        elif head_stability >= 60:
            feedback.append("⚠️ Başın biraz oynakla. Daha sabit tutmaya çalış.")
        else:
            feedback.append("❌ Başın çok hareketli. Dikkat dağıtıcı. Daha sabit dur.")

        # Posture
        posture = metrics.get("posture_score", 0)
        if posture >= 75:
            feedback.append("✅ Duruşun çok profesyonel. Dik ve kontrollü.")
        elif posture >= 60:
            feedback.append("⚠️ Biraz eğik oturuyorsun. Daha dik otural daha iyi göz tutardın.")
        else:
            feedback.append("❌ Çok eğik veya gergin görünüyorsun. Duruşunu düzelt, rahatla.")

        # Facial expression
        positive = metrics.get("facial_expression_positive", 0)
        negative = metrics.get("facial_expression_negative", 0)
        if positive >= 50 and negative < 10:
            feedback.append("✅ Yüz ifaden güzel. Pozitif ve samimi görünüyorsun.")
        elif negative > 20:
            feedback.append("❌ Stresli veya üzgün görünüyorsun. Rahatla, gülümse!")
        else:
            feedback.append("⚠️ Biraz daha enerji gösterebilirsin. Gülümse, pozitif kalma.")

        return "\n".join(feedback)

    @staticmethod
    def generate_strengths(metrics: Dict, content_feedback: str, speech_feedback: str, nonverbal_feedback: str) -> List[str]:
        """Generate list of strengths"""
        strengths = []

        if metrics.get("relevance_score", 0) >= 85:
            strengths.append("Soruları tam anladın ve doğrudan cevap verdin")
        if metrics.get("keyword_match_score", 0) >= 80:
            strengths.append("Önemli kavramları iyi ele aldın")
        if metrics.get("content_score", 0) >= 85:
            strengths.append("İçerik kalitesi mükemmel")
        if metrics.get("speech_rate_wpm", 0) and 120 <= metrics["speech_rate_wpm"] <= 150:
            strengths.append("Konuşma hızı profesyonel")
        if metrics.get("tone_variation_score", 0) >= 50:
            strengths.append("Konuşman renkli ve ilginç")
        if metrics.get("eye_contact_score", 0) >= 75:
            strengths.append("Kameraya bakışın samimi ve güvenli")
        if metrics.get("answer_length_words", 0) >= 150:
            strengths.append("Cevapların yeterince detaylı")

        return strengths[:3] if strengths else ["Cevaplarında iyi çaba gösterdin"]

    @staticmethod
    def generate_improvements(metrics: Dict) -> List[str]:
        """Generate list of areas for improvement"""
        improvements = []

        if metrics.get("relevance_score", 0) < 80:
            improvements.append("Sorulara daha odaklanmış cevaplar ver. Soruyu iki kez oku.")
        if metrics.get("keyword_match_score", 0) < 70:
            improvements.append("Sorudaki önemli kelimeleri cevapında da kullan")
        if metrics.get("answer_length_words", 0) < 100:
            improvements.append("Cevapların daha detaylı olması gerek. En az 150-200 kelime hedefle.")
        if metrics.get("speech_rate_wpm", 0) and (metrics["speech_rate_wpm"] < 100 or metrics["speech_rate_wpm"] > 170):
            improvements.append("Konuşma hızını düzenle (120-150 WPM hedefi)")
        if metrics.get("pause_frequency_score", 0) < 70:
            improvements.append("'Um' ve 'uh' gibi fillers'ı azalt. Sessizlik natural ama kısa tut.")
        if metrics.get("eye_contact_score", 0) < 70:
            improvements.append("Kameraya daha sık bak. Göz iletişimi güveni gösterir.")
        if metrics.get("tone_variation_score", 0) < 40:
            improvements.append("Konuşman biraz monoton. Önemli noktaları vurgula, ton değiştir.")

        return improvements[:3] if improvements else []

    @staticmethod
    def calculate_overall_score(metrics: Dict) -> int:
        """Calculate overall interview score"""
        scores = {
            "content": metrics.get("content_score", 50) * 0.4,
            "speech": metrics.get("speech_quality_score", 50) * 0.3,
            "nonverbal": metrics.get("eye_contact_score", 50) * 0.2,
            "engagement": metrics.get("engagement_score", 50) * 0.1,
        }

        overall = sum(scores.values()) / sum([0.4, 0.3, 0.2, 0.1])
        return int(overall)

    @staticmethod
    def generate_recommendation(overall_score: int, content_score: int, technical_score: Optional[int] = None) -> str:
        """Generate hiring recommendation"""
        if overall_score >= 80 and content_score >= 85:
            return "Strong Yes"
        elif overall_score >= 70 and content_score >= 75:
            return "Yes"
        elif overall_score >= 60 and content_score >= 65:
            return "Maybe"
        elif overall_score >= 50:
            return "No"
        else:
            return "Strong No"

    def generate_full_report(self, interview_data: Dict, metrics: Dict) -> Dict:
        """Generate complete interview feedback report"""
        logger.info("Generating full feedback report...")

        content_feedback = self.generate_content_feedback(metrics)
        speech_feedback = self.generate_speech_feedback(metrics)
        nonverbal_feedback = self.generate_nonverbal_feedback(metrics)
        strengths = self.generate_strengths(metrics, content_feedback, speech_feedback, nonverbal_feedback)
        improvements = self.generate_improvements(metrics)
        overall_score = self.calculate_overall_score(metrics)
        recommendation = self.generate_recommendation(
            overall_score,
            metrics.get("content_score", 50),
            metrics.get("technical_accuracy_score")
        )

        report = {
            "overall_score": overall_score,
            "content_score": metrics.get("content_score", 50),
            "speech_score": metrics.get("speech_quality_score", 50),
            "nonverbal_score": int(
                metrics.get(
                    "nonverbal_aggregate",
                    (metrics.get("eye_contact_score", 50) + metrics.get("posture_score", 50)) / 2,
                )
            ),
            "strengths": strengths,
            "improvements": improvements,
            "content_feedback": content_feedback,
            "speech_feedback": speech_feedback,
            "nonverbal_feedback": nonverbal_feedback,
            "recommendation": recommendation,
            "metrics": metrics,
        }

        logger.info(f"Report generated: Score={overall_score}, Recommendation={recommendation}")
        return report


# Singleton instance
_generator = None

def get_generator() -> FeedbackGenerator:
    """Get or create FeedbackGenerator instance"""
    global _generator
    if _generator is None:
        _generator = FeedbackGenerator()
    return _generator
