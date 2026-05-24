import os
import json
import re
import logging
from typing import List, Dict

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)


def _ollama_chat(messages: list[dict], model: str | None = None):
    if not ollama:
        raise RuntimeError("Ollama python package is not installed")

    target_model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    host = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "").strip()
    options = {
        "temperature": float(os.getenv("OLLAMA_TEMPERATURE", "0.3")),
        "top_p": float(os.getenv("OLLAMA_TOP_P", "0.9")),
        "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "400")),
    }

    if host and hasattr(ollama, "Client"):
        client = ollama.Client(host=host)
        return client.chat(model=target_model, messages=messages, options=options)
    return ollama.chat(model=target_model, messages=messages, options=options)


def _parse_questions_json(raw: str) -> List[Dict]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 3:
            raw = parts[1]
        raw = raw.replace("json", "", 1).strip()
    if "[" in raw and "]" in raw:
        a = raw.find("[")
        b = raw.rfind("]")
        if a != -1 and b != -1 and b > a:
            raw = raw[a : b + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    cleaned: List[Dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        cleaned.append({"text": text})
    return cleaned


def _salvage_questions_from_text(raw: str) -> List[Dict]:
    text = (raw or "").strip()
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[Dict] = []
    for ln in lines:
        if ln.startswith("#") or ln.startswith("**") and ln.endswith("**"):
            continue
        ln = re.sub(r"^\d+[\.\)]\s*", "", ln)
        ln = re.sub(r"^[-*]\s*", "", ln)
        ln = re.sub(r"^\*\*(.*?)\*\*:\s*", "", ln)
        ln = re.sub(r"^\*\*(.*?)\*\*\s*", "", ln)
        ln = " ".join(ln.split()).strip()
        if len(ln) >= 8 and ("?" in ln or len(ln.split()) >= 5):
            out.append({"text": ln})
    return out


def _validate_questions(questions: List[Dict], n_questions: int) -> List[Dict]:
    cleaned: List[Dict] = []
    seen: set[str] = set()
    for item in questions:
        text = (item.get("text") or "").strip()
        if len(text) < 8:
            continue
        text = " ".join(text.split())
        norm = re.sub(r"[^a-zA-Z0-9 ]+", "", text.lower())
        if norm in seen:
            continue
        seen.add(norm)
        cleaned.append({"text": text[:1024]})
        if len(cleaned) >= n_questions:
            break
    return cleaned



def generate_questions(
    *,
    position: str,
    company_name: str | None,
    department_name: str | None,
    domain: str,
    sector: str | None = None,
    cv_text: str | None,
    profile_university: str | None,
    profile_department: str | None,
    profile_class_year: str | None,
    n_questions: int = 6,
    company_context: str | None = None,
) -> List[Dict]:
    if not ollama:
        logger.error("Ollama not available")
        return []

    trimmed_cv = (cv_text or "")[:3000]

    is_technical = (domain or "").lower() == "technical"

    if is_technical:
        system_content = (
            "You are an interview question generator for a TECHNICAL interview.\n"
            "Generate questions that assess the candidate's technical knowledge, tools, and problem-solving skills.\n"
            "Output ONLY a valid JSON list. No markdown, no explanation.\n"
            'Format: [{"text":"..."}]'
        )
        user_content = f"""
Position: {position}
Company: {company_name or '-'}
Department: {department_name or '-'}
Sector: {sector or '-'}

Candidate profile:
- University: {profile_university or '-'}
- Department: {profile_department or '-'}
- Year: {profile_class_year or '-'}

Candidate CV summary:
{trimmed_cv or '-'}

Company research context:
{company_context or 'No specific company information. Ask general questions based on the sector.'}

Generate EXACTLY {n_questions} interview questions in ENGLISH, following this EXACT order:
1) Introduction & Self-Presentation (education, past experiences, who you are)
   Example: "Could you walk us through your background and what led you to apply for this position?"
2) Motivation & Career (why this role/department, career goals, 5-year plan)
   Example: "What motivated you to apply for this role, and where do you see yourself in 5 years?"
3) Position & Industry Knowledge (industry trends, company's position in the market)
   Example: "What do you know about the current trends in this industry and how do you think this company fits into that landscape?"
4) Technical Skills & Tool Knowledge (tools/technologies specific to the role and sector)
   Example: "Which tools and technologies relevant to this position are you most comfortable with, and how have you used them?"
5) Project Experience (managed projects, task distribution, deadlines)
   Example: "Can you describe a project you worked on, how tasks were distributed, and how you handled deadlines?"
6) Learning & Adaptability (how they keep up with new technologies, learning something new for a project, adapting to change)
   Example: "How do you keep up with new technologies, and can you give an example of learning something new for a project?"
7) Team & Organization (teamwork, reporting structure)
   Example: "How do you typically collaborate with teammates, and how do you handle disagreements within a team?"

CRITICAL RULES:
- The candidate is APPLYING to the company, NOT working there.
- 1st question MUST be category 1 (Introduction). Last MUST be category 7.
- Each question must match its category number. Do NOT mix categories.
- Questions must be in ENGLISH. Do NOT use any Turkish words.
- Do NOT quote the CV directly. Ask naturally.
- Do NOT copy the examples. Use them only as style and topic references.
- If university or department name contains Turkish words, translate them to English.

Output ONLY valid JSON. No other text."""
    else:
        system_content = (
            "You are an interview question generator for a GENERAL/HR interview.\n"
            "Generate questions that assess motivation, cultural fit, communication, and interest.\n"
            "Do NOT ask technical questions about tools, technologies, or technical skills.\n"
            "Output ONLY a valid JSON list. No markdown, no explanation.\n"
            'Format: [{"text":"..."}]'
        )
        user_content = f"""
Position: {position}
Company: {company_name or '-'}
Department: {department_name or '-'}
Sector: {sector or '-'}

Candidate profile:
- University: {profile_university or '-'}
- Department: {profile_department or '-'}
- Year: {profile_class_year or '-'}

Candidate CV summary:
{trimmed_cv or '-'}

Company research context:
{company_context or 'No specific company information. Ask general questions based on the sector.'}

Generate EXACTLY {n_questions} interview questions in ENGLISH, following this EXACT order:
1) Introduction & Self-Presentation (education, past experiences, how they describe themselves)
   Example: "Could you walk us through your background and tell us a little about yourself?"
2) Motivation & Interest (why this position/company, what drives them, curiosity to learn)
   Example: "What drew you to apply for this specific position, and what excites you most about this opportunity?"
3) Career Goals (short and long-term goals, where they see themselves in this role)
   Example: "Where do you see yourself in the next few years, and how does this role fit into your career path?"
4) Strengths & Growth Areas (self-awareness, what they do to improve)
   Example: "What would you say is your greatest strength, and is there an area you are actively working to improve?"
5) Company & Industry Knowledge (how well they know the company, their perspective on the sector, depth of research)
   Example: "How familiar are you with our company, and what do you find most interesting about this sector?"
6) Communication & Team Fit (how they work with others, handling disagreements, receiving feedback)
   Example: "How do you handle disagreements with a colleague, and can you give an example of how you resolved one?"

CRITICAL RULES:
- This is a GENERAL/HR interview. Do NOT ask about technical tools, technologies, or technical skills.
- Focus on: motivation, interest, cultural fit, communication, self-awareness.
- The candidate is APPLYING to the company, NOT working there.
- 1st question MUST be category 1 (Introduction). Last MUST be category 6 (Communication & Team Fit).
- Each question must match its category number. Do NOT mix categories.
- Questions must be in ENGLISH. Do NOT use any Turkish words.
- Do NOT quote the CV directly. Ask naturally.
- Do NOT copy the examples. Use them only as style and topic references.
- If university or department name contains Turkish words, translate them to English.

Output ONLY valid JSON. No other text."""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    try:
        response = _ollama_chat(messages=messages, model=model_name)
        raw_text = response.get("message", {}).get("content", "") or "[]"
        parsed = _parse_questions_json(raw_text)
        if not parsed:
            parsed = _salvage_questions_from_text(raw_text)
        valid = _validate_questions(parsed, n_questions)
        if valid:
            return valid
        logger.warning("Ollama invalid question output (try1): %s", raw_text[:300])
    except Exception as e:
        logger.error(f"OLLAMA QUESTION GENERATION ERROR (try1): {repr(e)}")

    repair_messages = messages + [
        {
            "role": "user",
            "content": (
                f"Previous output was invalid. Now return ONLY valid JSON.\n"
                f"Generate exactly {n_questions} items.\n"
                'Format: [{"text":"..."}]\n'
                "Do not write a single word outside the JSON."
            ),
        }
    ]
    try:
        response2 = _ollama_chat(messages=repair_messages, model=model_name)
        raw2 = response2.get("message", {}).get("content", "") or "[]"
        parsed2 = _parse_questions_json(raw2)
        if not parsed2:
            parsed2 = _salvage_questions_from_text(raw2)
        valid2 = _validate_questions(parsed2, n_questions)
        if valid2:
            return valid2
        logger.warning("Ollama invalid question output (try2): %s", raw2[:300])
        return []
    except Exception as e:
        logger.error(f"OLLAMA QUESTION GENERATION ERROR (try2): {repr(e)}")
        return []


def fallback_questions(domain: str, n: int) -> List[Dict]:
    en_technical = [
        "Could you introduce yourself? What is your educational background and what experiences led you to this position?",
        "What is your main motivation for applying to this position? How does it align with your career goals?",
        "What do you see as the most important trends in this industry right now, and how does this role fit into that landscape?",
        "Which tools and technologies used in this position are you familiar with? Which ones have you used in your projects?",
        "Tell me about a project you managed or contributed to. How did you handle task distribution and meet deadlines?",
        "How do you keep up with new technologies, and can you give an example of learning something new for a project?",
        "How do you ensure communication and coordination when working in a team? Can you give an example from your past team experiences?",
    ]
    en_general = [
        "Could you introduce yourself? What is your educational background and what experiences led you to this position?",
        "What is your main motivation for applying to this position and company? What drives your interest in this field?",
        "What are your short and long-term career goals? Where do you see yourself in this role?",
        "What would you say is your greatest strength? Is there an area you'd like to improve, and what are you doing about it?",
        "How well do you know our company and industry? How do you stay updated on developments in this sector?",
        "How do you ensure communication and collaboration when working in a team? How do you handle disagreements?",
    ]

    is_technical = (domain or "").lower() == "technical"
    pool = en_technical if is_technical else en_general
    return [{"text": q} for q in pool[: max(1, min(n, len(pool)))]]


def research_company(
    *,
    company_name: str,
    sector: str | None,
    department_name: str | None,
    position: str | None,
) -> str:
    """Gets company/sector/position context from Ollama."""
    if not ollama:
        logger.warning("Ollama not available for research; returning empty context.")
        return ""

    focus_sector = sector or "N/A"
    focus_dept = department_name or "N/A"
    focus_pos = position or "N/A"

    prompt = f"""Company: {company_name}
Sector: {focus_sector}
Department: {focus_dept}
Position: {focus_pos}

Write everything you know about this company, concisely:

1. What does the company do? (main products/services, customer base)
2. What is its position in the sector? (competitors, market share, reputation)
3. In the {focus_dept} department and {focus_pos} position, what tools, technologies, software, or modules are typically used/required?
4. What technical skills and certifications are important for this position and department?

If you have no information about this specific company, describe what tools, 
technologies and skills are generally expected for {focus_pos} in the {focus_sector} sector's 
{focus_dept} departments at similar companies.

Provide only information, do not ask questions. Maximum 3-4 sentences."""

    try:
        response = _ollama_chat(
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            messages=[
                {"role": "system", "content": "You are a career research assistant. Provide brief, accurate information about the given company, sector and position. If you don't know the specific company, describe the sector in general."},
                {"role": "user", "content": prompt},
            ],
        )
        context = (response.get("message", {}).get("content", "") or "").strip()
        context = " ".join(context.split())[:3000]
        logger.info(f"Company research ok: {len(context)} chars for {company_name}")
        return context
    except Exception as e:
        logger.error(f"Company research error: {e}")
        return ""
