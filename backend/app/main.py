from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import os
import random
import smtplib
import ssl
from email.message import EmailMessage
from uuid import uuid4

import jwt
from pydantic import BaseModel, EmailStr
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .database import engine, SessionLocal
from . import models

# JWT ayarları (üretimde env'den alınmalı)
SECRET_KEY = "sizin-gizli-anahtar-buraya-degisitirin"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 gün

security = HTTPBearer(auto_error=False)

# Tabloları oluştur
models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama açılırken: yoksa 2 kategori ekle (general, technical)
    db = SessionLocal()
    try:
        if db.query(models.Category).count() == 0:
            db.add(models.Category(name="general", description="Genel mülakat soruları"))
            db.add(models.Category(name="technical", description="Teknik sorular"))
            db.commit()
    finally:
        db.close()
    yield
    # Uygulama kapanırken (şimdilik boş)


app = FastAPI(lifespan=lifespan)

# Password hash sistemi
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# DB bağlantısı dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def send_email(to_email: str, subject: str, body: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", smtp_user)

    if not (smtp_host and smtp_port and smtp_user and smtp_pass and email_from):
        raise HTTPException(status_code=500, detail="Mail ayarları eksik (SMTP).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Giriş yapmanız gerekiyor")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Geçersiz token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    return user


def require_admin(current_user: models.User = Depends(get_current_user)):
    if not getattr(current_user, "is_admin", 0):
        raise HTTPException(status_code=403, detail="Yalnızca adminler erişebilir.")
    return current_user

# Kullanıcı oluştur
class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/create-user")
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db)):
    # Email'i normalize et (boşlukları kırp, küçük harfe çevir)
    email = (payload.email or "").strip().lower()
    password = payload.password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Şifre en az 8 karakter olmalı.")
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Bu email ile zaten bir hesap var. Lütfen giriş yapın.")

    hashed_pw = hash_password(password)

    new_user = models.User(email=email, password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "email": new_user.email
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@app.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Mevcut şifre doğru mu?
    if not verify_password(payload.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Mevcut şifreniz yanlış.")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 8 karakter olmalı.")

    current_user.password = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Şifre güncellendi."}


@app.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    generic_response = {
        "detail": "Eğer bu email ile kayıtlı bir hesabın varsa, şifre sıfırlama linki gönderdik."
    }

    if not user:
        return generic_response

    token = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=1)

    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id
    ).delete(synchronize_session=False)

    reset_token = models.PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        used=0,
    )
    db.add(reset_token)
    db.commit()

    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    reset_link = f"{frontend_base}/reset-password?token={token}"

    subject = "Şifre sıfırlama talebi"
    body = (
        "Merhaba,\n\n"
        "Şifrenizi sıfırlamak için aşağıdaki linke tıklayabilirsiniz:\n\n"
        f"{reset_link}\n\n"
        "Eğer bu isteği siz yapmadıysanız, bu maili dikkate almayın.\n\n"
        "Mülakat Simülasyonu"
    )

    try:
        send_email(to_email=email, subject=subject, body=body)
    except Exception:
        # Mail hatasında bile kullanıcıya aynı mesajı veriyoruz
        return generic_response

    return generic_response


@app.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    token_str = (payload.token or "").strip()
    new_password = payload.new_password

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 8 karakter olmalı.")

    token_row = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == token_str)
        .first()
    )

    if not token_row or token_row.used == 1 or token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Bu şifre sıfırlama linki geçersiz veya süresi dolmuş.")

    user = db.query(models.User).filter(models.User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Kullanıcı bulunamadı.")

    user.password = hash_password(new_password)
    token_row.used = 1
    db.commit()

    return {"detail": "Şifre güncellendi."}

# Tüm kullanıcıları listele
@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return users

# Login endpoint – başarılı girişte JWT token döner
class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    if not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Şifre hatalı")
    token = create_access_token(data={"user_id": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "is_admin": getattr(user, "is_admin", 0),
    }


# --- Profil (mülakat sorularına katkı; kayıt sonrası zorunlu doldurulur) ---
class ProfileUpdate(BaseModel):
    full_name: str | None = None
    university: str | None = None
    department: str | None = None
    class_year: str | None = None


@app.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        return {}
    return {
        "full_name": profile.full_name,
        "university": profile.university,
        "department": profile.department,
        "class_year": profile.class_year,
        "cv_path": profile.cv_path,
    }


@app.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id)
        db.add(profile)
        db.flush()
    if payload.full_name is not None:
        profile.full_name = payload.full_name
    if payload.university is not None:
        profile.university = payload.university
    if payload.department is not None:
        profile.department = payload.department
    if payload.class_year is not None:
        profile.class_year = payload.class_year
    db.commit()
    db.refresh(profile)
    return {
        "full_name": profile.full_name,
        "university": profile.university,
        "department": profile.department,
        "class_year": profile.class_year,
        "cv_path": profile.cv_path,
    }


# CV yükleme: dosyayı kaydeder, profile.cv_path günceller
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "profiles")

@app.post("/profile/cv")
def upload_profile_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id)
        db.add(profile)
        db.flush()
    user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "cv")[-1] or ".pdf"
    path = os.path.join(user_dir, f"cv{ext}")
    with open(path, "wb") as f:
        f.write(file.file.read())
    profile.cv_path = path
    db.commit()
    db.refresh(profile)
    return {"cv_path": profile.cv_path, "message": "CV yüklendi"}


# --- Kategoriler (mülakat formu dropdown için) ---
@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return [{"id": c.id, "name": c.name, "description": c.description} for c in categories]


# --- Soru modelleri ---
class QuestionCreate(BaseModel):
    text: str
    category_id: int
    language: str                 # "tr" / "en"
    difficulty: int | None = None
    is_active: int = 1            # 1 = aktif, 0 = pasif


class QuestionUpdate(BaseModel):
    text: str | None = None
    category_id: int | None = None
    language: str | None = None
    difficulty: int | None = None
    is_active: int | None = None


class InterviewStatusUpdate(BaseModel):
    status: str


# --- Soru havuzu endpoint'leri (GET/POST/PUT) ---
@app.get("/questions")
def get_questions(
    category_id: int | None = None,
    language: str | None = None,
    is_active: int | None = None,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    query = db.query(models.Question)

    if category_id is not None:
        query = query.filter(models.Question.category_id == category_id)
    if language is not None:
        query = query.filter(models.Question.language == language)
    if is_active is not None:
        query = query.filter(models.Question.is_active == is_active)

    questions = query.all()
    return [
        {
            "id": q.id,
            "text": q.text,
            "category_id": q.category_id,
            "language": q.language,
            "difficulty": q.difficulty,
            "is_active": q.is_active,
        }
        for q in questions
    ]


@app.post("/questions")
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    new_q = models.Question(
        text=payload.text,
        category_id=payload.category_id,
        language=payload.language,
        difficulty=payload.difficulty,
        is_active=payload.is_active,
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return {
        "id": new_q.id,
        "text": new_q.text,
        "category_id": new_q.category_id,
        "language": new_q.language,
        "difficulty": new_q.difficulty,
        "is_active": new_q.is_active,
    }


@app.put("/questions/{question_id}")
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    if payload.text is not None:
        q.text = payload.text
    if payload.category_id is not None:
        q.category_id = payload.category_id
    if payload.language is not None:
        q.language = payload.language
    if payload.difficulty is not None:
        q.difficulty = payload.difficulty
    if payload.is_active is not None:
        q.is_active = payload.is_active

    db.commit()
    db.refresh(q)
    return {
        "id": q.id,
        "text": q.text,
        "category_id": q.category_id,
        "language": q.language,
        "difficulty": q.difficulty,
        "is_active": q.is_active,
    }


# Geçici: belirli emailleri admin yap (kullandıktan sonra silebilirsin)
@app.post("/make-admin")
def make_admin(db: Session = Depends(get_db)):
    admin_emails = [
        "melis.halamoglu@std.yeditepe.edu.tr",
        "selin.kartal@std.yeditepe.edu.tr",
    ]
    users = db.query(models.User).filter(models.User.email.in_(admin_emails)).all()
    for u in users:
        u.is_admin = 1
    db.commit()
    return {"detail": f"{len(users)} kullanıcı admin yapıldı."}


class InterviewCreate(BaseModel):
    title: str
    domain: str
    language: str


@app.post("/interviews")
def create_interview(
    payload: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    new_interview = models.Interview(
        user_id=current_user.id,
        title=payload.title,
        domain=payload.domain,
        language=payload.language,
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)

    # Sistem soruları seçer: domain + dildeki havuzdan en az 5, en fazla 7 rastgele
    category = db.query(models.Category).filter(models.Category.name == payload.domain).first()
    if category:
        pool = (
            db.query(models.Question)
            .filter(
                models.Question.category_id == category.id,
                models.Question.language == payload.language,
                models.Question.is_active == 1,
            )
            .all()
        )
        # En az 5, en fazla 7; havuzda daha az varsa hepsini al
        target = random.randint(5, 7)
        count = min(target, len(pool))
        if count > 0:
            chosen = random.sample(pool, count)
            for order, q in enumerate(chosen, start=1):
                iq = models.InterviewQuestion(
                    interview_id=new_interview.id,
                    question_id=q.id,
                    order=order,
                )
                db.add(iq)
            db.commit()

    return {
        "id": new_interview.id,
        "title": new_interview.title,
        "domain": new_interview.domain,
        "language": new_interview.language,
        "status": new_interview.status,
        "created_at": new_interview.created_at,
    }


# --- Mülakat listesi (dashboard; giriş yapan kullanıcının listesi) ---
@app.get("/interviews")
def list_interviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interviews = db.query(models.Interview).filter(models.Interview.user_id == current_user.id).order_by(models.Interview.created_at.desc()).all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "domain": i.domain,
            "language": i.language,
            "status": i.status,
            "created_at": i.created_at,
        }
        for i in interviews
    ]


@app.post("/interviews/{interview_id}/status")
def update_interview_status(
    interview_id: int,
    payload: InterviewStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")
    interview.status = payload.status
    db.commit()
    db.refresh(interview)
    return {
        "id": interview.id,
        "status": interview.status,
    }


# --- Tek mülakat detayı (sorular, transcript, feedback dahil) ---
@app.get("/interviews/{interview_id}")
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")
    # Sorular (interview_questions + questions)
    iqs = db.query(models.InterviewQuestion).filter(models.InterviewQuestion.interview_id == interview_id).order_by(models.InterviewQuestion.order).all()
    questions = []
    for iq in iqs:
        q = db.query(models.Question).filter(models.Question.id == iq.question_id).first()
        if q:
            questions.append({"order": iq.order, "text": q.text})
    # Transcript
    transcript_row = db.query(models.Transcript).filter(models.Transcript.interview_id == interview_id).first()
    transcript = transcript_row.text if transcript_row else None
    duration = transcript_row.duration_seconds if transcript_row else None
    # Feedback
    feedback_row = db.query(models.Feedback).filter(models.Feedback.interview_id == interview_id).first()
    feedback = None
    if feedback_row:
        feedback = {
            "scores_json": feedback_row.scores_json,
            "summary": feedback_row.summary,
            "strengths": feedback_row.strengths,
            "improvements": feedback_row.improvements,
        }
    return {
        "id": interview.id,
        "user_id": interview.user_id,
        "title": interview.title,
        "domain": interview.domain,
        "language": interview.language,
        "status": interview.status,
        "created_at": interview.created_at,
        "questions": questions,
        "transcript": transcript,
        "duration_seconds": duration,
        "feedback": feedback,
    }


# --- Mülakat silme ---
@app.delete("/interviews/{interview_id}")
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")

    # İlişkili kayıtları sil (cascade yoksa manuel)
    db.query(models.InterviewQuestion).filter(models.InterviewQuestion.interview_id == interview_id).delete(synchronize_session=False)
    db.query(models.Transcript).filter(models.Transcript.interview_id == interview_id).delete(synchronize_session=False)
    db.query(models.Feedback).filter(models.Feedback.interview_id == interview_id).delete(synchronize_session=False)
    db.delete(interview)
    db.commit()
    return {"detail": "Mülakat silindi."}


# --- AI Chat (geri bildirime dayalı sohbet; OpenAI entegrasyonu) ---
class ChatMessage(BaseModel):
    message: str


@app.post("/interviews/{interview_id}/chat")
def chat(
    interview_id: int,
    payload: ChatMessage,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    interview = db.query(models.Interview).filter(models.Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Mülakat bulunamadı")
    if interview.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu mülakata erişim yetkiniz yok")
    transcript_row = db.query(models.Transcript).filter(models.Transcript.interview_id == interview_id).first()
    feedback_row = db.query(models.Feedback).filter(models.Feedback.interview_id == interview_id).first()
    transcript = (transcript_row.text or "") if transcript_row else ""
    summary = (feedback_row.summary or "") if feedback_row else ""
    strengths = (feedback_row.strengths or "") if feedback_row else ""
    improvements = (feedback_row.improvements or "") if feedback_row else ""
    user_msg = (payload.message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            system_content = (
                "Sen bir mülakat koçusun. Kullanıcının mülakat geri bildirimi (özet, güçlü yönler, gelişim alanları) ve konuşma metni (transcript) verilmiş. "
                "Kullanıcının sorularına bu bağlamda kısa, yapıcı ve Türkçe yanıt ver."
            )
            user_content = (
                f"Geri bildirim özeti: {summary}\nGüçlü yönler: {strengths}\nGelişim: {improvements}\n\n"
                f"Konuşma metni (transcript): {transcript[:2000] if transcript else 'Yok'}\n\n"
                f"Kullanıcı soruyor: {user_msg}"
            )
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=500,
            )
            reply = response.choices[0].message.content or "Yanıt oluşturulamadı."
        except Exception as e:
            reply = f"AI yanıtı alınamadı ({type(e).__name__}). Özet: {summary or 'Henüz analiz yok.'} Gelişim: {improvements or '—'}"
    else:
        reply = f"Geri bildiriminize göre: {summary or 'Henüz analiz yok.'}"
        if improvements:
            reply += f" Gelişim önerisi: {improvements}"
        reply += " (AI için OPENAI_API_KEY ortam değişkeni tanımlayın.)"
    return {"reply": reply}