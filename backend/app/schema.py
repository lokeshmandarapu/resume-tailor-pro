"""Single source of truth for the resume data model (JSON Resume-inspired).
All renderers (DOCX / PDF) read from these models. Bullets carry an `evidence`
field so every tailored claim can be traced back to the master resume."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class Experience(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    dates: str = ""              # e.g. "Jan 2023 - Jun 2024"
    stack: str = ""              # optional one-line tech stack under the title
    bullets: List[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str = ""
    stack: str = ""
    bullets: List[str] = Field(default_factory=list)


class Education(BaseModel):
    school: str = ""
    location: str = ""
    dates: str = ""
    degree: str = ""
    coursework: str = ""


class Resume(BaseModel):
    name: str = ""
    contact: str = ""            # single line: city | email | phone | links
    work_authorization: str = "" # optional one-liner, surfaced near top (H-1B/OPT)
    summary: str = ""            # optional; only rendered if non-empty
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)   # each "Category: a, b, c"
    education: List[Education] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class JDKeywords(BaseModel):
    target_title: str = ""
    required_hard: List[str] = Field(default_factory=list)   # must-have skills/tools
    preferred: List[str] = Field(default_factory=list)       # nice-to-have / bonus
    soft: List[str] = Field(default_factory=list)
    company: str = ""
    values: List[str] = Field(default_factory=list)          # culture / leadership cues
    requires_no_sponsorship: bool = False                    # knockout flag


class SubScore(BaseModel):
    name: str
    weight: float
    value: float                 # 0..100
    detail: str = ""


class Score(BaseModel):
    total: int
    subscores: List[SubScore] = Field(default_factory=list)
    matched: List[str] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    missing_preferred: List[str] = Field(default_factory=list)
    adjacent: List[str] = Field(default_factory=list)   # JD skill covered by a held sibling
    parse_warnings: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class TailorResult(BaseModel):
    resume: Resume
    score_before: Score
    score_after: Score
    change_log: List[str] = Field(default_factory=list)
    flagged: List[str] = Field(default_factory=list)   # skills user must confirm true
