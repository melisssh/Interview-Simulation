# AI Interview System

A full-stack mock interview platform that conducts real-time voice interviews, analyzes candidate performance (content, speech, video), and produces detailed feedback reports.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Requirements](#requirements)
3. [Environment Variables](#environment-variables)
4. [Required Models](#required-models)
5. [Installation & Setup](#installation--setup)
6. [Running the Services](#running-the-services)
7. [Minimum Hardware Requirements](#minimum-hardware-requirements)
8. [Project Structure](#project-structure)

---

## Architecture Overview

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite, served on `localhost:5173` |
| Backend API | FastAPI (Python 3.11+), served on `localhost:8000` |
| Real-time interview | WebSocket (`/ws/interview/{id}`) |
| Local LLM | Ollama — `llama3.2:3b` |
| Speech-to-Text | faster-whisper (local, CPU/GPU) |
| Video Analysis | MediaPipe + OpenCV |
| Semantic Scoring | SentenceTransformer (`all-MiniLM-L6-v2`) |
| Database | Supabase (PostgreSQL) via psycopg3 |
| Email | Resend API (optional) |

---

## Requirements

### System

- Python 3.11 or higher
- Node.js 18 or higher
- [Ollama](https://ollama.com) installed and running

### Python dependencies

```bash
pip install -r backend/requirements.txt
```

### Node dependencies

```bash
cd frontend && npm install
```

---

## Environment Variables

Copy the example file and fill in your values:

```bash
cp backend/.env.example backend/.env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | Yes | Random string, minimum 32 characters. Used to sign JWTs. |
| `DATABASE_URL` | Yes | Supabase Postgres connection string with psycopg3 driver. Format: `postgresql+psycopg://user:pass@host:5432/db` |
| `FRONTEND_BASE_URL` | Yes | Base URL of the frontend, used in email links (e.g. `http://localhost:5173`) |
| `OLLAMA_BASE_URL` | Yes | Ollama API base URL (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Yes | Ollama model name to use (default: `llama3.2:3b`) |
| `RESEND_API_KEY` | No | Resend API key for sending verification emails. Without this, email verification is skipped in dev mode. |
| `EMAIL_FROM` | No | Sender address for emails (must be a verified domain on Resend free tier) |
| `DEV_AUTO_VERIFY` | No | Set to `true` to automatically verify new user accounts without sending email. Useful for local development. |

---

## Required Models

### Ollama (Local LLM)

Install Ollama from [ollama.com](https://ollama.com), then pull the required model:

```bash
ollama pull llama3.2:3b
```

The model is used for:
- Generating interview questions from CV and job description
- Asking adaptive follow-up questions during the interview
- Producing qualitative feedback and recommendations after the interview

Minimum RAM for `llama3.2:3b`: **4 GB** (runs on CPU if no GPU is available, but inference is significantly slower).

### faster-whisper (Speech-to-Text)

Downloaded automatically on first use. No manual setup required. Uses the `base` Whisper model by default (~150 MB).

### SentenceTransformer (Semantic Scoring)

Downloaded automatically on first use. Model: `all-MiniLM-L6-v2` (~90 MB).

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd <repo-directory>
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your values
```

### 3. Set up the database

Create a project in [Supabase](https://supabase.com) and copy the connection string (Session mode, port 5432) into `DATABASE_URL`.

Tables are created automatically when the backend first starts.

### 4. Install backend dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
```

### 6. Pull the Ollama model

```bash
ollama pull llama3.2:3b
```

---

## Running the Services

All three services must be running simultaneously.

### Ollama

```bash
ollama serve
# Runs on http://localhost:11434
```

### Backend (FastAPI)

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### Frontend (React + Vite)

```bash
cd frontend
npm run dev
# Available at http://localhost:5173
```

Open `http://localhost:5173` in your browser → Register → Complete profile → Create interview → Run

---

## Minimum Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16 GB |
| Disk | 8 GB free | 15 GB free |
| GPU (optional) | — | 4 GB VRAM (CUDA or Apple Metal) |

> **Note:** The system runs fully on CPU. GPU acceleration speeds up both Ollama inference and faster-whisper transcription significantly, but is not required.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration
│   │   ├── database.py              # SQLAlchemy engine (Supabase Postgres)
│   │   ├── models.py                # ORM models
│   │   ├── routers/
│   │   │   ├── auth.py              # Register, login, JWT, CV upload
│   │   │   ├── interviews.py        # Create/manage interviews, video upload
│   │   │   ├── websocket.py         # Real-time interview WebSocket
│   │   │   ├── analysis.py          # Trigger and retrieve interview analysis
│   │   │   ├── ollama_service.py    # LLM wrapper (question gen, follow-ups)
│   │   │   └── content_analyzer.py  # Keyword/STAR analysis helpers
│   │   └── analysis/
│   │       ├── ollama_feedback.py   # LLM-based qualitative feedback
│   │       ├── scoring.py           # Composite score calculation
│   │       ├── speech_metrics.py    # Filler words, speaking rate, pauses
│   │       ├── video_features.py    # Eye contact, posture (MediaPipe)
│   │       ├── stt.py               # faster-whisper transcription
│   │       └── llm_answer_scores.py # SentenceTransformer semantic scoring
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── pages/                   # React pages (Login, Dashboard, InterviewRun, etc.)
    │   ├── components/              # Shared UI components
    │   └── context/                 # Auth context
    └── package.json
```
