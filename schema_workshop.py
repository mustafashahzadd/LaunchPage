from typing import List, Optional
from pydantic import BaseModel, Field


# ---------- leaf objects (no extra keys allowed) ----------
class RiskItem(BaseModel):
    risk: str
    mitigation: str
    # tell Pydantic/OpenAI schema: no extra properties allowed
    model_config = {"extra": "forbid"}


class ReferenceItem(BaseModel):
    title: str
    url: str
    model_config = {"extra": "forbid"}


class Task(BaseModel):
    desc: str
    owner: str = "Organizer"
    effort_hrs: int = Field(..., ge=0)
    model_config = {"extra": "forbid"}


class Milestone(BaseModel):
    title: str
    due: str  # keep as string (e.g., "2025-09-03" or "10 days")
    tasks: List[Task]
    model_config = {"extra": "forbid"}


# ---------- top-level models ----------
class WorkshopPlan(BaseModel):
    agenda: List[str]                       # session schedule
    milestones: List[Milestone]
    success_metrics: List[str]
    risks: List[RiskItem]                   # explicit object, not dict
    model_config = {"extra": "forbid"}


class WorkshopResearch(BaseModel):
    topics: List[str]
    risks: List[RiskItem]                   # explicit object, not dict
    budget_notes: str
    references: List[ReferenceItem]         # explicit object, not dict
    model_config = {"extra": "forbid"}


class WorkshopAssets(BaseModel):
    invite_email: str
    poster_text: str
    checklist: str
    google_form_url: Optional[str] = None
    model_config = {"extra": "forbid"}
