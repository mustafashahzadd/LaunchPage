import os
from typing import Optional
from pydantic import ValidationError
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from schema_workshop import WorkshopPlan  # <- correct schema module

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
            model   = model   or st.secrets.get("GROQ_MODEL_PLANNER", "")
        except Exception:
            pass
    api_key = api_key or os.getenv("GROQ_API_KEY", "")
    model   = model   or os.getenv("GROQ_MODEL_PLANNER", default_model)
    return api_key, model

def make_workshop_plan(
    goal: str,
    audience: Optional[str],
    constraints: Optional[str],
    date_context: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.20,
) -> WorkshopPlan:
    """Structured workshop plan via ChatGroq; reads key from secrets.toml if present."""
    api_key, model = _resolve_creds(api_key, model, default_model="llama-3.1-70b-versatile")

    llm = ChatGroq(api_key=api_key, model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(WorkshopPlan)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a meticulous event planner. "
         "Generate a structured workshop plan with agenda, milestones, success metrics, and risks. "
         "Use the provided current date as the reference point for all scheduling and milestone planning."),
        ("user",
         "{date_context}\n\n"
         "Goal: {goal}\nAudience: {audience}\nConstraints: {constraints}\n\n"
         "Important: Use the current date provided above as your reference point for scheduling.\n\n"
         "Rules:\n"
         "- Agenda: 3–6 sessions with times\n"
         "- 2–4 milestones with realistic due dates (YYYY-MM-DD) based on today's date\n"
         "- Each milestone: 2–5 tasks; effort_hrs between 1–8\n"
         "- success_metrics must be measurable\n"
         "- Include risks and mitigations\n"
         "- Consider lead times for venue booking, material preparation, etc.\n"
         "- Account for weekends and holidays when setting milestone dates\n"
         "Return VALID JSON only.")
    ])

    chain = prompt | structured_llm
    try:
        return chain.invoke({
            "goal": goal,
            "audience": audience,
            "constraints": constraints,
            "date_context": date_context
        })
    except ValidationError:
        # Retry with stricter instruction if the model goes verbose
        return chain.invoke({
            "goal": goal,
            "audience": audience,
            "constraints": (constraints or "") + " STRICT JSON ONLY.",
            "date_context": date_context
        })
