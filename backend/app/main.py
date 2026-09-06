"""FastAPI entrypoint.

In production this same service also serves the built React app (single deploy,
single public URL, no CORS). In local dev the frontend runs on Vite (5173) and we
allow it via CORS.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import notes

app = FastAPI(title="Note Insight API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---- Serve the built frontend (frontend/dist) if present ----
_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        # Serve real files if they exist, otherwise index.html (SPA routing).
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
