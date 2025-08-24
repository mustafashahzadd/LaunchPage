# planner_work.py
from __future__ import annotations
import os
from typing import List, Optional

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
import streamlit as st
from langchain_openai import ChatOpenAI  # ⬅️ new import


# -----------------------
# Pydantic output schema
# -----------------------
class Task(BaseModel):
    desc: str = Field(..., description="Short task description")
    effort_hrs: Optional[float] = Field(default=None, description="Estimated effort in hours")
    owner: Optional[str] = Field(default=None, description="Responsible person/role")

class Milestone(BaseModel):
    title: str
    due: Optional[str] = Field(default=None, description="YYYY-MM-DD or human readable date")
    tasks: List[Task] = Field(default_factory=list)

class WorkshopPlan(BaseModel):
    agenda: List[str] = Field(default_factory=list)
    milestones: List[Milestone] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)

# -----------------------
# LLM (lower temp + cap tokens)
# -----------------------
_GROQ_KEY = os.getenv("GROQ_API_KEY", "")
_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

llm = ChatOpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    model=st.secrets.get("OPENAI_MODEL_PRODUCER", "gpt-5"),
    temperature=0.25,
)

# -----------------------
# Prompts
# -----------------------
_STRUCT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an operations planner. Produce a concise, **practical** workshop plan. "
     "Return content that fits this Pydantic schema exactly: "
     "WorkshopPlan(agenda: List[str], milestones: List[Milestone(title, due, tasks[Task(desc, effort_hrs?, owner?)])], "
     "success_metrics: List[str], risks: List[str]). "
     "HARD LIMITS:\n"
     "- agenda: 5–6 bullets max, one time range per bullet\n"
     "- milestones: 4–5 distinct items max; NO duplicates; each has <= 3 tasks\n"
     "- success_metrics: 4–6 items max\n"
     "- risks: 2–4 items max\n"
     "Do NOT put 'Risks' or 'Success Metrics' as milestone titles. "
     "Use short phrases (<= 14 words each). Dates use YYYY-MM-DD when possible."),
    ("human",
     "Goal: {goal}\nAudience: {audience}\nConstraints: {constraints}\nDate context: {date_context}")
])

_FALLBACK_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an operations planner. Write a **readable plan in Markdown** (no JSON). "
     "Use short, clear sentences. Headings to include exactly:\n"
     "1) Agenda\n2) Milestones\n3) Success Metrics\n4) Risks\n\n"
     "HARD LIMITS:\n"
     "- agenda: max 6 bullets\n- milestones: max 5, each with <= 3 tasks\n"
     "- success metrics: max 6\n- risks: max 4\n"
     "For Milestones, use bullets like:\n"
     "- Title — due YYYY-MM-DD — tasks: task A; task B; task C"),
    ("human",
     "Goal: {goal}\nAudience: {audience}\nConstraints: {constraints}\nDate context: {date_context}\n\n"
     "Return the full plan now.")
])

# -----------------------
# Heuristic parser for Markdown fallback
# -----------------------
def _parse_markdown(md: str) -> WorkshopPlan:
    import re
    section = None
    agenda: List[str] = []
    metrics: List[str] = []
    risks: List[str] = []
    milestones: List[Milestone] = []

    lines = [l.strip() for l in md.splitlines()]
    for ln in lines:
        low = ln.lower()

        if low.startswith("#") or low.endswith(":"):
            title = re.sub(r"^#+\s*", "", ln).strip(": ").lower()
            if "agenda" in title: section = "agenda"
            elif "milestone" in title: section = "milestones"
            elif "metric" in title: section = "metrics"
            elif "risk" in title: section = "risks"
            else: section = None
            continue

        if not ln or section is None:
            continue

        if ln.startswith(("-", "*", "•")):
            item = ln.lstrip("-*• ").strip()
            if section == "agenda":
                if len(agenda) < 6:
                    agenda.append(item)
            elif section == "metrics":
                if len(metrics) < 6:
                    metrics.append(item)
            elif section == "risks":
                if len(risks) < 4:
                    risks.append(item)
            elif section == "milestones":
                if len(milestones) >= 5:
                    continue
                title, due, tasks = None, None, []
                parts = [p.strip() for p in re.split(r"\s+—\s+|\s+-\s+", item)]
                if parts:
                    title = parts[0]
                for p in parts[1:]:
                    if p.lower().startswith("due"):
                        due = p.split(None, 1)[-1].strip()
                    elif p.lower().startswith("tasks:"):
                        tasks_txt = p.split(":", 1)[-1]
                        tasks = [Task(desc=t.strip()) for t in tasks_txt.split(";") if t.strip()][:3]
                milestones.append(Milestone(title=title or item, due=due, tasks=tasks))

    return WorkshopPlan(
        agenda=agenda,
        milestones=milestones,
        success_metrics=metrics,
        risks=risks,
    )

# -----------------------
# Public function
# -----------------------
def make_workshop_plan(goal: str, audience: str, constraints: str, date_context: str) -> dict:
    """
    Returns a dict with:
      - agenda: List[str]
      - milestones: List[Milestone as dict]
      - success_metrics: List[str]
      - risks: List[str]
      - markdown: str  (plain-English plan for users)
    """
    # 1) Try structured output first (with strict schema)
    structured_llm = llm.with_structured_output(WorkshopPlan, strict=True)
    chain = _STRUCT_PROMPT | structured_llm

    try:
        plan: WorkshopPlan = chain.invoke({
            "goal": goal,
            "audience": audience,
            "constraints": constraints,
            "date_context": date_context,
        })

        # Build a concise human-readable summary
        lines = [
            "## Workshop Plan",
            f"**Goal:** {goal}",
            f"**Audience:** {audience}",
            "",
            "### Agenda",
        ]
        lines += [f"- {a}" for a in plan.agenda[:6]]
        lines += ["", "### Milestones"]
        for m in plan.milestones[:5]:
            due = f" — due {m.due}" if m.due else ""
            lines.append(f"- {m.title}{due}")
            if m.tasks:
                lines.append("  - tasks: " + "; ".join(t.desc for t in m.tasks[:3] if t and t.desc))
        if plan.success_metrics:
            lines += ["", "### Success Metrics"]
            lines += [f"- {s}" for s in plan.success_metrics[:6]]
        if plan.risks:
            lines += ["", "### Risks"]
            lines += [f"- {r}" for r in plan.risks[:4]]

        markdown = "\n".join(lines)

        return {
            "agenda": plan.agenda[:6],
            "milestones": [m.model_dump() for m in plan.milestones[:5]],
            "success_metrics": plan.success_metrics[:6],
            "risks": plan.risks[:4],
            "markdown": markdown,
        }

    except Exception:
        # 2) Fallback: readable Markdown, then parse to lists
        md_chain = _FALLBACK_PROMPT | llm
        md_resp = md_chain.invoke({
            "goal": goal,
            "audience": audience,
            "constraints": constraints,
            "date_context": date_context,
        })
        md = getattr(md_resp, "content", "") or str(md_resp)

        parsed = _parse_markdown(md)
        return {
            "agenda": parsed.agenda,
            "milestones": [m.model_dump() for m in parsed.milestones],
            "success_metrics": parsed.success_metrics,
            "risks": parsed.risks,
            "markdown": md,  # show the English plan to the user
        }
