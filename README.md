# AI Interview System

A full-stack mock interview platform that conducts real-time voice interviews, analyzes candidate performance (content, speech, and video), and produces structured feedback reports. All core AI inference runs locally (Ollama, faster-whisper); the database and optional email delivery may use external services depending on deployment.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Requirements](#requirements)
3. [Environment Variables](#environment-variables)
4. [Required Models](#required-models)
5. [Installation and Setup](#installation-and-setup)
6. [Running with Docker](#running-with-docker)
7. [Running the Services](#running-the-services)
8. [Minimum Hardware Requirements](#minimum-hardware-requirements)
9. [Project Structure](#project-structure)

---

## Architecture Overview

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + Vite (`http://localhost:5173`) |
| Backend API | FastAPI, Python 3.11+ (`http://localhost:8000`) |
| Real-time interview | WebSocket (`/ws/interview/{id}`) |
| Local LLM | Ollama (`llama3.2:3b` by default) |
| Speech-to-text | faster-whisper (local, CPU/GPU) |
| Video analysis | MediaPipe + OpenCV |
| Semantic scoring | SentenceTransformer (`all-MiniLM-L6-v2`) |
| Database | PostgreSQL (e.g. Supabase) via SQLAlchemy + psycopg3 |
| Email | SMTP (verification and password reset) |
| TTS (backend, macOS) | `say` + `afconvert` |

---

## Requirements

### System

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com)
- **FFmpeg** and **ffprobe** on `PATH` (required by faster-whisper for video/audio extraction)
- **macOS only (optional TTS):** `say` and `afconvert` for backend `/tts` endpoint; other platforms fall back to browser speech synthesis

### Python dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Node dependencies

```bash
cd frontend
npm install
```

---

## Environment Variables

Copy the example file and edit values:

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | Yes | Random secret (≥ 32 characters) for signing JWT access tokens |
| `DATABASE_URL` | Yes | PostgreSQL URL, e.g. `postgresql+psycopg://user:pass@host:5432/dbname` |
| `FRONTEND_BASE_URL` | Yes | Frontend base URL for email links (e.g. `http://localhost:5173`) |
| `OLLAMA_BASE_URL` | Yes | Ollama API URL (default `http://localhost:11434`) |
| `OLLAMA_MODEL` | Yes | Model for live questions and company research (default `llama3.2:3b`) |
| `OLLAMA_ANALYSIS_MODEL` | No | Separate model for post-interview feedback; falls back to `OLLAMA_MODEL` if unset |
| `OLLAMA_TEMPERATURE` | No | Sampling temperature (default `0.55`) |
| `WHISPER_MODEL_SIZE` | No | faster-whisper model size (default `base`) |
| `WHISPER_DEVICE` | No | e.g. `cpu` or `cuda` |
| `SMTP_HOST` | Yes* | SMTP server hostname |
| `SMTP_PORT` | Yes* | SMTP port (default `587`) |
| `SMTP_USER` | Yes* | SMTP username |
| `SMTP_PASS` | Yes* | SMTP password |
| `EMAIL_FROM` | Yes* | Sender address |
| `DEV_AUTO_VERIFY` | No | If `true`/`1`, new users are marked verified immediately (local testing only) |

\*Required for registration and password-reset email flows. Registration fails if verification email cannot be sent.

---

## Required Models

### Ollama

```bash
ollama pull llama3.2:3b
```

Optional (if using separate analysis model):

```bash
ollama pull qwen2.5:7b
```

Used for:

- Company context research during interview preparation
- Dynamic question generation during the live WebSocket session
- Post-interview qualitative feedback

### faster-whisper

Downloaded on first use (default: `base`, ~150 MB).

### SentenceTransformer

Downloaded on first use: `all-MiniLM-L6-v2` (~90 MB).

### MediaPipe (video analysis)

Face/pose landmark model files under `backend/app/analysis/models/` are downloaded automatically on first video analysis if missing.

---

## Installation and Setup

1. Clone the repository and enter the project directory.
2. Create and configure `backend/.env` from `backend/.env.example`.
3. Create a PostgreSQL database (e.g. Supabase) and set `DATABASE_URL`.
4. Install backend and frontend dependencies (see [Requirements](#requirements)).
5. Pull Ollama models (see [Required Models](#required-models)).
6. Start Ollama, backend, and frontend (see [Running the Services](#running-the-services)).

Database tables are created automatically when the backend starts (`models.Base.metadata.create_all`).

---

## Running with Docker

The easiest way to run the project. Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

### Steps

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it.
2. Install [Ollama](https://ollama.com) and pull the required model:
   ```bash
   ollama pull llama3.1:8b
   ```
3. Set up a PostgreSQL database (e.g. [Supabase](https://supabase.com) free tier) and copy the connection string.
4. Configure your environment file:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Fill in `DATABASE_URL`, `JWT_SECRET_KEY`, SMTP settings, and set:
   ```
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   ```
5. Build and start:
   ```bash
   docker compose up --build
   ```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

> **Note:** On first run, faster-whisper (~150 MB), SentenceTransformer (~90 MB), and MediaPipe models are downloaded automatically. This may take a few minutes before the first interview is ready.

### Stop

```bash
docker compose down
```

---

## Running the Services

All of the following must be running:

### 1. Ollama

```bash
ollama serve
```

### 2. Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000` — docs: `http://localhost:8000/docs`

### 3. Frontend

```bash
cd frontend
npm run dev
```

App: `http://localhost:5173`

### Typical flow

Register → verify email (unless `DEV_AUTO_VERIFY`) → complete profile and upload CV → create interview → wait until status `ready` → run live interview → upload completes analysis → view results on dashboard.

---

## Minimum Hardware Requirements

| Component | Minimum | Recommended (this project) |
|-----------|---------|---------------------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB (live sessions with Ollama + analysis often use ~10 GB) |
| Disk | 8 GB free | 15 GB free (models, uploads, caches) |
| GPU | — | Optional; speeds up Ollama and Whisper |

The system runs on CPU only. GPU reduces question-generation and transcription latency.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── routers/
│   │   │   ├── auth.py           # /login, /create-user, profile, CV
│   │   │   ├── interviews.py     # CRUD, video upload, preparation
│   │   │   ├── websocket.py      # Live interview session
│   │   │   ├── analysis.py       # Post-interview analysis
│   │   │   ├── ollama_service.py
│   │   │   └── tts.py
│   │   └── analysis/             # STT, scoring, video, feedback
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/pages/                # Login, Dashboard, InterviewRun, etc.
└── README.md
```

---

## API endpoints (reference)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/create-user` | Register |
| POST | `/login` | Login, returns JWT |
| GET | `/me` | Validate token |
| POST | `/interviews` | Create interview (requires CV on profile) |
| GET | `/interviews` | List interviews |
| POST | `/interviews/{id}/video` | Upload session video, trigger analysis |
| WS | `/ws/interview/{id}` | Live interview (`init` message includes token) |

---

## Testing

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

57 automated tests covering authentication, interview flow, security, and analysis endpoints.
