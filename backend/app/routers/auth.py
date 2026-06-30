import os
import logging
from datetime import datetime, timedelta
from uuid import uuid4

import jwt
import smtplib
import ssl
from email.message import EmailMessage
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Cookie, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from starlette.requests import Request
from typing import Optional

from .messages import _

from ..database import SessionLocal
from .. import models
from ..cv_read import read_cv_plaintext, is_valid_cv_text

logger = logging.getLogger(__name__)

router = APIRouter()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is not set.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 240

security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Simple in-memory rate limiter (ip → [timestamps])
import time as _time
from collections import defaultdict
_rate_store: dict = defaultdict(list)

def _check_rate_limit(key: str, max_calls: int = 10, window: int = 60) -> None:
    """Raises 429 if key exceeded max_calls in the last `window` seconds."""
    now = _time.time()
    calls = [t for t in _rate_store[key] if now - t < window]
    calls.append(now)
    _rate_store[key] = calls
    if len(calls) > max_calls:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")


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


def _create_verification_token() -> tuple[str, datetime]:
    token = uuid4().hex
    expires_at = datetime.utcnow() + timedelta(hours=1)
    return token, expires_at


def _build_verification_email(token: str) -> tuple[str, str]:
    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    verify_link = f"{frontend_base}/verify-email?token={token}"
    subject = "Verify your email address"
    body = (
        "Hello,\n\n"
        "Please verify your email address to complete your Interview Simulation account registration by clicking the link below:\n\n"
        f"{verify_link}\n\n"
        "This link is valid for 5 minutes.\n\n"
        "If you did not create this account, please ignore this email.\n\n"
        "Interview Simulation"
    )
    return subject, body


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
    access_token: Optional[str] = Cookie(default=None),
):
    token = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token
    if not token:
        raise HTTPException(status_code=401, detail=_("login_required"))
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail=_("invalid_token"))
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail=_("token_expired"))
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail=_("invalid_token"))
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail=_("user_not_found"))
    return user



class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/create-user")
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    ip = request.client.host if request and request.client else "unknown"
    _check_rate_limit(f"create-user:{ip}", max_calls=5, window=60)
    email = (payload.email or "").strip().lower()
    password = payload.password
    if len(password) < 8:
        raise HTTPException(status_code=400, detail=_("password_too_short"))
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail=_("email_exists"))

    hashed_pw = hash_password(password)
    dev_auto = os.getenv("DEV_AUTO_VERIFY", "0") in ("1", "true")
    verification_token, expires_at = _create_verification_token() if not dev_auto else (None, None)

    new_user = models.User(
        email=email,
        password=hashed_pw,
        is_verified=1 if dev_auto else 0,
        verification_token=verification_token,
        verification_expires_at=expires_at,
    )

    subject, body = _build_verification_email(verification_token)

    db.add(new_user)
    try:
        send_email(to_email=email, subject=subject, body=body)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not send verification email to %s", email, exc_info=True)
        raise HTTPException(status_code=500, detail="Verification email could not be sent.")

    db.refresh(new_user)
    logger.info("Verification email sent to %s", email)

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
):
    if not verify_password(payload.current_password, current_user.password):
        raise HTTPException(status_code=400, detail=_("current_password_wrong"))
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail=_("new_password_too_short"))
    current_user.password = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Password updated."}


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    ip = request.client.host if request and request.client else "unknown"
    _check_rate_limit(f"forgot:{ip}", max_calls=5, window=60)
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
        (models.PasswordResetToken.user_id == user.id) |
        (models.PasswordResetToken.expires_at < datetime.utcnow())
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
    ip = request.client.host if request and request.client else "unknown"
    _check_rate_limit(f"reset:{ip}", max_calls=5, window=60)
    token_str = (payload.token or "").strip()
    new_password = payload.new_password

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail=_("new_password_too_short"))

    token_row = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == token_str)
        .first()
    )

    if not token_row or token_row.used == 1 or token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail=_("invalid_reset_link"))

    user = db.query(models.User).filter(models.User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail=_("user_not_found"))

    user.password = hash_password(new_password)
    # Invalidate all reset tokens for this user after a successful reset.
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user.id
    ).delete(synchronize_session=False)
    db.commit()

    return {"detail": "Password updated."}


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    token_str = (payload.token or "").strip()
    user = db.query(models.User).filter(models.User.verification_token == token_str).first()
    if not user or user.is_verified:
        return {"detail": "Email verified. You can now log in."}
    if user.verification_expires_at and user.verification_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail=_("verification_link_expired"))
    user.is_verified = 1
    db.commit()
    return {"detail": "Email verified. You can now log in."}


class ResendVerificationRequest(BaseModel):
    email: EmailStr


@router.post("/resend-verification")
def resend_verification(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    ip = request.client.host if request and request.client else "unknown"
    _check_rate_limit(f"resend-verification:{ip}", max_calls=5, window=60)

    email = (payload.email or "").strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return {"detail": "If an account with this email exists, a verification link was sent."}
    if user.is_verified:
        return {"detail": "This email is already verified."}
    if (
        user.verification_token
        and user.verification_expires_at
        and user.verification_expires_at > datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail=_("verification_link_still_valid"))

    verification_token, expires_at = _create_verification_token()
    user.verification_token = verification_token
    user.verification_expires_at = expires_at

    subject, body = _build_verification_email(verification_token)

    try:
        send_email(to_email=email, subject=subject, body=body)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not resend verification email to %s", email, exc_info=True)
        raise HTTPException(status_code=500, detail="Verification email could not be sent.")

    return {"detail": "Verification link sent."}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    ip = request.client.host if request and request.client else "unknown"
    _check_rate_limit(f"login:{ip}", max_calls=15, window=60)
    email = (payload.email or "").strip().lower()
    password = payload.password
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail=_("invalid_credentials"))
    if not user.is_verified:
        raise HTTPException(status_code=403, detail=_("email_not_verified"))
    token = create_access_token(data={"user_id": user.id})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
    }


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"detail": "Logged out."}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    university: str | None = None
    department: str | None = None
    class_year: str | None = None


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    token = create_access_token(data={"user_id": current_user.id})
    return {"id": current_user.id, "email": current_user.email, "access_token": token}


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
    safe_name = f"{uuid4().hex}.pdf"
    path = os.path.join(user_dir, safe_name)
    with open(path, "wb") as f:
        f.write(contents)
    profile.cv_path = os.path.join("profiles", str(current_user.id), safe_name)
    db.commit()
    db.refresh(profile)

    # Check CV content (is it a real CV?)
    cv_text = read_cv_plaintext(profile.cv_path, max_chars=12000)
    if not is_valid_cv_text(cv_text):
        try:
            os.remove(path)
        except OSError:
            pass
        profile.cv_path = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid CV. Please upload a PDF containing your resume."
        )

    return {"cv_path": profile.cv_path, "original_name": safe_name, "message": "CV uploaded"}

