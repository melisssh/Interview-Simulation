from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from datetime import datetime, timedelta

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_verified = Column(Integer, default=0)
    verification_token = Column(String(255), nullable=True, unique=True)
    verification_expires_at = Column(DateTime, nullable=True)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    full_name = Column(String, nullable=True)
    university = Column(String, nullable=True)
    department = Column(String, nullable=True)
    class_year = Column(String, nullable=True)
    cv_path = Column(String, nullable=True)


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)        # e.g. "Junior Backend Interview"
    domain = Column(String, nullable=False)       # e.g. "technical", "general"
    language = Column(String, nullable=False)     # e.g. "en", "tr"
    status = Column(String, default="created")    # created/preparing/ready/preparation_failed/in_progress/analyzing/analyzed/analysis_failed
    created_at = Column(DateTime, default=datetime.utcnow)
    video_path = Column(String, nullable=True)    # path of uploaded interview video
    company_name = Column(String, nullable=True)
    department_name = Column(String, nullable=True)
    position = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    company_context = Column(String(5000), nullable=True)
    preparation_error = Column(String(2000), nullable=True)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)   # "general", "technical"
    description = Column(String, nullable=True)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    language = Column(String, nullable=False)            # "tr" / "en"
    difficulty = Column(Integer, nullable=True)          # 1–5
    is_active = Column(Integer, default=1)               # 1 = active, 0 = inactive
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    question_text = Column(String(1024), nullable=True)
    order = Column(Integer, nullable=False)              # 1, 2, 3...


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    text = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=True)

class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_order = Column(Integer, nullable=False)
    question_text = Column(String(1024), nullable=True)
    answer_text = Column(String(5000), nullable=True)

    # Content Metrics (Primary)
    relevance_score = Column(Integer, nullable=True)           # 0-100: semantic similarity to question
    star_structure_score = Column(Integer, nullable=True)      # 0-100: STAR structure (behavioral only)
    technical_accuracy_score = Column(Integer, nullable=True)  # 0-100: Ollama score (technical only)

    # Speech Metrics (Secondary) — set from PCM at WebSocket time; backfilled from transcript if missing
    speech_rate_wpm = Column(Integer, nullable=True)           # words per minute
    pause_frequency_score = Column(Integer, nullable=True)     # 0-100: fluency / pause control

    # Response Behavior
    answer_length_words = Column(Integer, nullable=True)

    # Non-verbal — set from MediaPipe video analysis
    eye_contact_score = Column(Integer, nullable=True)         # 0-100
    head_stability_score = Column(Integer, nullable=True)      # 0-100
    posture_score = Column(Integer, nullable=True)             # 0-100

    # Composite Score
    content_score = Column(Integer, nullable=True)             # (relevance + star/technical) / 2 − length penalty

    # Video segment timestamps (seconds from interview start, set by WebSocket)
    video_start_second = Column(Float, nullable=True)  # when question was asked
    video_end_second   = Column(Float, nullable=True)  # when answer ended

    # Feedback
    answer_feedback = Column(String(2000), nullable=True)
    red_flags = Column(String(1000), nullable=True)  # JSON: ["flag1", "flag2"]

    created_at = Column(DateTime, default=datetime.utcnow)

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    # Overall Scores
    overall_score = Column(Integer, nullable=True)  # 0-100
    content_quality_score = Column(Integer, nullable=True)  # Primary
    speech_quality_score = Column(Integer, nullable=True)  # Secondary
    nonverbal_score = Column(Integer, nullable=True)  # Supporting

    # Detailed Metrics (JSON)
    metrics_json = Column(String(5000), nullable=True)  # all metrics as JSON

    # Feedback Content
    summary = Column(String(1000), nullable=True)
    strengths = Column(String(3000), nullable=True)  # Bullet points
    improvements = Column(String(3000), nullable=True)  # Bullet points
    actionable_recommendations = Column(String(3000), nullable=True)

    # Decision Indicators
    technical_fit = Column(String(50), nullable=True)           # "Insufficient" / "Partial" / "Sufficient"
    communication_fit = Column(String(50), nullable=True)       # "Weak" / "Average" / "Good" / "Strong"
    motivation_level = Column(String(50), nullable=True)        # "Low" / "Average" / "Moderate" / "High"
    overall_recommendation = Column(String(50), nullable=True)  # "Strong No" / "No" / "Maybe" / "Yes" / "Strong Yes"

    created_at = Column(DateTime, default=datetime.utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=1))
    used = Column(Integer, default=0)  # 0 = unused, 1 = used
