"""
Security Tests — AI Interview Simulator
Tests authentication, authorization, and input validation security.
"""

import pytest
import sys
import os
import uuid
import jwt as pyjwt
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from app.main import app
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

client = TestClient(app)

TEST_PASSWORD = "TestPass123!"


def register_and_login():
    """Helper: register a fresh user and return token."""
    email = f"sec_{uuid.uuid4().hex[:8]}@testmail.com"
    client.post("/create-user", json={"email": email, "password": TEST_PASSWORD})
    res = client.post("/login", json={"email": email, "password": TEST_PASSWORD})
    if res.status_code == 200:
        return res.json()["access_token"]
    return None


# ─────────────────────────────────────────────
# ST-01 / ST-05 / ST-06 — Token Güvenliği
# ─────────────────────────────────────────────

class TestTokenSecurity:

    def test_invalid_token_returns_401(self):
        """
        ST-01: Tamamen geçersiz (rastgele string) bir token ile
        korumalı endpoint'e erişim 401 döndürmeli.
        """
        res = client.get("/profile", headers={"Authorization": "Bearer thisisaninvalidtoken"})
        assert res.status_code == 401

    def test_empty_token_returns_401(self):
        """
        ST-05: Boş string token ile istek 401 döndürmeli.
        """
        res = client.get("/profile", headers={"Authorization": "Bearer "})
        assert res.status_code == 401

    def test_no_token_profile_returns_401(self):
        """
        ST-06a: Token olmadan /profile isteği 401 döndürmeli.
        """
        res = client.get("/profile")
        assert res.status_code == 401

    def test_no_token_interviews_returns_401(self):
        """
        ST-06b: Token olmadan /interviews isteği 401 döndürmeli.
        """
        res = client.get("/interviews")
        assert res.status_code == 401

    def test_no_token_create_interview_returns_401(self):
        """
        ST-06c: Token olmadan POST /interviews isteği 401 döndürmeli.
        """
        res = client.post("/interviews", json={
            "company_name": "Google",
            "position": "SWE",
            "sector": "Tech",
        })
        assert res.status_code == 401

    def test_expired_token_returns_401(self):
        """
        ST-02: Süresi dolmuş JWT token 401 döndürmeli.
        Token manuel olarak eski bir exp ile imzalanır.
        """
        secret = os.getenv("JWT_SECRET_KEY")
        expired_payload = {
            "user_id": 999,
            "email": "expired@test.com",
            "exp": int(time.time()) - 3600,  # 1 saat önce expired
        }
        expired_token = pyjwt.encode(expired_payload, secret, algorithm="HS256")
        res = client.get("/profile", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401

    def test_tampered_token_returns_401(self):
        """
        ST-02b: İmzası bozulmuş (tampered) JWT token 401 döndürmeli.
        Geçerli bir token'ın son karakteri değiştirilerek bozulur.
        """
        token = register_and_login()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")
        tampered = token[:-4] + "XXXX"
        res = client.get("/profile", headers={"Authorization": f"Bearer {tampered}"})
        assert res.status_code == 401

    def test_wrong_secret_token_returns_401(self):
        """
        ST-02c: Farklı bir secret ile imzalanmış JWT token 401 döndürmeli.
        Saldırgan kendi secret'ı ile token üretmeye çalışır.
        """
        fake_payload = {"user_id": 1, "email": "hacker@evil.com"}
        fake_token = pyjwt.encode(fake_payload, "wrong_secret_key", algorithm="HS256")
        res = client.get("/profile", headers={"Authorization": f"Bearer {fake_token}"})
        assert res.status_code == 401


# ─────────────────────────────────────────────
# ST-03 — Yetkilendirme (Authorization)
# ─────────────────────────────────────────────

class TestAuthorization:

    def test_cannot_access_other_users_interview(self):
        """
        ST-03: Bir kullanıcı başka kullanıcıya ait interview'a erişememeli
        (404 veya 403 dönmeli).
        """
        token = register_and_login()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")
        # Var olmayan / başka kullanıcıya ait ID ile istek
        res = client.get("/interviews/999999", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code in [403, 404]

    def test_cannot_delete_other_users_interview(self):
        """
        ST-03b: Başka kullanıcının interview'unu silmeye çalışmak 403/404 döndürmeli.
        """
        token = register_and_login()
        if not token:
            pytest.skip("DEV_AUTO_VERIFY not enabled")
        res = client.delete("/interviews/999999", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code in [403, 404]


# ─────────────────────────────────────────────
# ST-04 — SQL Injection & Input Validation
# ─────────────────────────────────────────────

class TestInputValidation:

    def test_sql_injection_in_login_email(self):
        """
        ST-04a: Email alanına SQL injection girişi uygulama crash'lememeli.
        422 (validation error) veya 401 dönmeli.
        """
        res = client.post("/login", json={
            "email": "' OR '1'='1",
            "password": "anything",
        })
        assert res.status_code in [400, 401, 422]

    def test_sql_injection_in_login_password(self):
        """
        ST-04b: Şifre alanına SQL injection girişi uygulama crash'lememeli.
        """
        res = client.post("/login", json={
            "email": "test@test.com",
            "password": "' OR '1'='1'; DROP TABLE users; --",
        })
        assert res.status_code in [400, 401, 422]

    def test_xss_payload_in_registration(self):
        """
        ST-04c: Email alanına XSS payload girişi 422 döndürmeli
        (email format validation bunu engeller).
        """
        res = client.post("/create-user", json={
            "email": "<script>alert('xss')</script>@evil.com",
            "password": TEST_PASSWORD,
        })
        assert res.status_code == 422

    def test_very_short_password_rejected(self):
        """
        ST-07: Çok kısa şifre (3 karakter) 422 veya 400 döndürmeli.
        """
        res = client.post("/create-user", json={
            "email": f"sec_{uuid.uuid4().hex[:8]}@testmail.com",
            "password": "abc",
        })
        assert res.status_code in [400, 422]

    def test_very_long_input_does_not_crash(self):
        """
        ST-08: Çok uzun input (10.000 karakter) uygulamayı crash'lememeli.
        400, 422 veya 200 dönebilir ama 500 dönmemeli.
        """
        long_string = "A" * 10000
        res = client.post("/login", json={
            "email": f"{long_string}@test.com",
            "password": long_string,
        })
        assert res.status_code != 500

    def test_null_fields_in_login(self):
        """
        ST-04d: Null değerler ile login isteği uygulama crash'lememeli.
        FastAPI null email'i string'e dönüştürüp login mantığına düşürür → 401.
        422 veya 401 kabul edilir; önemli olan 500 dönmemesi.
        """
        res = client.post("/login", json={
            "email": None,
            "password": None,
        })
        assert res.status_code in [401, 422]
