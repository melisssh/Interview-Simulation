import os
import logging
from datetime import datetime, timedelta
from uuid import uuid4

import jwt
import smtplib
import ssl
from email.message import EmailMessage
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from starlette.requests import Request

from .messages import _, get_lang_from_header

from ..database import SessionLocal
from .. import models
from ..cv_read import read_cv_plaintext, is_valid_cv_text

logger = logging.getLogger(__name__)

router = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "sizin-gizli-anahtar-buraya-degisitirin")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


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
    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key:
        import json
        import urllib.request
        import urllib.error

        email_from = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
        payload = {
            "from": email_from,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if 200 <= resp.status < 300:
                    return
                raw = resp.read().decode("utf-8", errors="replace")
                raise HTTPException(status_code=500, detail=f"Email could not be sent (Resend): {raw}")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
            raise HTTPException(status_code=500, detail=f"Email could not be sent (Resend): {raw}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Email could not be sent (Resend): {repr(e)}")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", smtp_user)

    if not (smtp_host and smtp_port and smtp_user and smtp_pass and email_from):
        raise HTTPException(status_code=500, detail="Email settings missing (SMTP).")

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
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    if not credentials:
        raise HTTPException(status_code=401, detail=_("login_required", lang))
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail=_("invalid_token", lang))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail=_("token_expired", lang))
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail=_("invalid_token", lang))
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail=_("user_not_found", lang))
    return user


def require_admin(
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    if not getattr(current_user, "is_admin", 0):
        raise HTTPException(status_code=403, detail=_("admin_only", lang))
    return current_user


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/create-user")
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    email = (payload.email or "").strip().lower()
    password = payload.password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail=_("password_too_short", lang))
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail=_("email_exists", lang))

    hashed_pw = hash_password(password)
    verification_token = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=24)

    new_user = models.User(
        email=email,
        password=hashed_pw,
        is_verified=0,
        verification_token=verification_token,
        verification_expires_at=expires_at,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    verify_link = f"{frontend_base}/verify-email?token={verification_token}"

    subject = "Verify your email address"
    body = (
        "Hello,\n\n"
        "Please verify your email address to complete your Interview Simulation account registration by clicking the link below:\n\n"
        f"{verify_link}\n\n"
        "This link is valid for 24 hours.\n\n"
        "If you did not create this account, please ignore this email.\n\n"
        "Interview Simulation"
    )

    try:
        send_email(to_email=email, subject=subject, body=body)
        logger.info("Verification email sent to %s", email)
    except Exception as e:
        logger.warning("Could not send verification email to %s: %s", email, repr(e))
        # DEV mode: Auto-verify if email can't be sent (local only)
        if os.getenv("DEV_AUTO_VERIFY") == "1":
            new_user.is_verified = 1
            new_user.verification_token = None
            new_user.verification_expires_at = None
            db.commit()
            logger.info("DEV_AUTO_VERIFY: User %s auto-verified", email)
        # Don't fail registration if email can't be sent

    return {"id": new_user.id, "email": new_user.email, "message": "Registration successful. Please verify your email."}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    if not verify_password(payload.current_password, current_user.password):
        raise HTTPException(status_code=400, detail=_("current_password_wrong", lang))
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail=_("new_password_too_short", lang))
    current_user.password = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Password updated."}


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    email = (payload.email or "").strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    generic_response = {
        "detail": "If an account with this email exists, we sent a password reset link."
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

    subject = "Password reset request"
    body = (
        "Hello,\n\n"
        "You can reset your password by clicking the link below:\n\n"
        f"{reset_link}\n\n"
        "If you did not request a password reset, please ignore this email.\n\n"
        "Interview Simulation"
    )

    try:
        send_email(to_email=email, subject=subject, body=body)
    except Exception:
        return generic_response

    return generic_response


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    token_str = (payload.token or "").strip()
    new_password = payload.new_password

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail=_("new_password_too_short", lang))

    token_row = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == token_str)
        .first()
    )

    if not token_row or token_row.used == 1 or token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail=_("invalid_reset_link", lang))

    user = db.query(models.User).filter(models.User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail=_("user_not_found", lang))

    user.password = hash_password(new_password)
    token_row.used = 1
    db.commit()

    return {"detail": "Password updated."}


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    token_str = (payload.token or "").strip()
    user = db.query(models.User).filter(models.User.verification_token == token_str).first()
    if not user:
        raise HTTPException(status_code=400, detail=_("invalid_verification_code", lang))
    if user.is_verified:
        return {"detail": "Email already verified."}
    if user.verification_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail=_("verification_link_expired", lang))
    user.is_verified = 1
    user.verification_token = None
    user.verification_expires_at = None
    db.commit()
    return {"detail": "Email verified. You can now log in."}


class ResendVerificationRequest(BaseModel):
    email: EmailStr


@router.post("/resend-verification")
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    email = (payload.email or "").strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"detail": "If an account with this email exists, a verification link was sent."}
    if user.is_verified:
        return {"detail": "This email is already verified."}

    verification_token = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=24)
    user.verification_token = verification_token
    user.verification_expires_at = expires_at
    db.commit()

    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    verify_link = f"{frontend_base}/verify-email?token={verification_token}"

    subject = "Verify your email address"
    body = (
        "Hello,\n\n"
        "Please verify your email address to complete your Interview Simulation account registration by clicking the link below:\n\n"
        f"{verify_link}\n\n"
        "This link is valid for 24 hours.\n\n"
        "Interview Simulation"
    )

    try:
        send_email(to_email=email, subject=subject, body=body)
    except Exception:
        pass

    return {"detail": "Verification link sent."}


@router.post("/login")
def login(
    payload: dict,
    db: Session = Depends(get_db),
    request: Request = None,
):
    lang = get_lang_from_header(request.headers.get("accept-language") if request else None)
    email = payload.get("email", "")
    password = payload.get("password", "")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail=_("user_not_found", lang))
    if not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail=_("wrong_password", lang))
    if not user.is_verified:
        raise HTTPException(status_code=403, detail=_("email_not_verified", lang))
    token = create_access_token(data={"user_id": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "is_admin": getattr(user, "is_admin", 0),
    }


@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    users = db.query(models.User).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "is_admin": getattr(u, "is_admin", 0),
        }
        for u in users
    ]


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    university: str | None = None
    department: str | None = None
    class_year: str | None = None


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        return {}
    cv_filename = profile.cv_path.split("/")[-1] if profile.cv_path else None
    return {
        "full_name": profile.full_name,
        "university": profile.university,
        "department": profile.department,
        "class_year": profile.class_year,
        "cv_path": profile.cv_path,
        "cv_filename": cv_filename,
    }


@router.put("/profile")
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


UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "profiles")


@router.post("/profile/cv")
def upload_profile_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # File type check
    if file.content_type not in ["application/pdf", "application/x-pdf"]:
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # File size check (10MB)
    MAX_SIZE = 10 * 1024 * 1024
    contents = file.file.read(MAX_SIZE + 1)
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File size cannot exceed 10MB.")
    file.file.seek(0)

    profile = db.query(models.Profile).filter(models.Profile.user_id == current_user.id).first()
    if not profile:
        profile = models.Profile(user_id=current_user.id)
        db.add(profile)
        db.flush()
    user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    original_name = (file.filename or "cv.pdf").replace("/", "_")
    safe_name = "".join(c for c in original_name if c.isalnum() or c in "._- ")
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    path = os.path.join(user_dir, safe_name)
    with open(path, "wb") as f:
        f.write(contents)
    profile.cv_path = os.path.join("profiles", str(current_user.id), safe_name)
    db.commit()
    db.refresh(profile)

    # Check CV content (is it a real CV?)
    cv_text = read_cv_plaintext(profile.cv_path, max_chars=12000)
    if not is_valid_cv_text(cv_text):
        os.remove(path)
        profile.cv_path = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid CV. Please upload a PDF containing your resume."
        )

    return {"cv_path": profile.cv_path, "original_name": safe_name, "message": "CV uploaded"}

