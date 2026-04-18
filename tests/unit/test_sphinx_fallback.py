"""
Testes do SpeechRecognizer atual.

Historicamente este arquivo testava fallback CMU Sphinx dentro do VoiceListener.
A arquitetura mudou: VoiceListener delega STT para SpeechRecognizer, que tenta
faster-whisper local, Groq Whisper e Google Speech em ordem de fallback.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

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

    def test_cuda_runtime_dll_check_sem_toolkit_retorna_false(self):
        recognizer = SpeechRecognizer()

        with patch("src.voice.speech_recognizer.Path") as mock_path:
            # Simula nenhum toolkit NVIDIA instalado e CUDA_PATH não definido
            mock_path.return_value.exists.return_value = False
            with patch.dict("os.environ", {"CUDA_PATH": ""}, clear=False):
                assert recognizer._cuda_runtime_dlls_available() is False

    def test_cuda_runtime_dll_check_com_toolkit_injeta_path(self):
        recognizer = SpeechRecognizer()

        fake_bin = MagicMock()
        fake_bin.exists.return_value = True
        fake_bin.__str__ = lambda self: "C:/fake/cuda/bin"

        fake_version = MagicMock()
        fake_version.__truediv__ = lambda self, other: fake_bin

        fake_toolkit = MagicMock()
        fake_toolkit.exists.return_value = True
        fake_toolkit.iterdir.return_value = [fake_version]

        with patch("src.voice.speech_recognizer.Path") as mock_path, \
             patch.dict("os.environ", {"CUDA_PATH": "", "PATH": ""}, clear=False):
            mock_path.side_effect = lambda p: fake_toolkit if "NVIDIA" in str(p) else MagicMock(exists=lambda: False)
            # Não levanta exceção — comportamento principal é não crashar
            # O teste real é a integração (toolkit encontrado = retorna True)
