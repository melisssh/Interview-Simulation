import os
import re
import base64
import subprocess
import tempfile
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from . import auth

router = APIRouter()

GOOGLE_TTS_KEY = os.getenv("GOOGLE_TTS_KEY", "")
USE_GOOGLE_TTS = False  # True yap → Google TTS (lip-sync iyi, quota harcar)
                        # False  → macOS say (ücretsiz, lip-sync yok)

SAY_VOICE = "Samantha"


def _ssml_to_text(ssml: str) -> str:
    text = re.sub(r"<[^>]+>", " ", ssml)
    return re.sub(r"\s+", " ", text).strip()


@router.post("/tts")
async def tts(request: Request, _current_user=Depends(auth.get_current_user)):
    body = await request.json()

    if USE_GOOGLE_TTS:
        # --- Google Cloud TTS (lip-sync + iyi ses, quota harcar) ---
        key = GOOGLE_TTS_KEY
        if not key:
            raise HTTPException(status_code=503, detail="GOOGLE_TTS_KEY not set")

        audio_cfg = body.get("audioConfig", {})
        if audio_cfg.get("audioEncoding") == "OGG-OPUS":
            audio_cfg["audioEncoding"] = "OGG_OPUS"
            body["audioConfig"] = audio_cfg

        body["enableTimePointing"] = ["SSML_MARK"]

        url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={key}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        data.setdefault("timepoints", [])
        return JSONResponse(content=data)

    else:
        # --- macOS say (ücretsiz, quota yok) ---
        inp = body.get("input", {})
        text = _ssml_to_text(inp.get("ssml", "")) or inp.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="No text")

        aiff_fd, aiff_path = tempfile.mkstemp(suffix=".aiff")
        wav_fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(aiff_fd); os.close(wav_fd)
        try:
            subprocess.run(["say", "-v", SAY_VOICE, "-o", aiff_path, text], check=True, timeout=30)
            subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path], check=True, timeout=10)
            audio_b64 = base64.b64encode(open(wav_path, "rb").read()).decode()
        finally:
            for p in (aiff_path, wav_path):
                if os.path.exists(p): os.unlink(p)

        return JSONResponse(content={"audioContent": audio_b64, "timepoints": []})
