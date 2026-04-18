"""
Tests for UI action handler messaging.
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from src.brain.handlers.ui_action_handler import UIActionHandler


@dataclass
class FakeClickResult:
    success: bool


@pytest.mark.asyncio
async def test_empty_target_asks_for_element():
    speak = AsyncMock()
    handler = UIActionHandler(speak=speak)

    await handler.handle("")

    speak.assert_awaited_once_with("Qual elemento devo clicar?")


@pytest.mark.asyncio
async def test_reports_success_only_after_click_success():
    speak = AsyncMock()
    click = AsyncMock(return_value=FakeClickResult(success=True))
    handler = UIActionHandler(speak=speak, click_fn=click)

    await handler.handle("Yes, I accept")

    click.assert_awaited_once_with("Yes, I accept")
    assert [call.args[0] for call in speak.await_args_list] == [
        "Vou tentar clicar em 'Yes, I accept'.",
        "Consegui clicar em Yes, I accept.",
    ]


@pytest.mark.asyncio
async def test_reports_failure_when_click_fails():
    speak = AsyncMock()
    click = AsyncMock(return_value=FakeClickResult(success=False))
    handler = UIActionHandler(speak=speak, click_fn=click)

    await handler.handle("OK")

    assert [call.args[0] for call in speak.await_args_list] == [
        "Vou tentar clicar em 'OK'.",
        "Não consegui clicar em 'OK'.",
    ]
