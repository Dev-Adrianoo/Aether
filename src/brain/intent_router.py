"""
IntentRouter — recebe texto classificado e despacha para o handler correto.
main.py instancia, injeta dependências e delega. Sem lógica de roteamento em main.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class IntentRouter:

    def __init__(
        self,
        speak: Callable[[str], Awaitable[None]],
        modules: Dict,
        stt_corrector,
        base_dir: Path,
        screenshot_handler: Callable[[str, float], Awaitable[None]],
        save_correction_fn: Callable[[str, str], Awaitable[None]],
        log_fn: Callable[[Dict], Awaitable[None]],
    ):
        self._speak = speak
        self._modules = modules
        self._stt_corrector = stt_corrector
        self._base_dir = base_dir
        self._handle_screenshot_command = screenshot_handler
        self._save_correction = save_correction_fn
        self._log = log_fn

        self._last_recognized: str = ""
        self._last_code_action: str = ""
        self._pending_learn: Optional[str] = None

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def route(self, command_text: str, confidence: float):
        """Classifica a intenção via LLM e despacha para o handler correto."""
        if self._pending_learn:
            await self._confirm_learn_app(command_text, confidence)
            return

        corrected = self._stt_corrector.apply(command_text)
        if corrected != command_text:
            print(f"[STT corrigido] '{command_text}' -> '{corrected}'")
        command_text = corrected

        last = self._last_recognized
        self._last_recognized = command_text

        llm = self._modules.get('integration')
        if not llm:
            await self._speak("LLM não disponível.")
            return

        from src.intents.intent_loader import build_prompt
        prompt = build_prompt(command_text, last_recognized=last)

        raw = await llm.classify(prompt)
        if not raw:
            await self._speak("Não entendi. Pode repetir?")
            return

        try:
            raw_clean = raw.strip().strip("```json").strip("```").strip()
            intent = json.loads(raw_clean)
        except Exception:
            await self._handle_conversation(command_text, confidence)
            return

        intent_type = intent.get("type", "conversation")

        if intent_type == "screenshot":
            monitor = intent.get("monitor", 1)
            await self._handle_screenshot_command(
                "direita" if monitor == 2 else "esquerda", confidence
            )

        elif intent_type == "action":
            await self._handle_action(intent.get("app", ""), confidence)

        elif intent_type == "terminal":
            action = intent.get("action", "open")
            shell = intent.get("shell", "powershell")
            await self._handle_openclaude_terminal(
                f"{'feche' if action == 'close' else 'abre'} {shell}", confidence
            )

        elif intent_type == "task":
            await self._handle_task_command(intent.get("text", ""), confidence)

        elif intent_type == "code_agent":
            await self._handle_code_agent(
                intent.get("prompt", command_text), confidence
            )

        elif intent_type == "correction":
            wrong = intent.get("wrong", "").strip()
            right = intent.get("right", "").strip()
            if wrong and right:
                self._stt_corrector.add(wrong, right)
                await self._save_correction(wrong, right)
                await self._speak(f"Entendido. Vou lembrar que '{wrong}' é '{right}'.")
            else:
                await self._speak("Não entendi a correção. Pode repetir?")

        elif intent_type == "conversation":
            response = intent.get("response", "")
            if response:
                await self._speak(response)
            else:
                await self._handle_conversation(command_text, confidence)

        else:
            await self._handle_conversation(command_text, confidence)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_task_command(self, command_text: str, confidence: float):
        from src.actions.system_actions import write_claude_task
        keywords = ["anota", "anote", "tarefa", "lembra", "lembre", "adiciona", "adicione", "registra", "registre"]
        task_text = command_text.lower()
        for kw in keywords:
            if kw in task_text:
                idx = task_text.find(kw) + len(kw)
                task_text = command_text[idx:].strip(" :,-")
                break
        if task_text:
            write_claude_task(task_text)
            response = await self._modules['integration'].ask_question(
                f"Acabei de anotar a tarefa: '{task_text}'. Confirme de forma natural e breve."
            )
            await self._speak(response or "Anotado.")
        else:
            await self._speak("Qual é a tarefa que devo anotar?")

    async def _handle_code_agent(self, command_text: str, confidence: float):
        oc = self._modules.get('openclaude')
        if not oc:
            await self._speak("OpenClaude nao esta disponivel.")
            return

        lumina_dir = str(self._base_dir)
        lumina_keywords = ["lumina", "voce mesmo", "em voce", "no seu codigo", "obsidian", "vault", "nova acao", "system_actions", "registry"]
        is_self = any(kw in command_text.lower() for kw in lumina_keywords)
        working_dir = lumina_dir if is_self else str(Path.home() / "Documents")

        prompt = (
            "Execute a tarefa diretamente sem pedir confirmação nem fazer perguntas. "
            "Não mostre design nem planejamento — só execute:\n\n"
            + command_text
        )

        await self._speak("Entendido. Abrindo o terminal.")
        oc.run_visible(prompt=prompt, working_dir=working_dir)
        self._last_code_action = command_text
        await self._speak("OpenClaude ta trabalhando. Acompanha no terminal.")

        asyncio.create_task(self._monitor_openclaude_sentinel())

    async def _handle_action(self, command_text: str, confidence: float):
        from src.actions.action_loader import dispatch, UnknownTarget
        result = dispatch(command_text)
        if isinstance(result, UnknownTarget):
            await self._handle_unknown_app(result.action_id)
        elif result:
            await self._speak(result)
        else:
            await self._handle_conversation(command_text, confidence)

    async def _handle_unknown_app(self, app_name: str):
        await self._speak(f"{app_name} não tá cadastrado. Quer que eu procure no sistema?")
        self._pending_learn = app_name

    async def _confirm_learn_app(self, command_text: str, confidence: float):
        app_name = self._pending_learn
        self._pending_learn = None

        if any(w in command_text.lower() for w in ["sim", "pode", "vai", "yes", "claro", "bora", "ok"]):
            oc = self._modules.get('openclaude')
            if not oc:
                await self._speak("OpenClaude não está disponível.")
                return
            learned_file = self._base_dir / "data" / "learned_path.txt"
            prompt = (
                f"Localize o executável (.exe) do aplicativo '{app_name}' neste sistema Windows. "
                f"Quando encontrar, escreva APENAS o path completo no arquivo: {learned_file}\n"
                f"Não pergunte nada, não explique — só escreva o path no arquivo."
            )
            await self._speak(f"Procurando {app_name} no sistema.")
            oc.run_visible(prompt=prompt)
            asyncio.create_task(self._apply_learned_path(app_name))
        else:
            await self._speak("Tudo bem, fica pra depois.")

    async def _apply_learned_path(self, app_name: str):
        learned_file = self._base_dir / "data" / "learned_path.txt"
        learned_file.unlink(missing_ok=True)

        for _ in range(300):
            await asyncio.sleep(1)
            if learned_file.exists():
                exe_path = learned_file.read_text(encoding="utf-8").strip()
                learned_file.unlink(missing_ok=True)
                if exe_path and Path(exe_path).exists():
                    from src.actions.action_loader import learn, dispatch
                    learn(app_name, exe_path)
                    await self._speak(f"Aprendi o caminho do {app_name}. Abrindo agora.")
                    dispatch(app_name)
                else:
                    await self._speak(f"OpenClaude não encontrou o {app_name}.")
                return
        await self._speak(f"Não recebi resposta sobre o {app_name}. Tenta de novo mais tarde.")

    async def _monitor_openclaude_sentinel(self):
        sentinel = self._base_dir / "data" / "run" / "done.sentinel"
        for _ in range(300):
            await asyncio.sleep(1)
            if sentinel.exists():
                try:
                    sentinel.unlink()
                except OSError:
                    pass
                await self._speak("OpenClaude terminou. Confere o resultado no terminal.")
                return
        await self._speak("OpenClaude ainda ta rodando. Me chama quando terminar.")

    async def _handle_openclaude_terminal(self, command_text: str, confidence: float):
        oc = self._modules.get('openclaude')
        if not oc:
            await self._speak("OpenClaude não está disponível.")
            return
        text = command_text.lower()
        if any(w in text for w in ["esconde", "fecha", "feche", "oculta", "esconder"]):
            closed = oc.hide_terminal()
            await self._speak("Terminal fechado." if closed else "Não tenho nenhum terminal aberto.")
            return

        shell = "cmd" if "cmd" in text else "powershell"
        already_open = oc._terminal_proc and oc._terminal_proc.poll() is None
        oc.show_terminal(shell=shell)
        await self._speak("Terminal já está aberto." if already_open else f"Terminal aberto em {shell}.")

    async def _handle_conversation(self, command_text: str, confidence: float):
        logger.debug(f"Conversa: {command_text}")
        question = command_text
        if self._last_code_action:
            question = (
                f"[Contexto: acabei de enviar ao OpenClaude a tarefa: '{self._last_code_action}'. "
                f"O terminal está aberto e pode ainda estar executando.]\n\n{command_text}"
            )
        response = await self._modules['integration'].ask_question(question)
        if not response:
            await self._speak("Não consegui responder agora. Pode repetir?")
            return

        if response.strip().startswith("CÓDIGO:"):
            task = response.strip()[len("CÓDIGO:"):].strip()
            await self._handle_code_agent(task, confidence)
            return

        await self._speak(response)
        await self._log({
            'type': 'conversation',
            'question': command_text,
            'answer': response,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })
