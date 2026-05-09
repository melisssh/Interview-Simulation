"""Load plaintext from a user CV PDF path (shared by analysis and optional reuse elsewhere)."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def read_cv_plaintext(cv_path: Optional[str], max_chars: int = 12000) -> str:
    if not cv_path:
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(cv_path)
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
        return text[:max_chars]
    except Exception as e:
        logger.warning("CV read failed (%s): %s", cv_path, e)
        return ""
