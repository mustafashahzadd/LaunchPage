# =============================
# planner.py (plain-English output) — OpenAI version
# =============================
import textwrap
from openai import OpenAI




def make_plan(api_key: str,
              product: str,
              audience: str,
              brief: str,
              research: str,
              repo_name: str,
              repo_desc: str,
              private: bool,
              license: str,
              add_ci: bool) -> str:
    client = OpenAI(api_key=api_key)

    system = (
        "You are a product planner.\n"
        "Write in plain English sentences.\n"
        "Output MUST be human-readable Markdown with headings and bullets.\n"
        "Do NOT return JSON, tables of objects, or code blocks.\n"
        "Use short sentences and keep each bullet under 18 words.\n"
    )

    user = f"""
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
# Milestones — 5 bullets; each: title — goal — owner (placeholder) — ETA in days
# Success Metrics — 6 bullets, measurable
# Copy Outline — sections in order (Hero, Quickstart, Features, Playground, FAQ, Footer + any others)
# Risks & Mitigations — 3 bullets
# Repo Settings — short bullets for privacy, license, CI choice

Only return the Markdown. No JSON.
""".strip()

    resp = client.responses.create(
        model="gpt-5",
        input=f"{system}\n\n{user}",
    )

    text = (resp.output_text or "").replace("```", "").strip()
    return text
