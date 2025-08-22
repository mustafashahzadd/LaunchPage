# schema.py
from typing import List, Dict
from pydantic import BaseModel, Field, conint

# ---------- Research ----------
class Competitor(BaseModel):
    name: str
    angle: str

class Reference(BaseModel):
    title: str
    url: str

class RiskItem(BaseModel):
    risk: str
    mitigation: str

class ResearchOut(BaseModel):
    competitors: List[Competitor] = Field(..., description="2–3 closest dev tools or pages")
    hooks: List[str] = Field(..., description="5 short, code-first hooks for the landing page")
    keywords: List[str] = Field(..., description="6–10 SEO keywords developers would search")
    risks: List[RiskItem] = Field(..., description="2–3 delivery risks with concrete mitigations")
    references: List[Reference] = Field(..., description="3–4 trustworthy sources")

def clamp_research(d: dict) -> dict:
    d["competitors"] = (d.get("competitors") or [])[:3]
    d["hooks"]       = (d.get("hooks") or [])[:5]
    d["keywords"]    = (d.get("keywords") or [])[:10]
    d["risks"]       = (d.get("risks") or [])[:3]
    d["references"]  = (d.get("references") or [])[:4]
    return d

# ---------- Planner ----------
class Task(BaseModel):
    desc: str
    effort_hrs: conint(ge=1, le=8)

class Milestone(BaseModel):
    title: str
    due_days: conint(ge=1, le=10)
    tasks: List[Task] = Field(..., min_items=2, max_items=5)

class RepoSettings(BaseModel):
    name: str
    description: str
    private: bool
    default_branch: str
    license: str  # "None" | "MIT" | "Apache-2.0"
    init_readme: bool
    add_ci: bool

class FileItem(BaseModel):
    path: str
    why: str

class PlanOut(BaseModel):
    milestones: List[Milestone] = Field(..., min_items=3, max_items=10)  # allow extra; clamp later
    success_metrics: List[str] = Field(..., min_items=3, max_items=10)
    copy_outline: List[str]
    repo: RepoSettings
    file_manifest: List[FileItem] = Field(default_factory=list)

def clamp_plan(d: dict, max_ms: int = 5) -> dict:
    d["milestones"] = (d.get("milestones") or [])[:max_ms]
    for m in d["milestones"]:
        m["tasks"] = (m.get("tasks") or [])[:5]
    d["success_metrics"] = (d.get("success_metrics") or [])[:6]
    d["copy_outline"]    = (d.get("copy_outline") or [])[:8]
    d["file_manifest"]   = (d.get("file_manifest") or [])[:20]
    return d

# ---------- Producer ----------
class FilesOut(BaseModel):
    files: Dict[str, str] = Field(..., description="filename -> content")

def clamp_files(d: dict) -> dict:
    d["files"] = d.get("files") or {}
    return d
