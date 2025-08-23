import os
from typing import Optional, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from schema_workshop import WorkshopResearch  # <- correct schema module

def _resolve_creds(
    api_key: Optional[str],
    model: Optional[str],
    default_model: str,
) -> tuple[str, str]:
    """Prefer Streamlit secrets, then env vars, then defaults."""
    if not api_key or not model:
        try:
            import streamlit as st  # available in your app
            api_key = api_key or st.secrets.get("GROQ_API_KEY", "")
            model   = model   or st.secrets.get("GROQ_MODEL", "")
        except Exception:
            pass
    api_key = api_key or os.getenv("GROQ_API_KEY", "")
    model   = model   or os.getenv("GROQ_MODEL", default_model)
    return api_key, model

def make_workshop_research(
    goal: str,
    audience: Optional[str],
    constraints: Optional[str],
    date_context: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.30,
) -> WorkshopResearch:
    """Research topics/risks/budget using ChatGroq; reads key from secrets.toml if present."""
    api_key, model = _resolve_creds(api_key, model, default_model="llama-3.1-8b-instant")

    llm = ChatGroq(api_key=api_key, model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(WorkshopResearch)

    prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are a researcher. Provide topics, risks, and budget notes for a workshop. "
     "Use the provided date context for time-sensitive research and recommendations."),
    ("user",
     "{date_context}\n\n"
     "Workshop Goal: {goal}\nAudience: {audience}\nConstraints: {constraints}\n\n"
     "Consider the current date when researching:\n"
     "- Seasonal considerations and timing\n"
     "- Current trends and technologies relevant to the workshop\n"
     "- Time-sensitive budget considerations\n"
     "- Venue availability and booking lead times\n\n"
     "Return JSON with:\n"
     "- topics (list of strings)\n"
     "- risks (list of objects with keys 'risk' and 'mitigation')\n"
     "- budget_notes (string - plain text)\n"
     "- references (list of objects with keys 'title' and 'url')"
    )
])


    chain = prompt | structured_llm
    return chain.invoke({
        "goal": goal,
        "audience": audience,
        "constraints": constraints,
        "date_context": date_context
    })
