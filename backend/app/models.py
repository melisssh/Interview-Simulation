from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime, timedelta

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Integer, default=0)  # 0 = normal kullanıcı, 1 = admin


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    full_name = Column(String, nullable=True)
    university = Column(String, nullable=True)
    department = Column(String, nullable=True)
    class_year = Column(String, nullable=True)   # örn. "3", "4. sınıf"
    cv_path = Column(String, nullable=True)     # yüklenen CV dosya yolu


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)        # e.g. "Junior Backend Interview"
    domain = Column(String, nullable=False)       # e.g. "technical", "general"
    language = Column(String, nullable=False)     # e.g. "en", "tr"
    status = Column(String, default="created")    # created/recording/completed/analyzed
    created_at = Column(DateTime, default=datetime.utcnow)
    video_path = Column(String, nullable=True)    # path of uploaded interview video


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
    is_active = Column(Integer, default=1)               # 1 = aktif, 0 = pasif


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    order = Column(Integer, nullable=False)              # 1, 2, 3...


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    text = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=True)


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    scores_json = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    strengths = Column(String, nullable=True)
    improvements = Column(String, nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=1))
    used = Column(Integer, default=0)  # 0 = kullanılmadı, 1 = kullanıldı
