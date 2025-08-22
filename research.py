# =============================
# research.py (plain-English output)
# =============================
import textwrap
from groq import Groq


def make_research(api_key: str, product: str, audience: str, brief: str) -> str:
    """
    Returns a plain-English, human-friendly research summary
    as a single Markdown string. NO JSON. Sections are clearly
    labeled so non-technical users can read and copy.
    """
    client = Groq(api_key=api_key)

    system = (
        "You are a concise product researcher.\n"
        "Write in plain English sentences.\n"
        "Output MUST be human-readable Markdown with headings and bullet points.\n"
        "Do NOT return JSON, code blocks, or lists of objects.\n"
        "Keep it short, clear, and skimmable for a non-technical stakeholder.\n"
    )

    user = textwrap.dedent(f"""
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
    """)

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=1200,
    )

    text = resp.choices[0].message.content or ""
    # Ensure no accidental code fences or JSON cues
    text = text.replace("```", "").strip()
    return text
