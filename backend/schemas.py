"""Pydantic schemas: the contract between the LLM, the API and the database."""
import re
from datetime import date
from typing import Annotated, Literal, Optional

from pydantic import (BaseModel, EmailStr, Field, StringConstraints,
                      field_validator, model_validator)

DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Medium = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


def _blank_to_none(v):
    """LLMs sometimes return "" or "null" instead of null."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in {"", "null", "none", "n/a"}:
        return None
    return v


class Skill(BaseModel):
    name: Short
    category: Literal["language", "framework", "tool", "soft", "other"] = "other"
    proficiency: Optional[Literal["beginner", "intermediate", "advanced"]] = None

    _clean = field_validator("proficiency", mode="before")(_blank_to_none)


class Experience(BaseModel):
    role: Short
    organization: Optional[Short] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    highlights: list[Medium] = Field(default_factory=list, max_length=15)

    _clean = field_validator("organization", "start_date", "end_date", mode="before")(_blank_to_none)

    @field_validator("start_date", "end_date")
    @classmethod
    def check_date(cls, v):
        if v is not None and not DATE_RE.match(v):
            raise ValueError("date must be YYYY-MM or null")
        return v

    @model_validator(mode="after")
    def check_order(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date is after end_date")
        return self


class Education(BaseModel):
    degree: Short
    institution: Optional[Short] = None
    year: Optional[int] = Field(default=None, ge=1950, le=2100)

    _clean = field_validator("institution", "year", mode="before")(_blank_to_none)


class Project(BaseModel):
    title: Short
    tech: list[Short] = Field(default_factory=list, max_length=30)
    description: Long = ""


class ResumeProfile(BaseModel):
    full_name: Optional[Short] = None
    email: Optional[EmailStr] = None
    summary: Optional[Long] = None
    skills: list[Skill] = Field(default_factory=list, max_length=100)
    experience: list[Experience] = Field(default_factory=list, max_length=30)
    education: list[Education] = Field(default_factory=list, max_length=15)
    projects: list[Project] = Field(default_factory=list, max_length=30)
    missing_fields: list[str] = Field(default_factory=list)

    _clean = field_validator("full_name", "email", "summary", mode="before")(_blank_to_none)

    def with_computed_missing(self) -> "ResumeProfile":
        """Don't trust the LLM to report gaps: compute them from the data too."""
        checks = {
            "full_name": self.full_name,
            "email": self.email,
            "summary": self.summary,
            "skills": self.skills,
            "experience": self.experience,
            "education": self.education,
            "projects": self.projects,
        }
        missing = [k for k, v in checks.items() if not v]
        if any(e.start_date is None for e in self.experience):
            missing.append("experience_dates")
        extra = [m for m in self.missing_fields if m not in missing and isinstance(m, str)]
        return self.model_copy(update={"missing_fields": missing + extra[:10]})

    def is_empty(self) -> bool:
        return not (self.full_name or self.email or self.summary or self.skills
                    or self.experience or self.education or self.projects)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
WorkMode = Literal["remote", "hybrid", "onsite"]
Level = Literal["intern", "entry", "mid", "senior"]
JobStatus = Literal["saved", "applied", "shortlisted", "interview", "offer", "rejected"]
JD_TEXT = Annotated[str, StringConstraints(max_length=15000)]


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        k = it.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(it.strip())
    return out


class JobPosting(BaseModel):
    title: Short
    company: Optional[Short] = None
    location: Optional[Short] = None
    work_mode: Optional[WorkMode] = None
    experience_level: Optional[Level] = None
    required_skills: list[Short] = Field(default_factory=list, max_length=40)
    preferred_skills: list[Short] = Field(default_factory=list, max_length=40)
    deadline: Optional[str] = None
    notes: Optional[Long] = None

    _clean = field_validator("company", "location", "work_mode", "experience_level", "deadline", "notes",
                             mode="before")(_blank_to_none)

    @field_validator("work_mode", "experience_level", mode="before")
    @classmethod
    def _lower(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("deadline")
    @classmethod
    def _deadline(cls, v):
        if v is None:
            return v
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("deadline must be a real date like 2026-12-31")
        return v

    @model_validator(mode="after")
    def _skills(self):
        self.required_skills = _dedupe(self.required_skills)
        self.preferred_skills = _dedupe(self.preferred_skills)
        if not self.required_skills and not self.preferred_skills:
            raise ValueError("add at least one required or preferred skill")
        return self


class JobIn(JobPosting):
    jd_text: Optional[JD_TEXT] = None
    source: Literal["jd", "role_title"] = "jd"
    status: JobStatus = "saved"


# ---------------------------------------------------------------------------
# AI outputs for the career workspace
# ---------------------------------------------------------------------------
class Recommendation(BaseModel):
    action: Medium
    why: Medium
    impact: Literal["high", "medium", "low"] = "medium"


class Recommendations(BaseModel):
    recommendations: list[Recommendation] = Field(min_length=1, max_length=6)


class PlanTask(BaseModel):
    skill: Short
    title: Short
    description: Long = ""
    cadence: Literal["daily", "weekly"] = "weekly"
    day: Optional[int] = Field(default=None, ge=1, le=7)
    minutes: int = Field(default=30, ge=10, le=240)

    _clean = field_validator("day", mode="before")(_blank_to_none)


class PlanWeek(BaseModel):
    week: int = Field(ge=1, le=8)
    goal: Medium
    tasks: list[PlanTask] = Field(min_length=1, max_length=14)


class PlanDraft(BaseModel):
    title: Short
    weeks: list[PlanWeek] = Field(min_length=1, max_length=8)


class GeneratedQuestion(BaseModel):
    question: Medium
    focus: Optional[Short] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    _clean = field_validator("focus", mode="before")(_blank_to_none)


class QuestionSet(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=3, max_length=8)


Score10 = Annotated[int, Field(ge=0, le=10)]


class AnswerFeedback(BaseModel):
    relevance: Score10
    clarity: Score10
    completeness: Score10
    strengths: list[Medium] = Field(default_factory=list, max_length=5)
    improvements: list[Medium] = Field(default_factory=list, max_length=6)
    missing_concepts: list[Short] = Field(default_factory=list, max_length=8)
    sample_structure: list[Medium] = Field(default_factory=list, max_length=8)

    def overall(self) -> int:
        return round((self.relevance + self.clarity + self.completeness) / 3 * 10)


class BulletFix(BaseModel):
    id: Short
    improved: Medium
    reason: Medium


class UnclearItem(BaseModel):
    id: Short
    issue: Medium
    suggestion: Medium


class OptimizationDraft(BaseModel):
    tailored_summary: Optional[Long] = None
    bullet_fixes: list[BulletFix] = Field(default_factory=list, max_length=20)
    unclear_items: list[UnclearItem] = Field(default_factory=list, max_length=12)

    _clean = field_validator("tailored_summary", mode="before")(_blank_to_none)


class Milestone(BaseModel):
    title: Short
    description: Long = ""


class Dataset(BaseModel):
    name: Short
    description: Long = ""


class ProjectIdea(BaseModel):
    level: Literal["beginner", "intermediate", "advanced"]
    title: Short
    problem_statement: Long
    features: list[Medium] = Field(min_length=2, max_length=10)
    tech_stack: list[Short] = Field(min_length=1, max_length=15)
    milestones: list[Milestone] = Field(min_length=2, max_length=8)
    datasets: list[Dataset] = Field(default_factory=list, max_length=5)
    evaluation_metrics: list[Medium] = Field(default_factory=list, max_length=8)
    readme_outline: list[Short] = Field(default_factory=list, max_length=12)
    github_description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=350)] = ""
    skills_demonstrated: list[Short] = Field(default_factory=list, max_length=15)


class ProjectIdeas(BaseModel):
    ideas: list[ProjectIdea] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _levels(self):
        if {i.level for i in self.ideas} != {"beginner", "intermediate", "advanced"}:
            raise ValueError("need exactly one beginner, one intermediate and one advanced idea")
        return self
