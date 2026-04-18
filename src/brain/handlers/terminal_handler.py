"""
Terminal handler.

Abre ou fecha um terminal externo (cmd / powershell) via openclaude.
"""

from typing import Awaitable, Callable, Optional


_HIDE_WORDS = {"esconde", "fecha", "feche", "oculta", "esconder"}


class TerminalHandler:
    def __init__(
        self,
        speak: Callable[[str], Awaitable[None]],
        openclaude=None,
    ):
        self._speak = speak
        self._oc = openclaude

    async def handle(self, command_text: str) -> None:
        if not self._oc:
            await self._speak("OpenClaude não está disponível.")
            return

        text = command_text.lower()

        if any(w in text for w in _HIDE_WORDS):
            closed = self._oc.hide_terminal()
            await self._speak(
                "Terminal fechado." if closed else "Não tenho nenhum terminal aberto."
            )
            return

        shell = "cmd" if "cmd" in text else "powershell"
        already_open = self._oc.is_terminal_open()
        self._oc.show_terminal(shell=shell)
        await self._speak(
            "Terminal já está aberto." if already_open else f"Terminal aberto em {shell}."
        )
