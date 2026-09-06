"""Gemini integration: structured output, schema validation, hallucination check.

Uses the modern `google-genai` SDK (httpx-based). The older `google-generativeai`
SDK was unreliable on the deployed container: its default gRPC transport hung
indefinitely, and its REST transport raised a latin-1 encoding error. `google-genai`
avoids both.

The flow is deliberately defensive:
  1. Ask Gemini for JSON matching our schema (response_mime_type=application/json).
  2. Parse + validate against `AiAnalysis` (Pydantic). Malformed output raises.
  3. Retry ONCE on failure. If it still fails, raise AiAnalysisError so the caller
     can persist a `failed` analysis instead of crashing.
  4. Traceability: verify every evidence_quote actually appears in the source note.
     Quotes that don't are flagged `evidence_verified=False` — this is our answer to
     "how do you know the model didn't make it up?"
"""
import json
import re
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import ValidationError

from .config import settings
from .schemas import AiAnalysis

PROMPT_VERSION = "analysis_v1"
_PROMPT_TEMPLATE = (Path(__file__).parent.parent / "prompts" / "analysis_v1.txt").read_text(
    encoding="utf-8"
)

# Sanitize the key: strip whitespace and any stray non-ASCII characters. API keys
# are always ASCII, and a copy-paste artifact (e.g. a box-drawing char) in the env
# var otherwise crashes header encoding with "'ascii' codec can't encode ...".
_API_KEY = "".join(c for c in settings.gemini_api_key if c.isascii() and not c.isspace())

# Hard per-request timeout (ms) so a slow/stuck call fails fast instead of hanging.
_client = genai.Client(
    api_key=_API_KEY,
    http_options=types.HttpOptions(timeout=30_000),
)


class AiAnalysisError(Exception):
    """Raised when Gemini output cannot be validated after a retry."""


def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase so quote matching tolerates reformatting."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _verify_evidence(analysis: AiAnalysis, note_text: str) -> AiAnalysis:
    haystack = _normalize(note_text)
    for condition in analysis.conditions:
        condition.evidence_verified = _normalize(condition.evidence_quote) in haystack
    return analysis


def _call_gemini(note_text: str) -> str:
    prompt = _PROMPT_TEMPLATE.replace("{note_text}", note_text)
    response = _client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return response.text


def analyze_note(note_text: str) -> AiAnalysis:
    """Return a validated, evidence-checked analysis, or raise AiAnalysisError."""
    last_error: Exception | None = None
    for _ in range(2):  # initial attempt + one retry
        try:
            raw = _call_gemini(note_text)
            analysis = AiAnalysis.model_validate(json.loads(raw))
            return _verify_evidence(analysis, note_text)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
        except Exception as exc:  # network / API errors
            last_error = exc
    raise AiAnalysisError(str(last_error))
