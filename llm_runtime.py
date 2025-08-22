# llm_runtime.py
import os, json, time, re

# Optional: use Streamlit secrets if present
try:
    import streamlit as st
    _SECRETS = dict(st.secrets)
except Exception:
    _SECRETS = {}

def _get_secret(key: str, default: str | None = None) -> str | None:
    # priority: env var -> st.secrets -> default
    return os.getenv(key) or _SECRETS.get(key, default)

# --- Provider selection
PROVIDER = (_get_secret("LLM_PROVIDER", "groq") or "groq").lower()

def _groq_client():
    from groq import Groq
    key = _get_secret("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Missing GROQ_API_KEY (set in env or .streamlit/secrets.toml)")
    return Groq(api_key=key)

def _openai_client():
    from openai import OpenAI
    key = _get_secret("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY (set in env or .streamlit/secrets.toml)")
    return OpenAI(api_key=key)

_CODEFENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

def _ensure_json(text: str) -> dict:
    # remove code fences if present
    if text.strip().startswith("```"):
        text = _CODEFENCE_RE.sub("", text).strip()
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise

def chat_json(system: str, user: str, *, model: str, temperature: float = 0.2, retries: int = 1) -> dict:
    """
    Call current provider and return parsed JSON.
    We enforce JSON output via instruction; parse defensively; retry once with stronger hint.
    """
    if PROVIDER == "groq":
        client = _groq_client()
        msgs = [
            {"role": "system", "content": system + " Return STRICT JSON only. No backticks."},
            {"role": "user", "content": user},
        ]
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=msgs,
                temperature=temperature,
                max_tokens=2048,          # <- works across Groq SDK versions
                top_p=0.95,
            )
            text = resp.choices[0].message.content
            return _ensure_json(text)
        except Exception as e:
            if retries > 0:
                time.sleep(0.4)
                return chat_json(system, user + "\n\nReturn STRICT JSON ONLY.", model=model, temperature=0.1, retries=retries-1)
            raise e

    elif PROVIDER == "openai":
        client = _openai_client()
        msgs = [
            {"role": "system", "content": system + " Return STRICT JSON only. No backticks."},
            {"role": "user", "content": user},
        ]
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=msgs,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            if retries > 0:
                time.sleep(0.4)
                msgs[-1]["content"] += "\n\nReturn STRICT JSON ONLY."
                resp = client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                return json.loads(resp.choices[0].message.content)
            raise e

    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {PROVIDER}")
