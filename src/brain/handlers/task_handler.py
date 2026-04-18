"""
Task handler.

Extrai e persiste tarefas a partir do texto do comando.
"""

from typing import Awaitable, Callable, Optional


_KEYWORDS = [
    "anota", "anote", "tarefa", "lembra", "lembre",
    "adiciona", "adicione", "registra", "registre",
]


class TaskHandler:
    def __init__(
        self,
        speak: Callable[[str], Awaitable[None]],
        integration=None,
        write_task_fn=None,
    ):
        self._speak = speak
        self._integration = integration
        self._write_task = write_task_fn or self._default_write_task

    @staticmethod
    def _default_write_task(text: str) -> None:
        from src.actions.task_store import write_task
        write_task(text)

    async def handle(self, command_text: str) -> None:
        task_text = command_text.lower()
        for kw in _KEYWORDS:
            if kw in task_text:
                idx = task_text.find(kw) + len(kw)
                task_text = command_text[idx:].strip(" :,-")
                break

        if task_text:
            self._write_task(task_text)
            response = None
            if self._integration:
                response = await self._integration.ask_question(
                    f"Acabei de anotar a tarefa: '{task_text}'. Confirme de forma natural e breve."
                )
            await self._speak(response or "Anotado.")
        else:
            await self._speak("Qual é a tarefa que devo anotar?")
