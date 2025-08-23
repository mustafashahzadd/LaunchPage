import os
from typing import Optional, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from schema_workshop import WorkshopAssets, WorkshopPlan, WorkshopResearch  # <- correct schema module

def _resolve_creds(
    api_key: Optional[str],
    model: Optional[str],
    default_model: str,
) -> tuple[str, str]:
    """Prefer Streamlit secrets, then env vars, then defaults."""
    if not api_key or not model:
        try:
            import streamlit as st
            api_key = api_key or st.secrets.get("GROQ_API_KEY", "")
            model   = model   or st.secrets.get("GROQ_MODEL_PRODUCER", "")
        except Exception:
            pass
    api_key = api_key or os.getenv("GROQ_API_KEY", "")
    model   = model   or os.getenv("GROQ_MODEL_PRODUCER", default_model)
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
    """Generate invite email, poster text, checklist. Key pulled from secrets.toml if available."""
    api_key, model = _resolve_creds(api_key, model, default_model="llama-3.1-70b-versatile")

    llm = ChatGroq(api_key=api_key, model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(WorkshopAssets)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a creative event producer. Generate assets for the workshop. "
         "Use the provided date context to create accurate dates and deadlines in all communications."),
        ("user",
         "{date_context}\n\n"
         "Goal: {goal}\nAudience: {audience}\nConstraints: {constraints}\n\n"
         "Plan: {plan}\nResearch: {research}\n\n"
         "Important: Use the current date provided above when creating:\n"
         "- Registration deadlines in emails\n"
         "- Event dates and times\n"
         "- RSVP deadlines\n"
         "- Preparation timeline mentions\n\n"
         "Return JSON with:\n"
         "- invite_email (string): Include specific dates, registration deadlines, and contact info\n"
         "- poster_text (string): Eye-catching with clear date/time/location info\n"
         "- checklist (string): Organized timeline with specific dates for preparation tasks\n"
         "- google_form_url (string): Leave as null since this will be auto-generated separately)")
    ])

    chain = prompt | structured_llm
    return chain.invoke({
        "goal": goal,
        "audience": audience,
        "constraints": constraints,
        "plan": _dump_json(plan),
        "research": _dump_json(research),
        "date_context": date_context
    })
