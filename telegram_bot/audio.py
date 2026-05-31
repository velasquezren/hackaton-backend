"""
audio.py — Módulo de procesamiento de audio para CampoIA Bot.

STT: Groq Whisper large-v3 (ya incluido en GROQ_API_KEY)
TTS: edge-tts con voz "es-BO-SofiaNeural" (español boliviano, sin API key)
Conversión: ffmpeg (mp3 → ogg/opus para Telegram)
"""

import os
import re
import logging
import tempfile
import subprocess

import edge_tts
from groq import Groq
from config import GROQ_API_KEY

logger = logging.getLogger(__name__)

# Cliente de Groq para Whisper (comparte API key con el LLM)
_groq_audio = Groq(api_key=GROQ_API_KEY)

# Voz edge-tts: español boliviano femenino de alta calidad
VOZ_ES_BO = "es-BO-SofiaNeural"


# ---------------------------------------------------------------------------
# STT — Speech to Text
# ---------------------------------------------------------------------------

def transcribir_audio(ogg_bytes: bytes) -> str:
    """
    Transcribe un audio OGG a texto en español usando Groq Whisper large-v3.
    Groq acepta OGG/Opus directamente, sin necesidad de conversión previa.

    Args:
        ogg_bytes: Bytes del archivo .ogg descargado de Telegram.

    Returns:
        Texto transcrito como string.

    Raises:
        RuntimeError: Si Groq devuelve error o el audio no se puede procesar.
    """
    try:
        respuesta = _groq_audio.audio.transcriptions.create(
            file=("audio.ogg", ogg_bytes),
            model="whisper-large-v3",
            language="es",
            response_format="text",
        )
        return str(respuesta).strip()
    except Exception as e:
        logger.error(f"[Whisper] Error al transcribir audio: {e}")
        raise RuntimeError(f"No se pudo transcribir el audio: {e}")


# ---------------------------------------------------------------------------
# TTS — Text to Speech
# ---------------------------------------------------------------------------

def _limpiar_para_tts(texto: str) -> str:
    """
    Elimina marcado Markdown y caracteres que suenan extraño en TTS.
    Preserva el contenido semántico para que el audio sea natural.
    """
    texto = re.sub(r"\*+", "", texto)          # negrita/cursiva **text**
    texto = re.sub(r"_+([^_]+)_+", r"\1", texto)  # cursiva _text_
    texto = re.sub(r"`+", "", texto)            # código `text`
    texto = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", texto)  # [label](url)
    texto = re.sub(r"⛔|⚠️|✅|🚨|ℹ️|🌧️|🌦️|☀️|💨|📊|🌤️|🌱|🌾|🌻|🌽", "", texto)
    texto = re.sub(r"\s+", " ", texto)         # espacios múltiples
    return texto.strip()


async def texto_a_voz_ogg(texto: str) -> bytes:
    """
    Convierte texto a un archivo OGG/Opus para enviar como Voice en Telegram.

    Pipeline:
        texto → edge-tts (MP3) → ffmpeg → OGG/Opus

    Args:
        texto: Texto a convertir (puede contener markdown, se limpiará).

    Returns:
        Bytes del archivo OGG/Opus listo para Telegram.

    Raises:
        RuntimeError: Si edge-tts o ffmpeg fallan.
        ValueError: Si el texto queda vacío tras la limpieza.
    """
    texto_limpio = _limpiar_para_tts(texto)
    if not texto_limpio:
        raise ValueError("El texto quedó vacío después de limpiar markdown.")

    mp3_path = None
    ogg_path = None

    try:
        # Archivos temporales
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            ogg_path = f.name

        # 1. Generar MP3 con edge-tts (voz española boliviana)
        comunicar = edge_tts.Communicate(texto_limpio, VOZ_ES_BO)
        await comunicar.save(mp3_path)

        # 2. Convertir MP3 → OGG/Opus con ffmpeg
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", mp3_path,
                "-c:a", "libopus",
                "-b:a", "64k",
                ogg_path,
            ],
            check=True,
            capture_output=True,
        )

        with open(ogg_path, "rb") as f:
            return f.read()

    except subprocess.CalledProcessError as e:
        logger.error(f"[ffmpeg] Error en conversión de audio: {e.stderr.decode(errors='replace')}")
        raise RuntimeError("Error al convertir el audio a formato OGG.")
    except Exception as e:
        logger.error(f"[TTS] Error generando audio: {e}")
        raise RuntimeError(f"Error en texto a voz: {e}")
    finally:
        for path in [mp3_path, ogg_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
