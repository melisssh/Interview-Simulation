"""
Unit Tests — AI Interview Simulator
Tests individual functions without database or network connections.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─────────────────────────────────────────────
# 1. Password Hashing
# ─────────────────────────────────────────────

from app.routers.auth import hash_password, verify_password

class TestPasswordHashing:

    def test_hash_is_not_plaintext(self):
        """Hashed password should not equal the original."""
        hashed = hash_password("testpassword123")
        assert hashed != "testpassword123"

    def test_correct_password_verifies(self):
        """Correct password should pass verification."""
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_wrong_password_fails(self):
        """Wrong password should fail verification."""
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_empty_password_hashes(self):
        """Empty password should still hash without error."""
        hashed = hash_password("")
        assert hashed != ""

    def test_same_password_different_hashes(self):
        """Same password hashed twice should produce different hashes (salt)."""
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2


# ─────────────────────────────────────────────
# 2. JWT Token
# ─────────────────────────────────────────────

from app.routers.auth import create_access_token
import jwt
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class TestJWT:

    def test_token_is_created(self):
        """Token should be a non-empty string."""
        token = create_access_token({"user_id": 1, "email": "test@test.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_user_id(self):
        """Decoded token should contain the user_id."""
        token = create_access_token({"user_id": 42, "email": "test@test.com"})
        secret = os.getenv("JWT_SECRET_KEY")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        assert payload["user_id"] == 42

    def test_token_contains_email(self):
        """Decoded token should contain the email."""
        token = create_access_token({"user_id": 1, "email": "selin@test.com"})
        secret = os.getenv("JWT_SECRET_KEY")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        assert payload["email"] == "selin@test.com"

    def test_different_users_get_different_tokens(self):
        """Two different users should get different tokens."""
        t1 = create_access_token({"user_id": 1, "email": "a@test.com"})
        t2 = create_access_token({"user_id": 2, "email": "b@test.com"})
        assert t1 != t2


# ─────────────────────────────────────────────
# 3. WPM (Words Per Minute)
# ─────────────────────────────────────────────

from app.analysis.speech_metrics import words_per_minute

class TestWPM:

    def test_normal_speech_rate(self):
        """120 words in 60 seconds = 120 WPM."""
        assert words_per_minute(120, 60.0) == 120

    def test_fast_speech(self):
        """200 words in 60 seconds = 200 WPM."""
        assert words_per_minute(200, 60.0) == 200

    def test_zero_duration_returns_none(self):
        """Zero duration should return None (no valid measurement)."""
        assert words_per_minute(100, 0.0) is None

    def test_zero_words_returns_none(self):
        """Zero words should return None (no speech)."""
        assert words_per_minute(0, 60.0) is None

    def test_half_minute(self):
        """60 words in 30 seconds = 120 WPM."""
        assert words_per_minute(60, 30.0) == 120


# ─────────────────────────────────────────────
# 4. Scoring Functions
# ─────────────────────────────────────────────

from app.analysis.scoring import pause_control_from_answer_text

class TestScoring:

    def test_pause_control_clean_text(self):
        """Clean English text should score high on pause control."""
        score = pause_control_from_answer_text("I have extensive experience in software development and team collaboration.")
        assert score >= 70

    def test_pause_control_filler_text(self):
        """Text with many filler words should score lower."""
        score = pause_control_from_answer_text("um like you know um like uh well you know um")
        assert score < 70

    def test_pause_control_empty_text(self):
        """Empty text should return default score."""
        score = pause_control_from_answer_text("")
        assert score == 45

    def test_pause_control_range(self):
        """Score should always be between 0 and 100."""
        score = pause_control_from_answer_text("um uh like um uh like um uh like um uh like um uh")
        assert 0 <= score <= 100
