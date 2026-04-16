"""
Testes unitários do VoiceListener (src/voice/voice_listener.py)
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.voice.voice_listener import VoiceListener
from src.voice.audio_capture import AudioCapture
from src.voice.speech_recognizer import SpeechRecognizer
from src.voice.command_processor import CommandProcessor


def make_listener(**kwargs):
    """Cria VoiceListener com dependências mockadas por padrão."""
    return VoiceListener(
        audio_capture=kwargs.get('audio_capture', Mock(spec=AudioCapture)),
        speech_recognizer=kwargs.get('speech_recognizer', Mock(spec=SpeechRecognizer)),
        command_processor=kwargs.get('command_processor', Mock(spec=CommandProcessor)),
        config=kwargs.get('config', {'print_feedback': False})
    )


class TestVoiceListenerInit:

    def test_injected_dependencies_stored(self):
        audio = Mock(spec=AudioCapture)
        recognizer = Mock(spec=SpeechRecognizer)
        processor = Mock(spec=CommandProcessor)
        listener = VoiceListener(
            audio_capture=audio,
            speech_recognizer=recognizer,
            command_processor=processor,
            config={'print_feedback': False}
        )
        assert listener.audio_capture is audio
        assert listener.speech_recognizer is recognizer
        assert listener.command_processor is processor
        assert listener.running is False

    def test_print_feedback_default_true(self):
        audio = Mock(spec=AudioCapture)
        recognizer = Mock(spec=SpeechRecognizer)
        processor = Mock(spec=CommandProcessor)
        listener = VoiceListener(audio_capture=audio, speech_recognizer=recognizer, command_processor=processor)
        assert listener._print is True

    def test_print_feedback_disabled_via_config(self):
        listener = make_listener()
        assert listener._print is False


class TestVoiceListenerStart:

    @pytest.mark.asyncio
    async def test_start_sets_running_true(self):
        listener = make_listener()
        listener.audio_capture.start_continuous_capture = AsyncMock()
        await listener.start()
        assert listener.running is True

    @pytest.mark.asyncio
    async def test_start_calls_audio_capture(self):
        listener = make_listener()
        listener.audio_capture.start_continuous_capture = AsyncMock()
        await listener.start()
        listener.audio_capture.start_continuous_capture.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_twice_ignores_second_call(self):
        listener = make_listener()
        listener.audio_capture.start_continuous_capture = AsyncMock()
        await listener.start()
        await listener.start()
        listener.audio_capture.start_continuous_capture.assert_called_once()


class TestVoiceListenerStop:

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self):
        listener = make_listener()
        listener.running = True
        listener.audio_capture.stop = AsyncMock()
        await listener.stop()
        assert listener.running is False

    @pytest.mark.asyncio
    async def test_stop_calls_audio_capture_stop(self):
        listener = make_listener()
        listener.running = True
        listener.audio_capture.stop = AsyncMock()
        await listener.stop()
        listener.audio_capture.stop.assert_called_once()


class TestProcessAudioCallback:

    @pytest.mark.asyncio
    async def test_recognized_text_sent_to_processor(self):
        processor = Mock(spec=CommandProcessor)
        processor.process_text = AsyncMock(return_value=False)
        recognizer = Mock(spec=SpeechRecognizer)
        recognizer.recognize = AsyncMock(return_value="iris captura tela")

        listener = make_listener(speech_recognizer=recognizer, command_processor=processor)
        listener.running = True

        await listener._process_audio_callback(b"fake_audio")

        recognizer.recognize.assert_called_once_with(b"fake_audio")
        processor.process_text.assert_called_once_with("iris captura tela")

    @pytest.mark.asyncio
    async def test_none_text_skips_processor(self):
        processor = Mock(spec=CommandProcessor)
        processor.process_text = AsyncMock()
        recognizer = Mock(spec=SpeechRecognizer)
        recognizer.recognize = AsyncMock(return_value=None)

        listener = make_listener(speech_recognizer=recognizer, command_processor=processor)
        listener.running = True

        await listener._process_audio_callback(b"silence")

        processor.process_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_running_skips_everything(self):
        recognizer = Mock(spec=SpeechRecognizer)
        recognizer.recognize = AsyncMock()

        listener = make_listener(speech_recognizer=recognizer)
        listener.running = False

        await listener._process_audio_callback(b"audio")

        recognizer.recognize.assert_not_called()

    @pytest.mark.asyncio
    async def test_recognition_exception_does_not_crash(self):
        recognizer = Mock(spec=SpeechRecognizer)
        recognizer.recognize = AsyncMock(side_effect=Exception("network error"))

        listener = make_listener(speech_recognizer=recognizer)
        listener.running = True

        await listener._process_audio_callback(b"audio")


class TestCallbackRegistration:

    def test_register_command_handler_delegates_to_processor(self):
        processor = Mock(spec=CommandProcessor)
        listener = make_listener(command_processor=processor)

        handler = Mock()
        listener.register_command_handler("screenshot", handler)

        processor.register_command.assert_called_once_with("screenshot", handler)

    def test_set_wake_callback_stored_on_processor(self):
        processor = Mock(spec=CommandProcessor)
        listener = make_listener(command_processor=processor)

        callback = Mock()
        listener.set_wake_callback(callback)

        assert processor.on_wake_detected == callback

    def test_set_command_callback_stored_on_processor(self):
        processor = Mock(spec=CommandProcessor)
        listener = make_listener(command_processor=processor)

        callback = Mock()
        listener.set_command_callback(callback)

        assert processor.on_command_detected == callback


class TestTestMicrophone:

    @pytest.mark.asyncio
    async def test_returns_true_when_speech_recognized(self):
        audio = Mock(spec=AudioCapture)
        audio.capture_audio = AsyncMock(return_value=b"audio_data")
        recognizer = Mock(spec=SpeechRecognizer)
        recognizer.recognize = AsyncMock(return_value="olá mundo")

        listener = make_listener(audio_capture=audio, speech_recognizer=recognizer)
        assert await listener.test_microphone() is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_audio_captured(self):
        audio = Mock(spec=AudioCapture)
        audio.capture_audio = AsyncMock(return_value=b"")

        listener = make_listener(audio_capture=audio)
        assert await listener.test_microphone() is False

    @pytest.mark.asyncio
    async def test_returns_false_when_speech_not_recognized(self):
        audio = Mock(spec=AudioCapture)
        audio.capture_audio = AsyncMock(return_value=b"audio_data")
        recognizer = Mock(spec=SpeechRecognizer)
        recognizer.recognize = AsyncMock(return_value=None)

        listener = make_listener(audio_capture=audio, speech_recognizer=recognizer)
        assert await listener.test_microphone() is False
