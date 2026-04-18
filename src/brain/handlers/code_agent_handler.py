"""
CodeAgentHandler — lida com execucao de codigo via OpenClaude e acoes de app.

Extraido de IntentRouter para seguir o padrao de Dependency Injection
adotado nos demais handlers (TerminalHandler, LearningHandler, TaskHandler).
"""

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_LUMINA_KEYWORDS = [
    "lumina", "voce mesmo", "em voce", "no seu codigo",
    "obsidian", "vault", "nova acao", "actions.yaml", "action_loader",
]


class CodeAgentHandler:
    """
    Gerencia execucao de tarefas via OpenClaude (code_agent) e despacho de
    acoes de aplicativo (action), incluindo self-learning de caminhos.
    """

    def __init__(
        self,
        speak: Callable[[str], Awaitable[None]],
        openclaude,                          # pode ser None
        base_dir: Path,
        dispatch_fn=None,                    # injetavel para testes
        learn_fn=None,                       # injetavel para testes
        conversation_fallback_fn=None,       # chamado quando dispatch retorna falsy
    ):
        self._speak = speak
        self._oc = openclaude
        self._base_dir = base_dir
        self._dispatch_fn = dispatch_fn
        self._learn_fn = learn_fn
        self._conversation_fallback_fn = conversation_fallback_fn

        self._pending_learn: Optional[str] = None
        self._last_code_action: str = ""
        self._openclaude_run_id: int = 0

    # ------------------------------------------------------------------
    # Propriedades publicas
    # ------------------------------------------------------------------

    @property
    def has_pending_learn(self) -> bool:
        return self._pending_learn is not None

    @property
    def last_code_action(self) -> str:
        return self._last_code_action

    # ------------------------------------------------------------------
    # Handlers publicos
    # ------------------------------------------------------------------

    async def handle_code_agent(self, command_text: str) -> None:
        if not self._oc:
            await self._speak("OpenClaude não está disponível.")
            return

        lumina_dir = str(self._base_dir)
        is_self = any(kw in command_text.lower() for kw in _LUMINA_KEYWORDS)
        working_dir = lumina_dir if is_self else str(Path.home() / "Documents")

        prompt = (
            "Execute a tarefa diretamente sem pedir confirmacao nem fazer perguntas. "
            "Nao mostre design nem planejamento - so execute:\n\n"
            + command_text
        )

        await self._speak("Entendido. Abrindo o terminal.")
        self._oc.run_visible(prompt=prompt, working_dir=working_dir)
        self._last_code_action = command_text
        self._openclaude_run_id += 1
        run_id = self._openclaude_run_id
        await self._speak("OpenClaude tá trabalhando. Acompanha no terminal.")

        asyncio.create_task(self._monitor_openclaude_sentinel(run_id))

    async def handle_action(self, command_text: str, confidence: float) -> None:
        from src.actions.action_loader import dispatch as _default_dispatch, UnknownTarget
        dispatch = self._dispatch_fn or _default_dispatch

        result = dispatch(command_text)
        if isinstance(result, UnknownTarget):
            await self._handle_unknown_app(result.action_id)
        elif result:
            await self._speak(result)
        else:
            if self._conversation_fallback_fn:
                await self._conversation_fallback_fn(command_text, confidence)

    async def confirm_learn_app(self, command_text: str, confidence: float) -> None:
        app_name = self._pending_learn
        self._pending_learn = None

        if any(w in command_text.lower() for w in ["sim", "pode", "vai", "yes", "claro", "bora", "ok"]):
            if not self._oc:
                await self._speak("OpenClaude não está disponível.")
                return
            learned_file = self._base_dir / "data" / "learned_path.txt"
            prompt = (
                f"Localize o executavel (.exe) do aplicativo '{app_name}' neste sistema Windows. "
                f"Quando encontrar, escreva APENAS o path completo no arquivo: {learned_file}\n"
                f"Nao pergunte nada, nao explique - so escreva o path no arquivo."
            )
            await self._speak(f"Procurando {app_name} no sistema.")
            self._oc.run_visible(prompt=prompt)
            asyncio.create_task(self._apply_learned_path(app_name))
        else:
            await self._speak("Tudo bem, fica pra depois.")

    # ------------------------------------------------------------------
    # Internos (testáveis)
    # ------------------------------------------------------------------

    async def _handle_unknown_app(self, app_name: str) -> None:
        await self._speak(f"{app_name} não tá cadastrado. Quer que eu procure no sistema?")
        self._pending_learn = app_name

    async def _apply_learned_path(self, app_name: str) -> None:
        from config import config
        learned_file = self._base_dir / "data" / "learned_path.txt"
        learned_file.unlink(missing_ok=True)

        async def _poll_learned():
            while not learned_file.exists():
                await asyncio.sleep(1)

        try:
            await asyncio.wait_for(_poll_learned(), timeout=config.sentinel_timeout)
        except asyncio.TimeoutError:
            await self._speak(f"Nao recebi resposta sobre o {app_name}. Tenta de novo mais tarde.")
            return

        exe_path = learned_file.read_text(encoding="utf-8").strip()
        learned_file.unlink(missing_ok=True)
        if exe_path and Path(exe_path).exists():
            from src.actions.action_loader import learn as _default_learn, dispatch as _default_dispatch
            learn = self._learn_fn or _default_learn
            dispatch = self._dispatch_fn or _default_dispatch
            learn(app_name, exe_path)
            await self._speak(f"Aprendi o caminho do {app_name}. Abrindo agora.")
            dispatch(app_name)
        else:
            await self._speak(f"OpenClaude nao encontrou o {app_name}.")

    async def _monitor_openclaude_sentinel(self, run_id: int) -> None:
        from config import config
        sentinel = self._base_dir / "data" / "run" / "done.sentinel"

        async def _poll_sentinel():
            while not sentinel.exists():
                await asyncio.sleep(1)

        try:
            await asyncio.wait_for(_poll_sentinel(), timeout=config.sentinel_timeout)
        except asyncio.TimeoutError:
            logger.warning("OpenClaude sentinel timeout; sem TTS para nao interromper conversa.")
            return

        if run_id != self._openclaude_run_id:
            logger.debug("Ignorando sentinel de execucao antiga do OpenClaude.")
            return

        try:
            sentinel.unlink()
        except OSError:
            pass
        await self._speak("OpenClaude terminou. Confere o resultado no terminal.")
