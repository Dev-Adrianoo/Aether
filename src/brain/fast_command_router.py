"""
Deterministic routing for obvious, low-risk voice commands.

This layer exists to avoid LLM calls for recurring commands where local rules are
more predictable and faster. It does not execute anything.
"""

from dataclasses import dataclass
from typing import Optional
import unicodedata


@dataclass(frozen=True)
class FastCommand:
    type: str
    monitor: int = 1


class FastCommandRouter:
    def route(self, command_text: str) -> Optional[FastCommand]:
        if self.looks_like_screenshot_request(command_text):
            monitor = 2 if self.mentions_right_monitor(command_text) else 1
            return FastCommand(type="screenshot", monitor=monitor)
        return None

    def looks_like_screenshot_request(self, command_text: str) -> bool:
        text = self.normalize_text(command_text)
        screen_terms = ["print", "screenshot", "tela", "monitor"]
        visual_verbs = [
            "olha", "olhe", "veja", "ver", "analisa", "analise",
            "captura", "capture", "tira", "tirar", "printa", "fotografa",
        ]
        answer_terms = [
            "me fala", "me falar", "me diga", "diz o que", "o que tem",
            "o que aparece", "o que ve", "o que voce ve", "o que ha",
        ]

        has_screen = any(term in text for term in screen_terms)
        asks_visual_action = any(term in text for term in visual_verbs)
        asks_answer = any(term in text for term in answer_terms)
        if self.is_first_person_narrative(text) and not asks_answer:
            return False
        return has_screen and (asks_visual_action or asks_answer)

    def mentions_right_monitor(self, command_text: str) -> bool:
        text = self.normalize_text(command_text)
        return any(term in text for term in ["direita", "monitor direito", "tela direita", "segunda tela", "monitor 2"])

    @staticmethod
    def is_first_person_narrative(normalized_text: str) -> bool:
        return normalized_text.startswith(("vou ", "eu vou ", "vou tentar ", "eu vou tentar "))

    @staticmethod
    def normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower())
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return " ".join(without_accents.split())
