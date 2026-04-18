"""
LearningHandler — gerencia aprendizado de aliases e preferências com confirmação explícita.

Responsabilidades:
- Receber solicitações de aprendizado (alias, preferência, esquecimento, listagem)
- Solicitar confirmação antes de persistir
- Manter estado de confirmação pendente internamente
"""

from typing import Awaitable, Callable, Optional

from src.learning.learning_manager import LearningManager, PendingLearning


class LearningHandler:
    def __init__(
        self,
        speak: Callable[[str], Awaitable[None]],
        learning_manager: LearningManager,
    ):
        self._speak = speak
        self._learning = learning_manager
        self._pending_learning: Optional[PendingLearning] = None

    @property
    def has_pending(self) -> bool:
        """True se há uma confirmação pendente aguardando resposta do usuário."""
        return self._pending_learning is not None

    async def handle_learn_alias(self, alias: str, target: str) -> None:
        alias = alias.strip()
        target = target.strip()
        if not alias or not target:
            await self._speak("Não entendi o alias. Fala no formato: aprende que X significa Y.")
            return
        self._pending_learning = PendingLearning(kind="alias", alias=alias, target=target)
        await self._speak(f"Quer que eu aprenda que '{alias}' significa '{target}'?")

    async def handle_learn_preference(self, key: str, value, description: str) -> None:
        key = str(key).strip()
        if not key:
            await self._speak("Não entendi qual preferência devo aprender.")
            return
        self._pending_learning = PendingLearning(
            kind="preference",
            key=key,
            value=value,
            description=str(description or ""),
        )
        await self._speak(f"Quer que eu salve essa preferência: {key}?")

    async def handle_forget_alias(self, alias: str) -> None:
        alias = alias.strip()
        if not alias:
            await self._speak("Qual alias devo esquecer?")
            return
        removed = self._learning.forget_alias(alias)
        await self._speak("Esqueci esse alias." if removed else "Não encontrei esse alias.")

    async def handle_list_learning(self) -> None:
        aliases = self._learning.list_aliases()
        preferences = self._learning.list_preferences()
        if not aliases and not preferences:
            await self._speak("Ainda não tenho aprendizados salvos.")
            return
        parts = []
        if aliases:
            rendered = "; ".join(f"{a['phrase']} vira {a['target']}" for a in aliases[:3])
            parts.append(f"Aliases: {rendered}")
        if preferences:
            rendered = "; ".join(p["key"] for p in preferences[:3])
            parts.append(f"Preferências: {rendered}")
        await self._speak(". ".join(parts))

    async def confirm_learning(self, command_text: str) -> None:
        pending = self._pending_learning
        self._pending_learning = None
        if pending is None:
            await self._speak("Não há nada pendente para confirmar.")
            return
        text = LearningManager.normalize(command_text)
        confirmed = any(w in text for w in ["sim", "pode", "claro", "confirma", "confirmo", "ok", "isso"])
        if not confirmed:
            await self._speak("Tudo bem, não vou salvar esse aprendizado.")
            return

        if pending.kind == "alias":
            self._learning.learn_alias(pending.alias, pending.target)
            await self._speak(f"Aprendi. Quando você disser '{pending.alias}', vou entender como '{pending.target}'.")
            return

        if pending.kind == "preference":
            self._learning.learn_preference(pending.key, pending.value, pending.description)
            await self._speak("Preferência salva.")
            return

        await self._speak("Tipo de aprendizado desconhecido.")
