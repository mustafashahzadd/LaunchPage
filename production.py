# production.py — robust JSON extraction + safer code cleanup
import json
import re
from typing import Dict, Any, Optional, List
from groq import Groq

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
                        brief: str, research: dict, plan: dict) -> dict:
    """
    Calls the model to produce landing page assets as JSON.
    Returns a dict of files like:
      {
        "index.html": "...",
        "styles.css": "...",
        "script.js": "...",
        "README.md": "...",
        "DEPLOY.md": "..."
      }
    """
    client = Groq(api_key=api_key)

    hooks = research.get("hooks", [])[:5]
    keywords = research.get("keywords", [])[:8]
    sections = plan.get("copy_outline", ["Hero", "Quickstart", "Features", "FAQ", "Footer"])
    repo = plan.get("repo", {})

    system_msg = (
        "You are a code generator that must return ONLY valid JSON.\n"
        "Schema:\n"
        "{\n"
        '  "files": {\n'
        '    "index.html": "<HTML5 string>",\n'
        '    "styles.css": "<CSS string>",\n'
        '    "script.js": "<JS string>",\n'
        '    "README.md": "<Markdown string>",\n'
        '    "DEPLOY.md": "<Markdown string>"\n'
        "  }\n"
        "}\n"
        "No comments, no trailing commas, no prose before/after. JSON only."
    )

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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()

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
                         product: str, research: dict) -> str:
    """Generate a custom file based on user prompt."""
    client = Groq(api_key=api_key)

    keywords = ", ".join(research.get("keywords", [])[:5])

    type_instructions = {
        "HTML": "Generate semantic HTML5 code with proper structure.",
        "CSS": "Generate modern CSS with variables and responsive design.",
        "JS": "Generate vanilla JavaScript ES6+ code.",
    }

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": f"{type_instructions.get(file_type, 'Generate code')} "
                           f"Return ONLY the code, no explanations or fences."
            },
            {
                "role": "user",
                "content": f"""Create {file_type} for {product}.
User request: {prompt}
Keywords: {keywords}

Return ONLY the code (no comments, no fences).
"""
            },
        ],
        temperature=0.2,
        max_tokens=2000,
    )

    content = response.choices[0].message.content or ""
    return clean_markdown(content)
