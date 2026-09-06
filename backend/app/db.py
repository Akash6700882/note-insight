"""Firestore data access — the four entities kept deliberately separate.

Layout:
  notes/{note_id}                         <- raw input, immutable text + metadata
    ├─ field user_id  (owner; every read is scoped to it)
    ├─ analyses/{analysis_id}             <- one machine run; a note may have many
    └─ review/current                     <- the human layer, kept apart from analyses

Why subcollections: an Analysis belongs to exactly one Note, a Note may have many
Analyses (re-run after a prompt change — old ones are never deleted), and the human
Review is a separate document so we can always answer "what did the model say vs.
what did the human change?".

History query: we filter notes by user_id and sort newest-first. For this
assessment's scale we sort in memory; at production scale you'd add a composite
index (user_id ASC, created_at DESC) — noted in the README.
"""
from datetime import datetime, timezone

from .firebase import db
from .schemas import (
    AiAnalysis,
    AnalysisStatus,
    NoteCreate,
    ReviewStatus,
    ReviewSubmit,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_note(uid: str, note: NoteCreate) -> str:
    ref = db.collection("notes").document()
    ref.set(
        {
            "user_id": uid,
            "text": note.text,
            "pseudonym": note.pseudonym,
            "visit_date": note.visit_date.isoformat() if note.visit_date else None,
            "created_at": _now(),
            "review_status": ReviewStatus.pending.value,
            "condition_count": 0,
            "latest_analysis_id": None,
        }
    )
    return ref.id


def _owned_note_ref(uid: str, note_id: str):
    """Return the note ref only if it belongs to uid, else None (no data leaks)."""
    ref = db.collection("notes").document(note_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get("user_id") != uid:
        return None
    return ref


def add_analysis_success(uid: str, note_id: str, analysis: AiAnalysis,
                         model_name: str, prompt_version: str) -> str | None:
    ref = _owned_note_ref(uid, note_id)
    if ref is None:
        return None
    a_ref = ref.collection("analyses").document()
    a_ref.set(
        {
            "status": AnalysisStatus.success.value,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "created_at": _now(),
            "conditions": [c.model_dump() for c in analysis.conditions],
            "documentation_gaps": analysis.documentation_gaps,
            "summary": analysis.summary,
            "error": None,
        }
    )
    ref.update(
        {
            "latest_analysis_id": a_ref.id,
            "condition_count": len(analysis.conditions),
        }
    )
    return a_ref.id


def add_analysis_failure(uid: str, note_id: str, error: str,
                         model_name: str, prompt_version: str) -> str | None:
    ref = _owned_note_ref(uid, note_id)
    if ref is None:
        return None
    a_ref = ref.collection("analyses").document()
    a_ref.set(
        {
            "status": AnalysisStatus.failed.value,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "created_at": _now(),
            "conditions": [],
            "documentation_gaps": [],
            "summary": "",
            "error": error,
        }
    )
    ref.update({"latest_analysis_id": a_ref.id})
    return a_ref.id


def save_review(uid: str, note_id: str, review: ReviewSubmit) -> bool:
    ref = _owned_note_ref(uid, note_id)
    if ref is None:
        return False
    ref.collection("review").document("current").set(
        {
            "conditions": [c.model_dump() for c in review.conditions],
            "documentation_gaps": review.documentation_gaps,
            "summary": review.summary,
            "review_status": ReviewStatus.reviewed.value,
            "updated_at": _now(),
        }
    )
    ref.update({"review_status": ReviewStatus.reviewed.value})
    return True


def list_notes(uid: str) -> list[dict]:
    docs = db.collection("notes").where("user_id", "==", uid).stream()
    rows = [{**d.to_dict(), "id": d.id} for d in docs]
    rows.sort(key=lambda r: r["created_at"], reverse=True)  # newest first
    return rows


def get_note_detail(uid: str, note_id: str) -> dict | None:
    ref = _owned_note_ref(uid, note_id)
    if ref is None:
        return None
    note = {**ref.get().to_dict(), "id": note_id}

    analysis = None
    latest_id = note.get("latest_analysis_id")
    if latest_id:
        a_snap = ref.collection("analyses").document(latest_id).get()
        if a_snap.exists:
            analysis = {**a_snap.to_dict(), "id": latest_id}

    review_snap = ref.collection("review").document("current").get()
    review = review_snap.to_dict() if review_snap.exists else None

    return {"note": note, "analysis": analysis, "review": review}
