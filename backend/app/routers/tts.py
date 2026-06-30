import os
import re
import sys
import base64
import subprocess
import tempfile
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from . import auth

router = APIRouter()

SAY_VOICE = "Samantha"


def _ssml_to_text(ssml: str) -> str:
    text = re.sub(r"<[^>]+>", " ", ssml)
    return re.sub(r"\s+", " ", text).strip()


@router.post("/tts")
async def tts(request: Request, _current_user=Depends(auth.get_current_user)):
    body = await request.json()

    if sys.platform != "darwin":
        # Not macOS — return empty audio so frontend falls back to browser TTS.
        return JSONResponse(content={"audioContent": "", "timepoints": []})

    inp = body.get("input", {})
    text = _ssml_to_text(inp.get("ssml", "")) or inp.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Text too long")

    aiff_fd, aiff_path = tempfile.mkstemp(suffix=".aiff")
    wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(aiff_fd)
    os.close(wav_fd)
    try:
        subprocess.run(["say", "-v", SAY_VOICE, "-o", aiff_path, text], check=True, timeout=30)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path], check=True, timeout=10)
        audio_b64 = base64.b64encode(open(wav_path, "rb").read()).decode()
    finally:
        for p in (aiff_path, wav_path):
            if os.path.exists(p):
                os.unlink(p)

    return JSONResponse(content={"audioContent": audio_b64, "timepoints": []})
