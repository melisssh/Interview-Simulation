import os
import logging

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
