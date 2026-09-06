import { useEffect, useState } from "react";
import { api } from "../api";
import type { NoteSummary } from "../types";

// The user's own notes, newest first. Backend scopes this to the current user.
export function History({
  refreshKey,
  onOpen,
}: {
  refreshKey: number;
  onOpen: (noteId: string) => void;
}) {
  const [notes, setNotes] = useState<NoteSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setError(null);
    api
      .listNotes()
      .then((rows) => active && setNotes(rows))
      .catch((err) =>
        active && setError(err instanceof Error ? err.message : "Failed to load history.")
      );
    return () => {
      active = false;
    };
  }, [refreshKey]);

  if (error) return <div className="card error">{error}</div>;
  if (notes === null) return <div className="card muted">Loading history…</div>;
  if (notes.length === 0)
    return <div className="card muted">No notes yet. Analyze your first note above.</div>;

  return (
    <div className="card">
      <h2>History</h2>
      <ul className="history">
        {notes.map((n) => (
          <li key={n.id}>
            <button className="history-row" onClick={() => onOpen(n.id)}>
              <span className="history-main">
                {n.pseudonym ?? "Untitled note"}
                <span className={`badge ${n.review_status}`}>{n.review_status}</span>
              </span>
              <span className="muted">
                {new Date(n.created_at).toLocaleString()} · {n.condition_count} condition
                {n.condition_count === 1 ? "" : "s"}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
