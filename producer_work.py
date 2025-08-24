# producer_work.py
import os
from typing import Optional, Any
import streamlit as st
# from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from schema_workshop import WorkshopAssets, WorkshopPlan, WorkshopResearch

# Optional: Google Forms helper (graceful if missing)
try:
    from forms_api import create_google_form as _create_google_form
except Exception:
    _create_google_form = None



from langchain_openai import ChatOpenAI  # ⬅️ new import

llm = ChatOpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    model=st.secrets.get("OPENAI_MODEL_PRODUCER", "gpt-5"),
    temperature=0.25,
)


def _resolve_creds(
    api_key: Optional[str],
    model: Optional[str],
    default_model: str,
) -> tuple[str, str]:
    """Prefer Streamlit secrets, then env vars, then defaults."""
    api_key = api_key or st.secrets.get("GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    model = model or st.secrets.get("GROQ_MODEL_PRODUCER", "") or os.getenv("GROQ_MODEL_PRODUCER", default_model)
    return api_key, model


def _dump_json(maybe_model: Any) -> str:
    """Accept pydantic model / dict / str and return a JSON-ish string for prompting."""
    if maybe_model is None:
        return "{}"
    try:
        # pydantic v2
        return maybe_model.model_dump_json()
    except Exception:
        pass
    try:
        # pydantic v1
        return maybe_model.json()
    except Exception:
        pass
    if isinstance(maybe_model, dict):
        import json
        return json.dumps(maybe_model, ensure_ascii=False)
    return str(maybe_model)


def make_workshop_assets(
    goal: str,
    audience: str,
    constraints: str,
    plan: Optional[WorkshopPlan],
    research: Optional[WorkshopResearch],
    date_context: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.40,
) -> WorkshopAssets:
    """Generate invite email, poster text, checklist (+ optional Google Form URL)."""
    api_key, model = _resolve_creds(api_key, model, default_model="llama-3.1-70b-versatile")

    # -- try to create a Google Form up front (optional) -----------------------
    form_url: Optional[str] = None
    if _create_google_form:
        try:
            # prefer a (title, description) signature; fall back to (goal, audience)
            try:
                info = _create_google_form(
                    title=f"{goal} — Registration",
                    description=f"Audience: {audience}\nConstraints: {constraints}\n{date_context}",
                ) or {}
            except TypeError:
                info = _create_google_form(goal, audience) or {}

            # Use responderUrl when available; else derive from formId; else editUrl
            form_url = (
                info.get("responderUrl")
                or (f"https://docs.google.com/forms/d/{info.get('formId')}/viewform" if info.get("formId") else None)
                or info.get("editUrl")
            )
        except Exception:
            form_url = None
    # -------------------------------------------------------------------------

    # llm = ChatGroq(api_key=api_key, model=model, temperature=temperature, max_tokens=3000)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         """You are a creative event producer. Generate assets for the workshop.

         IMPORTANT: Use actual line breaks and formatting, NOT escape characters like \\n or \\t.
         Generate clean, readable text with proper paragraphs and spacing.

         For the checklist, format it as a readable timeline with clear dates and tasks, not as code."""),
        ("user",
         """{date_context}

Goal: {goal}
Audience: {audience}
Constraints: {constraints}

Plan: {plan}
Research: {research}

Generate workshop assets with:
1. invite_email: Professional email with proper greeting, body paragraphs, and closing. Use real line breaks.
2. poster_text: Eye-catching poster content with event details. Use real formatting.
3. checklist: A readable preparation timeline with dates and tasks. Format as bullet points, not code.

Remember: Use actual formatting, not \\n or \\t escape characters.""")
    ])

    try:
        # Try structured output first
        structured_llm = llm.with_structured_output(WorkshopAssets)
        chain = prompt | structured_llm

        result = chain.invoke({
            "goal": goal,
            "audience": audience,
            "constraints": constraints,
            "plan": _dump_json(plan),
            "research": _dump_json(research),
            "date_context": date_context
        })

        # Clean up any escape characters
        if hasattr(result, 'invite_email') and isinstance(result.invite_email, str):
            result.invite_email = result.invite_email.replace('\\n', '\n').replace('\\t', '\t')
        if hasattr(result, 'poster_text') and isinstance(result.poster_text, str):
            result.poster_text = result.poster_text.replace('\\n', '\n').replace('\\t', '\t')
        if hasattr(result, 'checklist') and isinstance(result.checklist, str):
            result.checklist = result.checklist.replace('\\n', '\n').replace('\\t', '\t')

        # attach the form URL if present
        if hasattr(result, "google_form_url"):
            result.google_form_url = form_url

        return result

    except Exception:
        # Fallback: Generate without structured output
        fallback_prompt = ChatPromptTemplate.from_messages([
            ("system", "Generate workshop materials. Use real line breaks, not \\n."),
            ("user", """Create workshop materials for: {goal}

Generate:
1. An invite email
2. A poster text
3. A preparation checklist

Use proper formatting with real line breaks.""")
        ])

        response = llm.invoke(fallback_prompt.format_messages(goal=goal))

        # Create a basic WorkshopAssets object
        from schema_workshop import WorkshopAssets as WA

        # You can parse response.content here if you want;
        # we keep your robust defaults and still attach form_url.
        return WA(
            invite_email=(
                f"Dear Students and Teachers,\n\n"
                f"We are excited to invite you to our {goal}.\n\n"
                f"Audience: {audience}\n"
                f"{date_context}\n\n"
                f"Please RSVP by replying to this email.\n\n"
                f"Best regards,\nWorkshop Team"
            ),
            poster_text=(
                f"{goal.upper()}\n\n"
                f"For: {audience}\nWhen: See workshop schedule\nWhere: TBA\n\n"
                f"Join us for an exciting learning experience!\n\n"
                f"{constraints}"
            ),
            checklist=(
                "Workshop Preparation Checklist:\n\n"
                "• Book venue (2 weeks before)\n"
                "• Create materials (1 week before)\n"
                "• Send invitations (1 week before)\n"
                "• Confirm attendees (3 days before)\n"
                "• Setup equipment (1 day before)\n"
                "• Final review (day of event)\n"
                f"\nBudget/Constraints: {constraints}"
            ),
            google_form_url=form_url,  # <-- include it here too
        )
 