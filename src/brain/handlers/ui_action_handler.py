"""
UI action handler.

Keeps UI-control messaging honest: announce an attempt, then report success or
failure based on the actual click result.
"""

from typing import Awaitable, Callable


class UIActionHandler:
    def __init__(self, speak: Callable[[str], Awaitable[None]], click_fn=None):
        self._speak = speak
        self._click_fn = click_fn

    async def handle(self, target: str, confidence: float = 0.0):
        if not target:
            await self._speak("Qual elemento devo clicar?")
            return

        await self._speak(f"Vou tentar clicar em '{target}'.")
        click_fn = self._click_fn or self._default_click_fn
        result = await click_fn(target)
        if result.success:
            await self._speak(f"Consegui clicar em {target}.")
        else:
            await self._speak(f"Não consegui clicar em '{target}'.")

    @staticmethod
    async def _default_click_fn(target: str):
        from src.actions.ui_controller import find_and_click

        return await find_and_click(target)
