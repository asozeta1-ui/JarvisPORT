"""
Jarvis Server — Python + Kokoro ONNX + Vision
FastAPI server for ESP32 JarvisPORT

Endpoints:
  POST /tts       { "text": "hola", "voice": "em_alex" }  -> audio/wav
  POST /recognize  multipart: file (image)                  -> JSON { "description": "..." }
  GET  /health

Run locally:  python server.py
Deploy:       Railway / Render / Fly.io (see README)
"""

import io
import os
import re
import time
import base64
import logging
import urllib.request
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from kokoro_onnx import Kokoro

try:
    from groq import Groq
    GROQ_CLIENT = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")
    VISION_OK = True
except Exception as e:
    logger_v = logging.getLogger("jarvis-vision")
    logger_v.warning(f"[VISION] Groq no disponible: {e}")
    GROQ_CLIENT = None
    VISION_OK = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis-tts")

# ── Config ──────────────────────────────────────────────────────────────────

MODEL_DIR = os.environ.get("MODEL_DIR", ".")
KOKORO_MODEL = os.path.join(MODEL_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(MODEL_DIR, "voices-v1.0.bin")

# HuggingFace URLs for auto-download (Kokoro v1.0)
HF_BASE = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main"
MODEL_URL = os.environ.get("KOKORO_MODEL_URL", "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx")
VOICES_URL = os.environ.get("KOKORO_VOICES_URL", "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin")

DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "em_alex")
DEFAULT_LANG = os.environ.get("KOKORO_LANG", "es")
DEFAULT_SPEED = float(os.environ.get("KOKORO_SPEED", "1.0"))
PORT = int(os.environ.get("PORT", "8080"))


def download_if_missing(path: str, url: str, label: str):
    if os.path.exists(path):
        logger.info(f"[OK] {label} found: {path}")
        return
    logger.info(f"[DOWNLOAD] {label} from {url}")
    t0 = time.time()
    urllib.request.urlretrieve(url, path)
    logger.info(f"[DONE] {label} downloaded in {time.time()-t0:.1f}s ({os.path.getsize(path) / 1e6:.1f} MB)")


# ── Kokoro lifecycle ────────────────────────────────────────────────────────

kokoro: Kokoro | None = None


def load_kokoro():
    global kokoro
    download_if_missing(KOKORO_MODEL, MODEL_URL, "kokoro-v1.0.onnx")
    download_if_missing(KOKORO_VOICES, VOICES_URL, "voices-v1.0.bin")
    logger.info("Loading Kokoro ONNX model...")
    t0 = time.time()
    kokoro = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    logger.info(f"Kokoro loaded in {time.time()-t0:.1f}s")


def clean_text(text: str) -> str:
    text = re.sub(r'[¡¿«»""]', '', text)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


def generate_audio(text: str, voice: str, lang: str, speed: float):
    if kokoro is None:
        raise RuntimeError("Kokoro model not loaded")
    clean = clean_text(text)
    if not clean:
        raise ValueError("Empty text after cleaning")
    samples, sr = kokoro.create(clean, voice=voice, speed=speed, lang=lang)
    return samples, sr


# ── FastAPI ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_kokoro()
    yield

app = FastAPI(title="Jarvis TTS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    lang: str | None = None
    speed: float | None = None


@app.get("/health")
def health():
    return {
        "status": "ok" if kokoro else "error",
        "service": "jarvis-tts-kokoro",
        "model_loaded": kokoro is not None,
    }


@app.post("/tts")
def tts(req: TTSRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(400, "text is required")

    voice = req.voice or DEFAULT_VOICE
    lang = req.lang or DEFAULT_LANG
    speed = req.speed or DEFAULT_SPEED

    logger.info(f"[TTS] Generating: \"{req.text[:80]}\" voice={voice} lang={lang}")

    try:
        t0 = time.time()
        samples, sr = generate_audio(req.text, voice, lang, speed)
        buf = io.BytesIO()
        sf.write(buf, samples, sr, format="WAV")
        wav_bytes = buf.getvalue()
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


# ── Vision / Recognition ─────────────────────────────────────────────────────

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_MB = 5


@app.post("/recognize")
async def recognize(file: UploadFile = File(...)):
    try:
        if not file.content_type or file.content_type not in ALLOWED_TYPES:
            raise HTTPException(400, f"Tipo no soportado: {file.content_type}. Usa JPEG, PNG, WebP o GIF.")

        raw = await file.read()
        size_mb = len(raw) / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            raise HTTPException(400, f"Archivo demasiado grande: {size_mb:.1f}MB (max {MAX_FILE_MB}MB)")
        if len(raw) < 100:
            raise HTTPException(400, "Archivo demasiado pequeño, posible imagen corrupta.")

        logger.info(f"[RECOGNIZE] Recibido: {file.filename} ({size_mb:.2f}MB, {file.content_type})")

        if not VISION_OK or GROQ_CLIENT is None:
            raise HTTPException(503, "Modulo de vision no disponible. Configura GROQ_API_KEY.")

        b64 = base64.b64encode(raw).decode("utf-8")
        mime = file.content_type or "image/jpeg"

        t0 = time.time()
        response = GROQ_CLIENT.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe lo que ves en la imagen brevemente. Si hay texto, transcribelo. Responde en español."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                ]
            }],
            max_tokens=300,
            temperature=0.5,
        )
        elapsed = time.time() - t0

        desc = response.choices[0].message.content.strip()
        logger.info(f"[RECOGNIZE] OK en {elapsed:.2f}s: {desc[:80]}")

        return {"description": desc, "elapsed": round(elapsed, 2)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RECOGNIZE] Error: {type(e).__name__}: {e}")
        raise HTTPException(500, f"Error en reconocimiento: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
