"""
Jarvis TTS Server — Edge TTS (Microsoft Neural Voices)
FastAPI server for ESP32 JarvisPORT

Endpoints:
  POST /tts   { "text": "hola" }  -> audio/wav
  GET  /health
"""

import io
import re
import time
import logging
import asyncio

import edge_tts
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis-tts")

DEFAULT_VOICE = "es-ES-AlvaroNeural"
PORT = 8080


def clean_text(text: str) -> str:
    text = re.sub(r'[¡¿«»""]', '', text)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


async def generate_audio(text: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk['type'] == 'audio':
            buf.write(chunk['data'])
    return buf.getvalue()


app = FastAPI(title="Jarvis TTS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "jarvis-tts-edge"}


@app.post("/tts")
async def tts(req: TTSRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    voice = req.voice or DEFAULT_VOICE
    clean = clean_text(req.text)
    if not clean:
        raise HTTPException(400, "empty text after cleaning")

    logger.info(f"[TTS] Generating: \"{clean[:80]}\" voice={voice}")

    try:
        t0 = time.time()
        wav_bytes = await generate_audio(clean, voice)
        elapsed = time.time() - t0
        logger.info(f"[TTS] Generated {len(wav_bytes)} bytes in {elapsed:.2f}s")
    except Exception as e:
        logger.error(f"[TTS] Error: {e}")
        raise HTTPException(500, str(e))

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Access-Control-Allow-Origin": "*"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
