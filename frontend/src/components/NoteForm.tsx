import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";

// Creates a note then triggers analysis. Reports loading / error clearly so the
// UI never looks frozen or lies about what happened.
export function NoteForm({ onAnalyzed }: { onAnalyzed: (noteId: string) => void }) {
  const [text, setText] = useState("");
  const [pseudonym, setPseudonym] = useState("");
  const [visitDate, setVisitDate] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "analyzing">("idle");
  const [error, setError] = useState<string | null>(null);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      setStatus("saving");
      const { id } = await api.createNote({
        text,
        pseudonym: pseudonym || null,
        visit_date: visitDate || null,
      });
      setStatus("analyzing");
      await api.analyze(id);
      setText("");
      setPseudonym("");
      setVisitDate("");
      setStatus("idle");
      onAnalyzed(id);
    } catch (err) {
      setStatus("idle");
      setError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again."
      );
    }
  }

  const busy = status !== "idle";

  return (
    <form className="card" onSubmit={submit}>
      <h2>New note</h2>
      <div className="row">
        <label>
          Patient pseudonym (optional)
          <input
            value={pseudonym}
            placeholder="e.g. Patient-A"
            onChange={(e) => setPseudonym(e.target.value)}
          />
        </label>
        <label>
          Visit date (optional)
          <input
            type="date"
            value={visitDate}
            onChange={(e) => setVisitDate(e.target.value)}
          />
        </label>
      </div>

      <label>
        Clinical note
        <textarea
          value={text}
          rows={12}
          required
          placeholder="Paste the free-text clinical note here… (do not include real patient identifiers)"
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      <p className="muted">{wordCount} words</p>

      {error && <p className="error">{error}</p>}

      <button type="submit" disabled={busy || wordCount === 0}>
        {status === "saving"
          ? "Saving note…"
          : status === "analyzing"
          ? "Analyzing with AI… (this can take a few seconds)"
          : "Analyze note"}
      </button>
    </form>
  );
}
