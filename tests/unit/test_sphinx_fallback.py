"""
Testes do SpeechRecognizer atual.

Historicamente este arquivo testava fallback CMU Sphinx dentro do VoiceListener.
A arquitetura mudou: VoiceListener delega STT para SpeechRecognizer, que usa Groq
Whisper como primario e Google Speech como fallback.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import config
from src.voice.speech_recognizer import SpeechRecognizer


class TestSpeechRecognizerFallback:
    def test_init_without_groq_key_uses_google_fallback(self):
        with patch.object(config.groq, "api_key", ""):
            recognizer = SpeechRecognizer()

        assert recognizer._groq_available is False
        assert recognizer._groq_client is None

    @pytest.mark.asyncio
    async def test_recognize_uses_groq_when_available(self):
        recognizer = SpeechRecognizer()
        recognizer._groq_available = True
        recognizer._recognize_groq = Mock(return_value="texto groq")
        recognizer._recognize_google = Mock(return_value="texto google")

        async def groq(audio):
            return "texto groq"

        async def google(audio):
            return "texto google"

        recognizer._recognize_groq = groq
        recognizer._recognize_google = google

        result = await recognizer.recognize(b"fake wav")

        assert result == "texto groq"

    @pytest.mark.asyncio
    async def test_recognize_falls_back_to_google_when_groq_returns_none(self):
        recognizer = SpeechRecognizer()
        recognizer._groq_available = True

        async def groq(audio):
            return None

        async def google(audio):
            return "texto google"

        recognizer._recognize_groq = groq
        recognizer._recognize_google = google

        result = await recognizer.recognize(b"fake wav")

        assert result == "texto google"

    @pytest.mark.asyncio
    async def test_recognize_uses_google_when_groq_unavailable(self):
        recognizer = SpeechRecognizer()
        recognizer._groq_available = False

        async def google(audio):
            return "texto google"

        recognizer._recognize_google = google

        result = await recognizer.recognize(b"fake wav")

        assert result == "texto google"

    def test_audio_rms_handles_empty_audio(self):
        assert SpeechRecognizer._audio_rms(b"") == 0.0

    def test_audio_rms_handles_silence_wav_payload(self):
        wav_header = b"0" * 44
        silence_pcm = b"\x00\x00" * 100

        assert SpeechRecognizer._audio_rms(wav_header + silence_pcm) == 0.0
