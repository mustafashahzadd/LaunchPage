from typing import List, Optional
from pydantic import BaseModel

class Task(BaseModel):
    desc: str
    owner: str = "Organizer"
    effort_hrs: int

class Milestone(BaseModel):
    title: str
    due: str
    tasks: List[Task]

class WorkshopPlan(BaseModel):
    agenda: List[str]                 # session schedule
    milestones: List[Milestone]
    success_metrics: List[str]
    risks: List[dict]                 # {risk, mitigation}

class WorkshopResearch(BaseModel):
    topics: List[str]
    risks: List[dict]
    budget_notes: str
    references: List[dict]

class WorkshopAssets(BaseModel):
    invite_email: str
    poster_text: str
    checklist: str
    google_form_url: Optional[str] = None
