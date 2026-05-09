"""Optional Gemini-based scoring for technical answers (JSON-only prompt)."""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


def gemini_technical_score_0_100(question: str, answer: str, language: str = "tr") -> Optional[int]:
    """
    Returns 0–100 or None if API key missing / call failed.
    """
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None
    model = (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip()
    if "/" in model:
        model = model.split("/")[-1]

    lang_note = "Turkish" if (language or "tr").lower().startswith("tr") else "English"
    prompt = (
        f"You are an interview evaluator. Language context: {lang_note}.\n"
        f"Question:\n{question[:2000]}\n\n"
        f"Candidate answer:\n{answer[:6000]}\n\n"
        "Rate technical correctness, depth, and relevance to the question on a scale 0–100.\n"
        'Reply with a single JSON object only, no markdown: {"score": <integer 0-100>}\n'
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.15, "maxOutputTokens": 128},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("Gemini technical score failed: %s", e)
        return None
    except Exception as e:
        logger.warning("Gemini technical score unexpected error: %s", e)
        return None

    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        return None

    m = re.search(r"\{[^}]*\"score\"\s*:\s*(\d+)[^}]*\}", text)
    if not m:
        m = re.search(r"\"score\"\s*:\s*(\d+)", text)
    if not m:
        return None
    val = int(m.group(1))
    return max(0, min(100, val))
