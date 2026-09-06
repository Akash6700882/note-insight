// Typed API client. Every request attaches the current user's Firebase ID token;
// the backend verifies it and scopes data to that user.
import { auth } from "./firebase";
import type {
  AnalysisOut,
  NoteCreate,
  NoteDetail,
  NoteSummary,
  ReviewOut,
  ReviewSubmit,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const user = auth.currentUser;
  if (!user) throw new ApiError(401, "Not signed in.");
  const token = await user.getIdToken();

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  createNote: (payload: NoteCreate) =>
    request<{ id: string }>("/api/notes", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  analyze: (noteId: string) =>
    request<AnalysisOut>(`/api/notes/${noteId}/analyze`, { method: "POST" }),

  listNotes: () => request<NoteSummary[]>("/api/notes"),

  getNote: (noteId: string) => request<NoteDetail>(`/api/notes/${noteId}`),

  submitReview: (noteId: string, payload: ReviewSubmit) =>
    request<ReviewOut>(`/api/notes/${noteId}/review`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};
