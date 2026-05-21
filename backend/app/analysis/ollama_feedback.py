"""
Ollama-based personalized interview feedback generator.
Calls a local Ollama instance to produce specific, answer-aware feedback in Turkish.
"""

import json
import logging
import os
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


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
Question 1: [one sentence — what you did well and what was missing]
Question 2: [one sentence — what you did well and what was missing]
...continue for all {len(questions_answers)} questions...

**Communication Style**
[1-2 sentences addressed to the interviewee about their pace, fluency, and clarity.]

**Recommendations**
- [actionable recommendation using "you / your"]
- [actionable recommendation using "you / your"]
- [actionable recommendation using "you / your"]

IMPORTANT: Use "you/your" not "the candidate". Write everything in English only."""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.65,
            "num_predict": min(250 + len(questions_answers) * 65, 1400),
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
        with urllib.request.urlopen(req) as resp:
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
