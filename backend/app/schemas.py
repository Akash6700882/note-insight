"""Pydantic models — the typed contract for the whole system.

Three groups:
  1. What the client sends us (requests).
  2. What Gemini must return (AiAnalysis*) — validated before it touches the DB or UI.
  3. What we store and return (Note / Analysis / Review response shapes).

The AI output is validated against `AiAnalysis` the moment it arrives. If Gemini
returns anything that does not fit this schema, validation raises and we handle
it deliberately (retry once, then mark the analysis failed) — we never regex
free-form prose.
"""
from datetime import datetime, date
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ---------- enums ----------
class DocumentationStatus(str, Enum):
    well_documented = "well_documented"
    ambiguous = "ambiguous"
    mentioned_without_plan = "mentioned_without_plan"


class ReviewStatus(str, Enum):
    pending = "pending"
    reviewed = "reviewed"


class AnalysisStatus(str, Enum):
    success = "success"
    failed = "failed"


class ConditionOrigin(str, Enum):
    ai = "ai"                 # produced by the model
    ai_edited = "ai_edited"   # model produced it, human changed it
    ai_rejected = "ai_rejected"  # human marked it incorrect
    human_added = "human_added"  # human added a condition the model missed


# ---------- requests ----------
class NoteCreate(BaseModel):
    text: str = Field(min_length=1)
    pseudonym: str | None = Field(default=None, max_length=120)
    visit_date: date | None = None


# ---------- AI output (validated) ----------
class AiCondition(BaseModel):
    name: str
    evidence_quote: str
    documentation_status: DocumentationStatus
    icd10_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    # Set by our own traceability check, not by the model.
    evidence_verified: bool = True

    @field_validator("name", "evidence_quote", "icd10_code")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be blank")
        return v.strip()


class AiAnalysis(BaseModel):
    conditions: list[AiCondition]
    documentation_gaps: list[str]
    summary: str


# ---------- reviewed (human) layer ----------
class ReviewedCondition(AiCondition):
    origin: ConditionOrigin = ConditionOrigin.ai


class ReviewSubmit(BaseModel):
    conditions: list[ReviewedCondition]
    documentation_gaps: list[str]
    summary: str


# ---------- responses ----------
class AnalysisOut(BaseModel):
    id: str
    status: AnalysisStatus
    model_name: str
    prompt_version: str
    created_at: datetime
    # Present when status == success
    conditions: list[AiCondition] = []
    documentation_gaps: list[str] = []
    summary: str = ""
    error: str | None = None


class ReviewOut(BaseModel):
    review_status: ReviewStatus
    conditions: list[ReviewedCondition] = []
    documentation_gaps: list[str] = []
    summary: str = ""
    updated_at: datetime | None = None


class NoteSummary(BaseModel):
    """Row in the history list."""
    id: str
    pseudonym: str | None
    visit_date: date | None
    created_at: datetime
    condition_count: int
    review_status: ReviewStatus


class NoteDetail(BaseModel):
    id: str
    text: str
    pseudonym: str | None
    visit_date: date | None
    created_at: datetime
    analysis: AnalysisOut | None
    review: ReviewOut
