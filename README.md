# Note Insight

Paste a free-text clinical note, get back a **structured, evidence-linked read** of
what it contains — conditions, documentation quality, suggested ICD-10 codes, and the
gaps a coder would flag — then **correct anything the model got wrong** and save it.
The machine produces a draft; the clinician is the authority.

> Built for the DoctusTech technical assessment. All notes are synthetic.

- **Live URL:** _<add your Render URL here>_
- **Test account:** _<add email / password, or sign up on the login screen>_

---

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | React + TypeScript (Vite), strict mode, no `any` |
| Backend | Python + FastAPI, Pydantic validation |
| AI | Google Gemini (`gemini-flash-latest`), JSON structured output |
| Auth + DB | Firebase Authentication + Firestore |
| Deploy | Single Docker image on Render (FastAPI serves the built React app) |

---

## Data model (the part I thought about first)

Four **separate** entities. Collapsing them would break the moment a note is
re-analysed or a reviewer disagrees with the model.

```
User            id (Firebase uid), email
  │  owns
Note            id, user_id, text (immutable), pseudonym, visit_date, created_at
  │  has many                    review_status, condition_count, latest_analysis_id
Analysis        id, note_id, model_name, prompt_version, status(success|failed),
  │             conditions[], documentation_gaps[], summary, error, created_at
  │  reviewed by
Review          note_id, conditions[] (each tagged origin), documentation_gaps[],
                summary, review_status, updated_at
```

Firestore layout:

```
notes/{noteId}                 ← Note (owner = user_id; every read scoped to it)
  ├─ analyses/{analysisId}     ← Analysis (a note can have MANY; old ones kept)
  └─ review/current            ← Review (the human layer, kept apart)
```

**Why these boundaries:**

- **Note vs Analysis** — the note is the raw input and never changes. An analysis is
  one machine run. Re-analysing after a prompt change creates a *new* Analysis; the
  previous one is preserved (`prompt_version` + `model_name` are stored on each). This
  directly supports "multiple analyses per note" and lets us compare prompt versions.
- **Analysis vs Review** — the AI output is stored verbatim and is **never mutated**.
  Human edits live in a separate `Review` document, with each condition tagged by
  `origin` (`ai`, `ai_edited`, `ai_rejected`, `human_added`). This is what lets us
  answer *"what did the model say, and what did the human change?"* — the most valuable
  dataset the product produces.

**Who writes what:**
- Machine → `Analysis.*`
- Human → `Review.*` (and the `origin` tag on each condition)
- System → ids, timestamps, `user_id`, `status`, `condition_count`

**History query** — "all notes for user X, newest first": filter `notes` by `user_id`
and sort by `created_at` descending. At this assessment's scale I sort in memory; at
production scale you'd add a Firestore composite index `(user_id ASC, created_at DESC)`
— called out here honestly rather than silently relying on the console prompt.

---

## How the AI layer stays trustworthy

1. **Structured output, not parsed prose.** Gemini is called with
   `response_mime_type=application/json`, and the result is validated against the
   `AiAnalysis` Pydantic schema **before** it touches Firestore or the UI. No regex,
   no string-splitting.
2. **Hallucination check.** After validation, every `evidence_quote` is checked against
   the original note (whitespace/case-normalised substring match). Quotes that don't
   appear verbatim are flagged `evidence_verified = false` and shown in the UI with an
   "evidence unverified" badge. This is the concrete answer to *"how do you know the
   model didn't make it up?"*
3. **Deliberate failure handling.** Malformed / invalid JSON triggers **one retry**;
   if it still fails, a `failed` Analysis is persisted (with the error) and the API
   returns `502` with a clear message. The user can still add conditions by hand. The
   note itself is never lost.
4. **Input guards.** Empty/too-short and 5000-word-plus notes are rejected at the API
   boundary with a clear message.

The exact prompt is in [`backend/prompts/analysis_v1.txt`](backend/prompts/analysis_v1.txt),
versioned via `PROMPT_VERSION` and stored on every analysis.

---

## Security

- The backend **verifies the Firebase ID token** on every request and derives the uid
  from it. It never trusts a user id sent in the body. See `backend/app/auth.py`.
- Every Firestore read is scoped to the caller's uid; a note that isn't yours returns
  `404` (we don't even confirm it exists).
- The **Gemini key lives only on the server** (`GEMINI_API_KEY`) and is never sent to
  the browser. The Firebase *web* config in the frontend is public by design (it only
  identifies the project) and carries no privileged access.

---

## Run it locally (from zero)

Prereqs: Python 3.12+, Node 20+, a Firebase project (Auth email/password + Firestore
enabled), and a Gemini API key.

### 1. Firebase setup (~5 min)
1. Create a project at <https://console.firebase.google.com>.
2. **Authentication → Sign-in method →** enable **Email/Password**.
3. **Firestore Database →** create in test/production mode (rules don't matter — all
   access goes through the backend Admin SDK, which bypasses them).
4. **Project settings → Service accounts → Generate new private key** → save as
   `backend/serviceAccount.json`.
5. **Project settings → General → Your apps → Web app** → copy the config object.

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env        # then fill in GEMINI_API_KEY; FIREBASE_CREDENTIALS_PATH=./serviceAccount.json
uvicorn app.main:app --reload --port 8080
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env        # paste your Firebase web config JSON into VITE_FIREBASE_CONFIG
npm run dev                 # http://localhost:5173  (proxies /api to :8080)
```

Open <http://localhost:5173>, sign up, paste a note from `sample_notes/`, analyze.

---

## Deploy (single service on Render)

The `Dockerfile` builds the React app and serves it from FastAPI — one image, one URL.

1. Push to GitHub, create a **Render → Web Service → Docker** from the repo (or use the
   included `render.yaml`).
2. Set env vars in the Render dashboard:
   - `GEMINI_API_KEY` — your key
   - `FIREBASE_CREDENTIALS_JSON` — the entire service-account JSON on one line
   - `VITE_FIREBASE_CONFIG` — your Firebase web config JSON on one line
     (Render exposes env vars as Docker build args, so Vite picks this up at build)
3. Deploy. Add the resulting URL to **Firebase → Authentication → Settings →
   Authorized domains**.

---

## Design decisions

1. **FastAPI serves the frontend (one service).** *Alternative:* separate Vercel +
   Render deployments. *Why:* removes CORS and two-URL coordination, and gives a single
   public URL — fewer things to break under a tight deadline. Trade-off: no independent
   frontend CDN scaling, which doesn't matter at this stage.
2. **Firebase Auth + Firestore (vs Postgres).** *Alternative:* Postgres/SQLite with a
   hand-rolled JWT. *Why:* one provider gives verified auth **and** a database, and the
   Admin SDK does token verification for free — the fastest path to the hard security
   requirement. Trade-off: Firestore makes cross-entity queries and joins weaker, so I
   modelled the entities explicitly with subcollections rather than leaning on joins.
3. **Analysis and Review as separate documents.** *Alternative:* one document that the
   human edits in place. *Why:* the assessment's most valuable dataset is the diff
   between machine and human; that only exists if the AI output is immutable. Trade-off:
   the frontend seeds the editable form from the review if present, else the analysis.
4. **Substring evidence check for hallucinations.** *Alternative:* a second LLM call to
   grade faithfulness. *Why:* deterministic, free, instant, and good enough to catch
   invented quotes. Trade-off: it won't catch a *correct* paraphrase that isn't verbatim
   — acceptable, since the requirement is verbatim quotes.

---

## What I'd build next (one more week)

- Inline highlighting of each verified quote in the original note text.
- A metrics view: how often humans correct the machine, by condition.
- Automated tests around schema validation and the failure paths (highest-value bonus).
- Firestore security rules as defence-in-depth (today the backend is the only gate).
- Streaming the analysis into the UI.

## Knowingly left unfinished / cut (time-boxed build)

- No automated tests yet (would start with `gemini.py` validation + retry paths).
- No caching of identical notes, no rate limiting, no PDF/image upload.
- Styling is intentionally minimal — clarity over polish.
- History sorts in memory rather than via a composite index (fine at this scale).
- Gemini free tier is limited to ~5 requests/min; rapid repeated analyses can hit a
  429. The app surfaces this as a clear error and the note is never lost — caching and
  per-user rate limiting (listed above) would address it.

## Time spent

Roughly **~3 hours**, deliberately time-boxed. I prioritised the data model, the
security boundary, and robust AI handling over visual polish and bonus features.
