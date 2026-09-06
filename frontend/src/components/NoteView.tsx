import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type {
  ConditionOrigin,
  DocumentationStatus,
  NoteDetail,
  ReviewedCondition,
} from "../types";

const DOC_STATUSES: DocumentationStatus[] = [
  "well_documented",
  "ambiguous",
  "mentioned_without_plan",
];

function seedConditions(detail: NoteDetail): ReviewedCondition[] {
  // If the human already reviewed, start from their version; otherwise from the AI draft.
  if (detail.review.conditions.length > 0) return detail.review.conditions;
  return detail.analysis
    ? detail.analysis.conditions.map((c) => ({ ...c, origin: "ai" as ConditionOrigin }))
    : [];
}

export function NoteView({ noteId, onBack }: { noteId: string; onBack: () => void }) {
  const [detail, setDetail] = useState<NoteDetail | null>(null);
  const [conditions, setConditions] = useState<ReviewedCondition[]>([]);
  const [gaps, setGaps] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .getNote(noteId)
      .then((d) => {
        if (!active) return;
        setDetail(d);
        setConditions(seedConditions(d));
        const src = d.review.conditions.length > 0 ? d.review : d.analysis;
        setGaps(src?.documentation_gaps ?? []);
        setSummary(src?.summary ?? "");
      })
      .catch((err) => active && setError(err instanceof Error ? err.message : "Load failed."));
    return () => {
      active = false;
    };
  }, [noteId]);

  function update(index: number, patch: Partial<ReviewedCondition>) {
    setConditions((prev) =>
      prev.map((c, i) => {
        if (i !== index) return c;
        const next = { ...c, ...patch };
        // Any edit to an AI-produced field marks it as human-edited.
        if (next.origin === "ai" && !("origin" in patch)) next.origin = "ai_edited";
        return next;
      })
    );
    setSaved(false);
  }

  function toggleReject(index: number) {
    setConditions((prev) =>
      prev.map((c, i) =>
        i === index
          ? { ...c, origin: c.origin === "ai_rejected" ? "ai" : "ai_rejected" }
          : c
      )
    );
    setSaved(false);
  }

  function addCondition() {
    setConditions((prev) => [
      ...prev,
      {
        name: "",
        evidence_quote: "",
        documentation_status: "ambiguous",
        icd10_code: "",
        confidence: 1,
        evidence_verified: true,
        origin: "human_added",
      },
    ]);
    setSaved(false);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api.submitReview(noteId, {
        conditions,
        documentation_gaps: gaps,
        summary,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  const failed = useMemo(() => detail?.analysis?.status === "failed", [detail]);

  if (error && !detail) return <div className="card error">{error}</div>;
  if (!detail) return <div className="card muted">Loading…</div>;

  return (
    <div>
      <button className="link" onClick={onBack}>
        ← Back
      </button>

      <div className="card">
        <h2>{detail.pseudonym ?? "Note"}</h2>
        <p className="muted">
          {detail.visit_date ? `Visit ${detail.visit_date} · ` : ""}
          Created {new Date(detail.created_at).toLocaleString()}
        </p>
        <details>
          <summary>Original note text</summary>
          <pre className="note-text">{detail.text}</pre>
        </details>
      </div>

      {failed && (
        <div className="card error">
          The AI analysis failed for this note ({detail.analysis?.error}). You can still
          add conditions manually below.
        </div>
      )}

      <div className="card">
        <h3>Summary</h3>
        <textarea
          rows={3}
          value={summary}
          onChange={(e) => {
            setSummary(e.target.value);
            setSaved(false);
          }}
        />
      </div>

      <div className="card">
        <div className="row space-between">
          <h3>Conditions</h3>
          <button type="button" onClick={addCondition}>
            + Add condition
          </button>
        </div>

        {conditions.length === 0 && <p className="muted">No conditions.</p>}

        {conditions.map((c, i) => (
          <div
            key={i}
            className={`condition ${c.origin === "ai_rejected" ? "rejected" : ""}`}
          >
            <div className="row space-between">
              <span className="tags">
                <span className={`badge origin-${c.origin}`}>{c.origin}</span>
                {!c.evidence_verified && (
                  <span className="badge unverified" title="Quote not found verbatim in the note">
                    evidence unverified
                  </span>
                )}
              </span>
              <button type="button" className="link" onClick={() => toggleReject(i)}>
                {c.origin === "ai_rejected" ? "Undo reject" : "Mark incorrect"}
              </button>
            </div>

            <div className="row">
              <label>
                Condition
                <input value={c.name} onChange={(e) => update(i, { name: e.target.value })} />
              </label>
              <label>
                ICD-10
                <input
                  value={c.icd10_code}
                  onChange={(e) => update(i, { icd10_code: e.target.value })}
                />
              </label>
            </div>

            <label>
              Evidence quote
              <textarea
                rows={2}
                value={c.evidence_quote}
                onChange={(e) => update(i, { evidence_quote: e.target.value })}
              />
            </label>

            <div className="row">
              <label>
                Documentation status
                <select
                  value={c.documentation_status}
                  onChange={(e) =>
                    update(i, {
                      documentation_status: e.target.value as DocumentationStatus,
                    })
                  }
                >
                  {DOC_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Confidence: {c.confidence.toFixed(2)}
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={c.confidence}
                  onChange={(e) => update(i, { confidence: Number(e.target.value) })}
                />
              </label>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Documentation gaps</h3>
        <textarea
          rows={4}
          value={gaps.join("\n")}
          onChange={(e) => {
            setGaps(e.target.value.split("\n").filter((g) => g.trim()));
            setSaved(false);
          }}
        />
        <p className="muted">One gap per line.</p>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="row space-between sticky-save">
        <span className="muted">
          {saved ? "Review saved." : "Unsaved changes."}
        </span>
        <button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save review"}
        </button>
      </div>
    </div>
  );
}
