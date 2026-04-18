"""
Bounded conversation state for short-term continuity.

This module is pure state management. It does not execute actions, call LLMs,
touch files, or start async tasks.
"""

from typing import Optional


class ConversationState:
    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self.last_assistant_text = ""
        self.recent_turns: list[dict[str, str]] = []
        self.pending_context: Optional[dict] = None

    def record_assistant(self, text: str):
        self.last_assistant_text = text or ""
        self._set_pending_context_from_assistant(self.last_assistant_text)

    def _set_pending_context_from_assistant(self, text: str):
        normalized = self.normalize_text(text)
        if "quer que eu tire um print" in normalized or "quer que eu capture" in normalized:
            self.pending_context = {"type": "screenshot"}
        elif "qual elemento devo clicar" in normalized:
            self.pending_context = {"type": "ui_action"}

    def remember_turn(self, user_text: str, assistant_text: str):
        self.recent_turns.append({"user": user_text, "assistant": assistant_text})
        self.recent_turns = self.recent_turns[-self.max_turns:]

    def recent_context_text(self) -> str:
        if not self.recent_turns and not self.last_assistant_text:
            return ""

        lines = []
        for turn in self.recent_turns[-4:]:
            lines.append(f"Usuario: {turn['user']}")
            lines.append(f"Lumina: {turn['assistant']}")
        if self.last_assistant_text:
            lines.append(f"Ultima fala da Lumina: {self.last_assistant_text}")
        return "\n".join(lines)

    def consume_pending_context(self, command_text: str) -> Optional[dict]:
        if not self.pending_context:
            return None

        text = self.normalize_text(command_text)
        pending = self.pending_context

        if self.is_negative_reply(text):
            self.pending_context = None
            return {"type": "negative"}

        if pending["type"] == "screenshot" and self.is_affirmative_reply(text):
            self.pending_context = None
            return pending

        if pending["type"] == "ui_action":
            self.pending_context = None
            return pending

        return None

    @staticmethod
    def is_affirmative_reply(text: str) -> bool:
        words = text.replace(",", " ").replace(".", " ").split()
        if len(words) > 5:
            return False

        normalized = " ".join(words)
        affirmative_phrases = {
            "sim", "s", "pode", "pode sim", "claro", "ok", "okay",
            "yes", "yes i accept", "i accept", "aceito", "isso",
            "confirma", "confirmo", "pode tirar", "tira print",
            "captura", "capture", "manda",
        }
        return normalized in affirmative_phrases

    @staticmethod
    def is_negative_reply(text: str) -> bool:
        return any(phrase in text for phrase in ["nao", "não", "cancela", "deixa", "agora nao"])

    @staticmethod
    def normalize_text(text: str) -> str:
        import unicodedata

        normalized = unicodedata.normalize("NFD", text.lower())
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return " ".join(without_accents.split())
