"""
Ollama-based personalized interview feedback generator.
Calls a local Ollama instance to produce specific, answer-aware feedback in Turkish.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_URL   = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://localhost:11434"))
OLLAMA_MODEL = os.getenv("OLLAMA_ANALYSIS_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))


def ollama_technical_score_0_100(question: str, answer: str, language: str = "tr") -> Optional[int]:
    """
    Ask the local Ollama model to score technical correctness of an answer (0-100).
    Returns an int or None on failure.
    """
    lang_note = "Turkish" if (language or "tr").lower().startswith("tr") else "English"
    prompt = (
        f"You are a strict technical interview evaluator. Language context: {lang_note}.\n"
        f"Question:\n{question[:1500]}\n\n"
        f"Candidate answer:\n{answer[:4000]}\n\n"
        "Rate the technical correctness, depth, and relevance of the answer on a scale 0-100.\n"
        'Reply with a single JSON object only, no extra text: {"score": <integer 0-100>}\n'
    )

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 24,
        },
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())
            text = (result.get("response") or "").strip()
    except urllib.error.URLError as e:
        logger.warning("Ollama technical score unreachable: %s", e)
        return None
    except Exception as e:
        logger.warning("Ollama technical score error: %s", e)
        return None

    m = re.search(r'"score"\s*:\s*(\d+)', text)
    if not m:
        m = re.search(r'\b(\d{1,3})\b', text)
    if not m:
        return None
    val = int(m.group(1))
    return max(0, min(100, val))


def generate_ollama_feedback(
    questions_answers: list,   # [{"question": str, "answer": str}, ...]
    metrics: dict,
    domain: str = "general",
    language: str = "tr",
) -> str:
    """
    Generate personalized interview feedback using a local Ollama model.
    Returns an English feedback string, or "" on failure.
    """
    if not questions_answers:
        return ""

    qa_lines = []
    for i, qa in enumerate(questions_answers, 1):
        q = (qa.get("question") or "").strip()
        a = (qa.get("answer")   or "").strip()
        if q or a:
            qa_lines.append(f"Question {i}: {q}")
            qa_lines.append(f"Answer {i}: {a if a else '(no answer)'}")
            qa_lines.append("")
    qa_text = "\n".join(qa_lines).strip()

    # Build metric summary
    metric_lines = [
        f"- Content Score      : {metrics.get('content_score',  'N/A')}/100",
        f"- Relevance Score    : {metrics.get('relevance_score','N/A')}/100",
        f"- Speech Rate        : {metrics.get('speech_rate_wpm','N/A')} WPM (ideal: 120–150)",
        f"- Pause Control      : {metrics.get('pause_frequency_score','N/A')}/100",
    ]
    if metrics.get("eye_contact_score") is not None:
        metric_lines.append(f"- Eye Contact        : {metrics['eye_contact_score']}/100")
    if metrics.get("posture_score") is not None:
        metric_lines.append(f"- Posture Score      : {metrics['posture_score']}/100")
    if metrics.get("head_stability_score") is not None:
        metric_lines.append(f"- Head Stability     : {metrics['head_stability_score']}/100")
    metric_text = "\n".join(metric_lines)

    domain_en = "Technical" if (domain or "").lower() == "technical" else "General / Behavioral"

    prompt = f"""You are an experienced interview coach giving direct feedback to the interviewee. \
Address them as "you" / "your" throughout. Your response MUST be written entirely in English, \
regardless of the language of the questions or answers below.

Interview Type: {domain_en}

QUESTIONS AND ANSWERS:
{qa_text}

METRICS:
{metric_text}

Write your feedback using EXACTLY this format. Do not add any extra text outside the format:

**Answer Analysis**
(Write one line for EVERY question, Question 1 through Question {len(questions_answers)})
Question 1: [one sentence — if the answer was strong, say what was done well. \
If the answer was weak or incomplete, say what was missing. Do NOT force both.]
Question 2: [same rule — strong answers get praise only, weak answers get specific critique only]
...continue for all {len(questions_answers)} questions...

**Communication Style**
[1-2 sentences addressed to the interviewee about their pace, fluency, and clarity.]

**Recommendations**
- [actionable recommendation using "you / your"]
- [actionable recommendation using "you / your"]
- [actionable recommendation using "you / your"]

IMPORTANT:
- Use "you/your" not "the candidate".
- Write everything in English only.
- Do not always mention weaknesses if the answer was sufficient."""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.65,
            "num_predict": min(180 + len(questions_answers) * 40, 600),
            "top_p": 0.9,
        },
    }).encode()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            result = json.loads(body)
            text = (result.get("response") or "").strip()
            logger.info("Ollama feedback generated: %d chars (model=%s)", len(text), OLLAMA_MODEL)
            return text
    except urllib.error.URLError as e:
        logger.warning("Ollama unreachable (%s) — skipping personalized feedback", e)
        return ""
    except Exception as e:
        logger.error("Ollama feedback error: %s", e)
        return ""
