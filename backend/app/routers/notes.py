"""Note endpoints. Every route derives the user from the verified token (get_current_uid)
and scopes all data access to that uid. A note that isn't yours returns 404 — we don't
even confirm it exists.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from .. import db
from ..auth import get_current_uid
from ..config import settings
from ..gemini import PROMPT_VERSION, AiAnalysisError, analyze_note
from ..schemas import (
    AiCondition,
    AnalysisOut,
    NoteCreate,
    NoteDetail,
    NoteSummary,
    ReviewOut,
    ReviewStatus,
    ReviewSubmit,
    ReviewedCondition,
)

router = APIRouter(prefix="/api", tags=["notes"])


def _word_count(text: str) -> int:
    return len(text.split())


@router.post("/notes", status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteCreate, uid: str = Depends(get_current_uid)) -> dict:
    words = _word_count(payload.text)
    if words < settings.min_note_words:
        raise HTTPException(422, f"Note is too short (min {settings.min_note_words} words).")
    if words > settings.max_note_words:
        raise HTTPException(422, f"Note is too long (max {settings.max_note_words} words).")
    note_id = db.create_note(uid, payload)
    return {"id": note_id}


@router.post("/notes/{note_id}/analyze", response_model=AnalysisOut)
def analyze(note_id: str, uid: str = Depends(get_current_uid)) -> AnalysisOut:
    detail = db.get_note_detail(uid, note_id)
    if detail is None:
        raise HTTPException(404, "Note not found.")
    note_text = detail["note"]["text"]

    try:
        analysis = analyze_note(note_text)
    except AiAnalysisError as exc:
        db.add_analysis_failure(uid, note_id, str(exc), settings.gemini_model, PROMPT_VERSION)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI analysis could not be completed. Please try again.",
        )

    analysis_id = db.add_analysis_success(
        uid, note_id, analysis, settings.gemini_model, PROMPT_VERSION
    )
    if analysis_id is None:
        raise HTTPException(404, "Note not found.")

    return AnalysisOut(
        id=analysis_id,
        status="success",
        model_name=settings.gemini_model,
        prompt_version=PROMPT_VERSION,
        created_at=datetime.now(timezone.utc),
        conditions=analysis.conditions,
        documentation_gaps=analysis.documentation_gaps,
        summary=analysis.summary,
    )


@router.get("/notes", response_model=list[NoteSummary])
def list_notes(uid: str = Depends(get_current_uid)) -> list[NoteSummary]:
    rows = db.list_notes(uid)
    return [
        NoteSummary(
            id=r["id"],
            pseudonym=r.get("pseudonym"),
            visit_date=date.fromisoformat(r["visit_date"]) if r.get("visit_date") else None,
            created_at=r["created_at"],
            condition_count=r.get("condition_count", 0),
            review_status=r.get("review_status", ReviewStatus.pending.value),
        )
        for r in rows
    ]


@router.get("/notes/{note_id}", response_model=NoteDetail)
def get_note(note_id: str, uid: str = Depends(get_current_uid)) -> NoteDetail:
    detail = db.get_note_detail(uid, note_id)
    if detail is None:
        raise HTTPException(404, "Note not found.")

    note = detail["note"]
    a = detail["analysis"]
    r = detail["review"]

    analysis_out = None
    if a is not None:
        analysis_out = AnalysisOut(
            id=a["id"],
            status=a["status"],
            model_name=a["model_name"],
            prompt_version=a["prompt_version"],
            created_at=a["created_at"],
            conditions=[AiCondition(**c) for c in a.get("conditions", [])],
            documentation_gaps=a.get("documentation_gaps", []),
            summary=a.get("summary", ""),
            error=a.get("error"),
        )

    if r is not None:
        review_out = ReviewOut(
            review_status=r["review_status"],
            conditions=[ReviewedCondition(**c) for c in r.get("conditions", [])],
            documentation_gaps=r.get("documentation_gaps", []),
            summary=r.get("summary", ""),
            updated_at=r.get("updated_at"),
        )
    else:
        review_out = ReviewOut(review_status=ReviewStatus.pending)

    return NoteDetail(
        id=note["id"],
        text=note["text"],
        pseudonym=note.get("pseudonym"),
        visit_date=date.fromisoformat(note["visit_date"]) if note.get("visit_date") else None,
        created_at=note["created_at"],
        analysis=analysis_out,
        review=review_out,
    )


@router.put("/notes/{note_id}/review", response_model=ReviewOut)
def submit_review(
    note_id: str, payload: ReviewSubmit, uid: str = Depends(get_current_uid)
) -> ReviewOut:
    ok = db.save_review(uid, note_id, payload)
    if not ok:
        raise HTTPException(404, "Note not found.")
    return ReviewOut(
        review_status=ReviewStatus.reviewed,
        conditions=payload.conditions,
        documentation_gaps=payload.documentation_gaps,
        summary=payload.summary,
        updated_at=datetime.now(timezone.utc),
    )
