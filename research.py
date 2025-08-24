# =============================
# research.py (plain-English output) — OpenAI version
# =============================
import textwrap
from openai import OpenAI


from openai import OpenAI

def make_research(api_key: str, product: str, audience: str, brief: str) -> str:
    client = OpenAI(api_key=api_key)

    system = (
        "You are a concise product researcher.\n"
        "Write in plain English sentences.\n"
        "Output MUST be human-readable Markdown with headings and bullet points.\n"
        "Do NOT return JSON, code blocks, or lists of objects.\n"
        "Keep it short, clear, and skimmable for a non-technical stakeholder.\n"
    )

    user = f"""
Research the landing page inputs for:
• Product: {product}
• Audience: {audience}
• Brief: {brief}

Please produce:
# Overview — 2–3 sentences
# Top Competitors — 3 concise bullets
# Hooks — 5 compelling one-line messages
# Keywords — 8 short, comma-separated phrases (single line)
# Risks — 3 one-line risks with a mitigation phrase each

Only return the Markdown. No JSON.
""".strip()

    # Responses API: single 'input' string (system + user)
    resp = client.responses.create(
        model="gpt-5",
        input=f"{system}\n\n{user}",
    )

    text = (resp.output_text or "").replace("```", "").strip()
    return text
