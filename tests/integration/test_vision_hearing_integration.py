"""
Testes de integracao entre visao e processamento de comandos de voz.
"""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vision.screenshot_manager import ScreenshotManager
from src.voice.audio_capture import AudioCapture
from src.voice.command_processor import CommandProcessor
from src.voice.speech_recognizer import SpeechRecognizer
from src.voice.voice_listener import VoiceListener


def make_listener(processor: CommandProcessor) -> VoiceListener:
    audio = Mock(spec=AudioCapture)
    recognizer = Mock(spec=SpeechRecognizer)
    return VoiceListener(
        audio_capture=audio,
        speech_recognizer=recognizer,
        command_processor=processor,
        config={"print_feedback": False},
    )


class TestVisionHearingIntegration:
    @pytest.fixture
    def vision_manager(self):
        manager = ScreenshotManager()
        manager.screenshot_interval = 2
        return manager

    @pytest.mark.asyncio
    async def test_trigger_word_capture_integration(self, vision_manager):
        vision_manager.capture_and_analyze = AsyncMock(return_value={"summary": "Teste", "dimensions": (1920, 1080)})

        command_text = "lumina tira um print da tela"

        should_capture = await vision_manager.check_trigger_words(command_text)
        assert should_capture is True

        result = await vision_manager.capture_and_analyze(reason="voice_trigger")
        assert result["summary"] == "Teste"

    @pytest.mark.asyncio
    async def test_command_processor_routes_wake_word_to_llm_handler(self):
        processor = CommandProcessor(wake_word="lumina", cooldown=0)
        handler = AsyncMock()
        processor.register_command("llm_route", handler)

        detected = await processor.process_text("lumina tira um print da tela")

        assert detected is True
        handler.assert_awaited_once()
        assert "tira um print da tela" in handler.await_args.args[0]

    @pytest.mark.asyncio
    async def test_command_processor_conversation_turn_is_not_reported_as_wake_word(self):
        processor = CommandProcessor(wake_word="lumina", cooldown=0)
        handler = AsyncMock()
        processor.register_command("llm_route", handler)

        await processor.process_text("lumina")
        detected = await processor.process_text("agora clique no botao")

        assert detected is False
        assert handler.await_count == 1

    def test_command_classification_integration(self):
        processor = CommandProcessor(wake_word="lumina")

        assert processor._classify_command("tira um print") == "llm_route"
        assert processor._classify_command("abre o youtube") == "llm_route"
        assert processor._classify_command("para tudo") == "stop"

    def test_confidence_calculation_integration(self):
        processor = CommandProcessor(wake_word="lumina")

        assert processor._calculate_confidence("tira um print da tela") > 0.5
        assert processor._calculate_confidence("captura isso aqui") > 0.5
        assert processor._calculate_confidence("teste qualquer") == 0.5

    def test_screenshot_decision_flow(self, vision_manager):
        vision_manager.last_screenshot_time = time.time() - 10
        should_capture, reason = vision_manager.should_capture_screenshot("tira um print agora")
        assert should_capture is True
        assert reason == "trigger_word"

        vision_manager.last_screenshot_time = time.time() - 70
        should_capture, reason = vision_manager.should_capture_screenshot()
        assert should_capture is True
        assert reason == "interval"

        vision_manager.last_screenshot_time = time.time() - 1
        should_capture, reason = vision_manager.should_capture_screenshot("texto normal")
        assert should_capture is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_voice_listener_callback_flow(self):
        processor = CommandProcessor(wake_word="lumina", cooldown=0)
        listener = make_listener(processor)
        listener.running = True
        listener.speech_recognizer.recognize = AsyncMock(return_value="lumina tira um print da tela por favor")

        handler = AsyncMock()
        listener.register_command_handler("llm_route", handler)

        await listener._process_audio_callback(b"audio")

        handler.assert_awaited_once()
        assert "tira um print da tela por favor" in handler.await_args.args[0]

    def test_economy_of_context_integration(self, vision_manager):
        vision_manager.min_interval_for_context = 5
        vision_manager.last_context_send_time = time.time() - 10

        scenarios = [
            ({"has_errors": True}, True),
            ({"has_errors": False, "needs_attention": True}, True),
            ({"has_errors": False, "needs_attention": False, "change_significance": "high"}, True),
            ({"has_errors": False, "needs_attention": False, "change_significance": "low"}, True),
        ]

        for analysis, should_send in scenarios:
            current_time = time.time()
            sends = False
            if analysis.get("has_errors", False):
                sends = True
            elif analysis.get("needs_attention", False):
                sends = True
            elif current_time - vision_manager.last_context_send_time > vision_manager.min_interval_for_context:
                sends = True
            elif analysis.get("change_significance") in ["high", "medium"]:
                if current_time - vision_manager.last_context_send_time > 60:
                    sends = True

            assert sends == should_send
