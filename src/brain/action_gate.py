"""
Safety gate for executable intents.

This module is intentionally pure: no config, filesystem, network, async tasks,
or runtime dependencies. It decides whether an executable intent is explicit
enough to run.
"""

import unicodedata


class ActionGate:
    executable_intents = {"action", "terminal", "task", "code_agent", "ui_action"}

    blockers = [
        "vou ",
        "eu vou ",
        "eu iria ",
        "eu falei que eu iria",
        "vou tentar",
        "estou pensando",
        "to pensando",
        "to pensando",
        "eu acho",
        "nao pedi",
        "nao faz",
        "nao precisa",
        "estamos conversando",
        "brainstorm",
        "opinia",
        "compensa",
        "por que",
        "porque",
        "me explica",
        "me fale onde",
        "me fala onde",
        "qual ",
        "quais ",
    ]

    explicit_phrases = [
        "quero que voce",
        "preciso que voce",
        "gostaria que voce",
        "coloca nos seus aprendizados",
        "coloque nos seus aprendizados",
    ]

    imperative_prefixes = [
        "abre",
        "abra",
        "fecha",
        "feche",
        "cria",
        "crie",
        "edita",
        "edite",
        "gera",
        "gere",
        "roda",
        "rode",
        "executa",
        "execute",
        "clica",
        "clique",
        "pressiona",
        "pressione",
        "seleciona",
        "selecione",
        "anota",
        "anote",
        "registra",
        "registre",
        "aprende",
        "aprenda",
        "faz",
        "faca",
    ]

    def should_block(self, intent_type: str, command_text: str) -> bool:
        if intent_type not in self.executable_intents:
            return False
        return not self.is_explicit_execution_request(command_text)

    def is_explicit_execution_request(self, command_text: str) -> bool:
        text = self.normalize_text(command_text)

        if any(blocker in text for blocker in self.blockers):
            return False

        if any(phrase in text for phrase in self.explicit_phrases):
            return True

        first_word = text.split(" ", 1)[0] if text else ""
        return first_word in self.imperative_prefixes

    @staticmethod
    def normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFD", text.lower())
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return " ".join(without_accents.split())
