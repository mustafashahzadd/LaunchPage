# =============================
# planner.py (plain-English output)
# =============================
import textwrap
from groq import Groq


def make_plan(api_key: str,
              product: str,
              audience: str,
              brief: str,
              research: str,  # now accepts the plain-English research text
              repo_name: str,
              repo_desc: str,
              private: bool,
              license: str,
              add_ci: bool) -> str:
    """
    Returns a plain-English, human-friendly execution plan as a single Markdown string.
    NO JSON. Designed to be readable and copyable by non-technical users.
    """
    client = Groq(api_key=api_key)

    system = (
        "You are a product planner.\n"
        "Write in plain English sentences.\n"
        "Output MUST be human-readable Markdown with headings and bullets.\n"
        "Do NOT return JSON, tables of objects, or code blocks.\n"
        "Use short sentences and keep each bullet under 18 words.\n"
    )

    user = textwrap.dedent(f"""
        Based on this prior research (verbatim below), create a concise plan for a landing page project.

        --- Research ---
        {research}
        --- End Research ---

        Product: {product}
        Audience: {audience}
        Brief: {brief}
        Repo: name={repo_name}, desc={repo_desc}, private={private}, license={license}, CI={add_ci}

        Please produce:
        # One-Line Strategy — 1 sentence
        # Milestones — 5 bullets; each bullet: title — goal — owner (placeholder) — ETA in days
        # Success Metrics — 6 bullets, measurable
        # Copy Outline — list sections in order (Hero, Quickstart, Features, Playground, FAQ, Footer + any others)
        # Risks & Mitigations — 3 bullets
        # Repo Settings — short bullets for privacy, license, CI choice

        Only return the Markdown. No JSON.
    """)

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=1600,
    )

    text = resp.choices[0].message.content or ""
    text = text.replace("```", "").strip()
    return text
