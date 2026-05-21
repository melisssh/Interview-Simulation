"""Load plaintext from a user CV PDF path (shared by analysis and optional reuse elsewhere)."""

from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CV_SECTION_KW_TR = [
    "eğitim", "deneyim", "beceri", "okul", "üniversite", "staj",
    "sertifika", "yabancı dil", "referans", "iletişim",
    "yetenek", "çalışma", "başarı", "kurs", "iş deneyimi",
    "kişisel bilgiler", "eğitim bilgileri", "iş tecrübesi",
    "gönüllü", "seminer", "proje",
]

CV_SECTION_KW_EN = [
    "education", "experience", "skills", "university", "college",
    "internship", "certification", "language",
    "reference", "training", "achievement", "volunteer",
    "work experience", "personal information", "summary",
    "objective", "employment", "proficiency", "project",
]


def is_valid_cv_text(text: str) -> bool:
    """Check if extracted text looks like a real CV.
    
    Requirements:
    - At least 100 characters
    - At least 4 CV section keywords (TR or EN)
    - At least 1 personal info marker (email)
    """
    if not text or len(text.strip()) < 100:
        return False
    lower = text.lower()
    tr_count = sum(1 for kw in CV_SECTION_KW_TR if kw in lower)
    en_count = sum(1 for kw in CV_SECTION_KW_EN if kw in lower)

    # At least 4 CV section keywords
    if tr_count < 4 and en_count < 4:
        return False

    # At least 1 personal info marker (email)
    has_email = "@" in text

    return has_email


def read_cv_plaintext(cv_path: Optional[str], max_chars: int = 12000) -> str:
    if not cv_path:
        return ""
    # Resolve relative paths (stored as "profiles/{user_id}/cv.pdf")
    resolved = cv_path
    if not cv_path.startswith("/"):
        resolved = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),  # backend/app/
            "uploads",
            cv_path,
        )
    try:
        from pypdf import PdfReader

        reader = PdfReader(resolved)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        return text[:max_chars]
    except Exception as e:
        logger.warning("CV read failed (%s): %s", cv_path, e)
        return ""
