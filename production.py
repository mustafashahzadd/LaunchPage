# production.py — robust JSON extraction + safer code cleanup
import json
import re
from typing import Dict, Any, Optional, List
from openai import OpenAI 

# ---------------------------
# Utilities
# ---------------------------

def clean_markdown(content: str) -> str:
    """Remove markdown code fences & inline ticks from model output."""
    # Remove fenced code blocks but keep inner text if it's not labeled as code
    content = re.sub(r"```(?:json|javascript|js|html|css|md|markdown)?\s*([\s\S]*?)\s*```", r"\1", content, flags=re.IGNORECASE)
    # Remove stray inline backticks
    content = re.sub(r"`([^`]*)`", r"\1", content)
    return content.strip()


def _all_balanced_json_candidates(text: str) -> List[str]:
    """
    Find all balanced {...} regions in text and return the substrings.
    We then try json.loads on each, preferring ones that parse and have 'files'.
    """
    starts = []
    cands = []
    for i, ch in enumerate(text):
        if ch == '{':
            starts.append(i)
        elif ch == '}' and starts:
            start = starts.pop()
            cands.append(text[start:i+1])
    # Prefer longer candidates first (more likely to be the full object)
    cands.sort(key=len, reverse=True)
    return cands


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort JSON extraction:
      1) Look for fenced ```json blocks
      2) Try all balanced-brace substrings
      3) As a last resort, try first-to-last brace
    Returns a dict or None.
    """
    if not text:
        return None

    # 1) JSON code fences
    fence_matches = re.findall(r"```json\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    for block in fence_matches:
        try:
            return json.loads(block)
        except Exception:
            pass  # try others

    # 2) Balanced brace candidates
    for cand in _all_balanced_json_candidates(text):
        try:
            return json.loads(cand)
        except Exception:
            continue

    # 3) First/last brace fallback
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(text[first:last+1])
        except Exception:
            return None

    return None


# ---------------------------
# Main API
# ---------------------------

def make_landing_assets(api_key: str, product: str, audience: str,
                        brief: str, research: dict | str, plan: dict | str) -> dict:
    """
    Calls the model to produce landing page assets as JSON.
    Accepts research/plan as dict **or** Markdown strings.
    """
    client = OpenAI(api_key=api_key)

    import re

    def _section(md: str, title: str) -> str:
        """Return text under a markdown heading until the next heading or end."""
        # matches '# Hooks' or '## Hooks' etc, case-insensitive
        pat = rf"(?mi)^\s*#{1,6}\s*{re.escape(title)}\s*\n(.*?)(?=^\s*#|\Z)"
        m = re.search(pat, md)
        return (m.group(1).strip() if m else "").strip()

    def _bullets(md_block: str) -> list[str]:
        """Parse -/• bullets into a list."""
        lines = []
        for line in md_block.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*•]\s*", "", line)
            lines.append(line)
        return lines

    # ------- research: dict OR markdown -------
    if isinstance(research, dict):
        hooks = (research.get("hooks") or [])[:5]
        keywords = (research.get("keywords") or [])[:8]
    else:
        text = str(research)
        hooks_blk = _section(text, "Hooks")
        keys_blk  = _section(text, "Keywords")
        hooks = _bullets(hooks_blk)[:5]
        # keywords are requested as a single comma-separated line in research.py
        if keys_blk:
            first_line = keys_blk.splitlines()[0]
            keywords = [k.strip() for k in first_line.split(",") if k.strip()][:8]
        else:
            keywords = []

    # ------- plan: dict OR markdown -------
    if isinstance(plan, dict):
        sections = plan.get("copy_outline", []) or ["Hero", "Quickstart", "Features", "FAQ", "Footer"]
        repo     = plan.get("repo", {}) or {}
    else:
        ptext    = str(plan)
        outline  = _section(ptext, "Copy Outline") or _section(ptext, "Copy Outline —")
        sections = _bullets(outline) or ["Hero", "Quickstart", "Features", "FAQ", "Footer"]
        repo     = {}  # not present in the plain-English plan

    system_msg = (
        "You are a code generator that must return ONLY valid JSON.\n"
        "Schema:\n"
        "{\n"
        '  \"files\": {\n'
        '    \"index.html\": \"<HTML5 string>\",\n'
        '    \"styles.css\": \"<CSS string>\",\n'
        '    \"script.js\": \"<JS string>\",\n'
        '    \"README.md\": \"<Markdown string>\",\n'
        '    \"DEPLOY.md\": \"<Markdown string>\"\n'
        "  }\n"
        "}\n"
        "No comments, no trailing commas, no prose before/after. JSON only."
    )
    # (…keep the rest of the function unchanged…)


    user_msg = f"""Create a developer-focused landing page.

Product: {product}
Audience: {audience}
Brief: {brief}

Hooks: {', '.join(hooks)}
Keywords: {', '.join(keywords)}
Sections: {', '.join(sections)}

Requirements:
- Mobile-first responsive
- Dark mode support (CSS prefers-color-scheme)
- Copy-to-clipboard for code blocks (JS)
- Accessible semantics (landmarks, labels)
- SEO basics (title, meta description, open graph)
- No frameworks: pure HTML/CSS/JS
- Keep inline <script> minimal; use script.js for logic

Return ONLY JSON using the schema above.
"""

    resp = client.responses.create(
    model="gpt-5",
    input=f"{system_msg}\n\n{user_msg}",
   
)
    raw = (resp.output_text or "").strip()


    # Try to extract JSON robustly
    obj = _extract_json_object(raw)
    if not obj:
        # One more attempt after stripping markdown/code fences
        obj = _extract_json_object(clean_markdown(raw))

    if not obj:
        # If still nothing, return empty; Streamlit UI can show error
        return {}

    files = obj.get("files", obj)
    if not isinstance(files, dict):
        return {}

    # Add license if requested
    if repo.get("license") == "MIT":
        files["LICENSE"] = get_mit_license()

    # Add CI if requested
    if repo.get("add_ci"):
        files[".github/workflows/ci.yml"] = get_ci_workflow()

    return files


def get_mit_license() -> str:
    return """MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"""


def get_ci_workflow() -> str:
    return """name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: npx htmlhint index.html
      - run: npx stylelint styles.css
"""


def generate_custom_file(api_key: str, file_type: str, prompt: str,
                         product: str, research: dict | str) -> str:
    """Generate a custom file based on user prompt."""
    client = OpenAI(api_key=api_key)

    # ----- keywords from research: dict OR markdown string -----
    if isinstance(research, dict):
        kw_list = (research.get("keywords", []) or [])[:5]
    else:
        text = str(research)
        # pull the first line under a "Keywords" heading and split by commas
        m = re.search(r"(?mi)^\s*#{1,6}\s*Keywords\s*\n(.*)", text)
        if m:
            first_line = m.group(1).strip()
            kw_list = [k.strip() for k in first_line.split(",") if k.strip()][:5]
        else:
            kw_list = []
    keywords = ", ".join(kw_list)

    type_instructions = {
        "HTML": "Generate semantic HTML5 code with proper structure.",
        "CSS": "Generate modern CSS with variables and responsive design.",
        "JS": "Generate vanilla JavaScript ES6+ code.",
    }

    resp = client.responses.create(
    model="gpt-5",
    input="Return ONLY the code (no comments, no fences).",
)

    content = (resp.output_text or "")
    return clean_markdown(content)
