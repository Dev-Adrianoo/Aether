"""
Reconhecimento de fala independente da captura de áudio.
Groq Whisper (primário, rápido e preciso) + Google Speech (fallback).
"""

import asyncio
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class SpeechRecognizer:

    def __init__(self, language: str = "pt-BR"):
        self.language = language
        self._groq_client = None
        self._sr_recognizer = None
        self._groq_available = False
        self._init_groq()

    def _init_groq(self):
        try:
            from groq import Groq
            api_key = os.getenv("GROQ_API_KEY", "")
            if api_key:
                self._groq_client = Groq(api_key=api_key)
                self._groq_available = True
                logger.info("Groq Whisper disponível")
            else:
                logger.warning("GROQ_API_KEY não configurada — usando Google Speech")
        except ImportError:
            logger.warning("groq não instalado — usando Google Speech. Instale: pip install groq")

    async def recognize(self, audio_bytes: bytes) -> Optional[str]:
        if self._groq_available:
            result = await self._recognize_groq(audio_bytes)
            if result:
                return result
            logger.debug("Groq falhou — tentando Google Speech")

        return await self._recognize_google(audio_bytes)

    @staticmethod
    def _audio_rms(audio_bytes: bytes) -> float:
        """Calcula RMS médio do payload PCM de um WAV (descarta header de 44 bytes)."""
        import struct
        import math
        pcm = audio_bytes[44:]
        if len(pcm) < 2:
            return 0.0
        samples = struct.unpack_from(f"<{len(pcm)//2}h", pcm)
        return math.sqrt(sum(s * s for s in samples) / len(samples))

    async def _recognize_groq(self, audio_bytes: bytes) -> Optional[str]:
        if self._audio_rms(audio_bytes) < 150:
            logger.debug("RMS muito baixo — descartando antes do Groq")
            return None
        try:
            # Groq espera um file-like com nome — usamos tupla (filename, bytes)
            result = await asyncio.to_thread(
                self._groq_client.audio.transcriptions.create,
                file=("audio.wav", audio_bytes),
                model="whisper-large-v3-turbo",
                language="pt",
                response_format="text",
            )
            text = result.strip() if isinstance(result, str) else result.text.strip()
            if text:
                logger.debug(f"Groq reconheceu: {text}")
                return text.lower()
            return None
        except Exception as e:
            logger.warning(f"Groq erro: {e}")
            return None

    async def _recognize_google(self, audio_bytes: bytes) -> Optional[str]:
        try:
            import speech_recognition as sr

            if self._sr_recognizer is None:
                self._sr_recognizer = sr.Recognizer()

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    tmp_path = f.name
                    f.write(audio_bytes)

                with sr.AudioFile(tmp_path) as source:
                    audio = self._sr_recognizer.record(source)

                text = await asyncio.to_thread(
                    self._sr_recognizer.recognize_google,
                    audio,
                    language=self.language
                )
                logger.debug(f"Google reconheceu: {text}")
                return text.lower()

            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"Google falhou: {e}")
            return None

    async def recognize_from_file(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                audio_bytes = f.read()
            return await self.recognize(audio_bytes)
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return None
