"""
Testes de integracao leves para TTS.

Nao reproduzem audio real; validam que chamadas sequenciais nao quebram o fluxo.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.voice.tts_engine import TTSEngine


@pytest.mark.asyncio
async def test_tts_sequential_speak_calls_do_not_block():
    tts = TTSEngine(use_edge_tts=True)
    tts.engine = object()
    tts.speak = AsyncMock()

    phrases = [
        "Primeira fala do sistema Lumina.",
        "Segunda fala do sistema Lumina.",
        "Terceira fala do sistema Lumina.",
    ]

    for phrase in phrases:
        await tts.speak(phrase)

    assert tts.speak.await_count == len(phrases)


@pytest.mark.asyncio
async def test_tts_shutdown_without_engine_is_safe():
    tts = TTSEngine(use_edge_tts=True)
    tts.engine = None

    await tts.shutdown()
