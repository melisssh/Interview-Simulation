from contextlib import asynccontextmanager
from pathlib import Path
import logging

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, SessionLocal
from . import models
from .routers import auth, interviews, websocket

logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if db.query(models.Category).count() == 0:
            db.add(models.Category(name="general", description="Genel mülakat soruları"))
            db.add(models.Category(name="technical", description="Teknik sorular"))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(lifespan=lifespan)

origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, tags=["auth"])
app.include_router(interviews.router, tags=["interviews"])
app.include_router(websocket.router, tags=["websocket"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
