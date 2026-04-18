"""
Testes unitarios do modulo de fala (TTSEngine).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import config
from src.voice.tts_engine import TTSEngine


class TestTTSEngine:
    @pytest.fixture
    def tts(self):
        return TTSEngine()

    def test_initialization(self, tts):
        expected_engine = config.tts.engine
        expected_use_edge_tts = expected_engine == "edge-tts"

        assert tts.use_edge_tts == expected_use_edge_tts
        assert tts.voice_name == config.tts.voice
        assert tts.rate == config.tts.rate
        assert tts.engine is None
        assert tts.voice is None

    def test_initialization_with_override(self):
        assert TTSEngine(use_edge_tts=False).use_edge_tts is False
        assert TTSEngine(use_edge_tts=True).use_edge_tts is True

    @pytest.mark.asyncio
    async def test_initialize_edge_tts(self):
        with patch("src.voice.tts_engine.edge_tts") as mock_edge_tts:
            tts = TTSEngine(use_edge_tts=True)
            success = await tts.initialize()

            assert success is True
            assert tts.engine == mock_edge_tts

    @pytest.mark.asyncio
    async def test_initialize_pyttsx3(self):
        with patch("src.voice.tts_engine.pyttsx3") as mock_pyttsx3:
            mock_engine = Mock()
            mock_pyttsx3.init.return_value = mock_engine
            mock_engine.getProperty.return_value = []

            tts = TTSEngine(use_edge_tts=False)
            success = await tts.initialize()

            assert success is True
            assert tts.engine == mock_engine
            mock_engine.setProperty.assert_any_call("rate", tts.rate)
            mock_engine.setProperty.assert_any_call("volume", 0.9)

    @pytest.mark.asyncio
    async def test_initialize_import_error(self):
        with patch("src.voice.tts_engine.edge_tts", None):
            tts = TTSEngine(use_edge_tts=True)
            success = await tts.initialize()

            assert success is False

    @pytest.mark.asyncio
    async def test_speak_edge_tts(self):
        with patch("src.voice.tts_engine.edge_tts") as mock_edge_tts:
            mock_communicate = Mock()
            mock_edge_tts.Communicate.return_value = mock_communicate

            async def mock_stream():
                yield {"type": "audio", "data": b"audio_data"}

            mock_communicate.stream.return_value = mock_stream()

            tts = TTSEngine(use_edge_tts=True)
            tts.engine = mock_edge_tts
            tts._play_audio = AsyncMock()

            await tts.speak("Texto de teste")

            mock_edge_tts.Communicate.assert_called_once_with("Texto de teste", "pt-BR-FranciscaNeural")
            tts._play_audio.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_speak_pyttsx3(self):
        mock_engine = Mock()

        tts = TTSEngine(use_edge_tts=False)
        tts.engine = mock_engine

        await tts.speak("Texto de teste")

        mock_engine.say.assert_called_once_with("Texto de teste")
        mock_engine.runAndWait.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_empty_text(self):
        tts = TTSEngine()
        tts.engine = Mock()

        await tts.speak("")
        await tts.speak("   ")
        await tts.speak(None)

        if hasattr(tts.engine, "say"):
            tts.engine.say.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_no_engine(self):
        tts = TTSEngine()
        tts.engine = None

        await tts.speak("Texto de fallback")

    @pytest.mark.asyncio
    async def test_test_voice(self):
        tts = TTSEngine()
        tts.speak = AsyncMock()

        await tts.test_voice()

        assert tts.speak.call_count == 8
        phrases = [call.args[0] for call in tts.speak.call_args_list]
        expected_phrases = [
            "Olá, eu sou a Lumina.",
            "Sistema de visão e audição ativo.",
            "Pronto para ajudar no desenvolvimento.",
            "Teste de voz concluído com sucesso.",
        ]
        for expected in expected_phrases:
            assert expected in phrases

    @pytest.mark.asyncio
    async def test_shutdown_pyttsx3(self):
        mock_engine = Mock()

        tts = TTSEngine(use_edge_tts=False)
        tts.engine = mock_engine

        await tts.shutdown()

        mock_engine.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_edge_tts(self):
        tts = TTSEngine(use_edge_tts=True)
        tts.engine = Mock()

        await tts.shutdown()

    def test_voice_mapping(self):
        voice_map = {
            "pt-br": "pt-BR-FranciscaNeural",
            "pt-pt": "pt-PT-RaquelNeural",
            "en-us": "en-US-AriaNeural",
            "en-gb": "en-GB-SoniaNeural",
        }

        assert voice_map.get("pt-br", "pt-BR-FranciscaNeural") == "pt-BR-FranciscaNeural"
        assert voice_map.get("es-es", "pt-BR-FranciscaNeural") == "pt-BR-FranciscaNeural"
