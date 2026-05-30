from pathlib import Path
import logging

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from . import models
from .routers import auth, interviews, websocket, analysis, tts

logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth.router, tags=["auth"])
app.include_router(interviews.router, tags=["interviews"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(analysis.router, tags=["analysis"])
app.include_router(tts.router, tags=["tts"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
