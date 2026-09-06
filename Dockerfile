# Multi-stage build: build the React app, then serve it from FastAPI.
# One image, one deployed service, one public URL.

# ---- stage 1: build frontend ----
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
# Firebase web config is public by design; injected at build time.
ARG VITE_FIREBASE_CONFIG
ARG VITE_API_BASE=""
ENV VITE_FIREBASE_CONFIG=$VITE_FIREBASE_CONFIG
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# ---- stage 2: backend + built frontend ----
FROM python:3.12-slim
# Force UTF-8 everywhere. The slim image defaults to an ASCII/POSIX locale, which
# makes Python raise "'ascii' codec can't encode" when request text contains any
# non-ASCII character. UTF-8 mode avoids that.
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
