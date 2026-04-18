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

from src.learning.learning_manager import LearningManager, PendingLearning

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
        self._pending_learning: Optional[PendingLearning] = None
        self._learning = LearningManager(base_dir)
        self._openclaude_run_id = 0

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def route(self, command_text: str, confidence: float):
        """Classifica a intenção via LLM e despacha para o handler correto."""
        if self._pending_learning:
            await self._confirm_learning(command_text)
            return

        if self._pending_learn:
            await self._confirm_learn_app(command_text, confidence)
            return

        corrected = self._stt_corrector.apply(command_text)
        if corrected != command_text:
            print(f"[STT corrigido] '{command_text}' -> '{corrected}'")
        command_text = corrected

        alias_target = self._learning.resolve_alias(command_text)
        if alias_target:
            logger.info("Alias aplicado: %s -> %s", command_text, alias_target)
            command_text = alias_target

        last = self._last_recognized
        self._last_recognized = command_text

        llm = self._modules.get('integration')
        if not llm:
            await self._speak("LLM não disponível.")
            return

        from src.intents.intent_loader import build_prompt, classify_model, model_for_intent
        prompt = build_prompt(command_text, last_recognized=last)

        raw = await llm.classify(prompt, model=classify_model())
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
        if self._should_gate_execution(intent_type, command_text):
            logger.info("Action Gate bloqueou intent executavel '%s': %s", intent_type, command_text)
            await self._handle_conversation(
                command_text, confidence,
                model=model_for_intent("conversation")
            )
            return

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
            await self._handle_code_agent(intent.get("prompt", command_text), confidence)

        elif intent_type == "ui_action":
            await self._handle_ui_action(intent.get("target", ""), confidence)

        elif intent_type == "correction":
            wrong = intent.get("wrong", "").strip()
            right = intent.get("right", "").strip()
            if wrong and right:
                self._stt_corrector.add(wrong, right)
                await self._save_correction(wrong, right)
                await self._speak(f"Entendido. Vou lembrar que '{wrong}' é '{right}'.")
            else:
                await self._speak("Não entendi a correção. Pode repetir?")

        elif intent_type == "learn_alias":
            await self._handle_learn_alias(intent.get("alias", ""), intent.get("target", ""))

        elif intent_type == "learn_preference":
            await self._handle_learn_preference(
                intent.get("key", ""),
                intent.get("value", True),
                intent.get("description", ""),
            )

        elif intent_type == "forget_alias":
            await self._handle_forget_alias(intent.get("alias", ""))

        elif intent_type == "list_learning":
            await self._handle_list_learning()

        elif intent_type == "conversation":
            # sempre passa pelo ask_question — classify não tem system prompt nem vault
            await self._handle_conversation(
                command_text, confidence,
                model=model_for_intent("conversation")
            )

        else:
            await self._handle_conversation(command_text, confidence)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_task_command(self, command_text: str, confidence: float):
        from src.actions.task_store import write_task
        keywords = ["anota", "anote", "tarefa", "lembra", "lembre", "adiciona", "adicione", "registra", "registre"]
        task_text = command_text.lower()
        for kw in keywords:
            if kw in task_text:
                idx = task_text.find(kw) + len(kw)
                task_text = command_text[idx:].strip(" :,-")
                break
        if task_text:
            write_task(task_text)
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
        lumina_keywords = ["lumina", "voce mesmo", "em voce", "no seu codigo", "obsidian", "vault", "nova acao", "actions.yaml", "action_loader"]
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
        self._openclaude_run_id += 1
        run_id = self._openclaude_run_id
        await self._speak("OpenClaude ta trabalhando. Acompanha no terminal.")

        asyncio.create_task(self._monitor_openclaude_sentinel(run_id))

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
        from config import config
        learned_file = self._base_dir / "data" / "learned_path.txt"
        learned_file.unlink(missing_ok=True)

        async def _poll_learned():
            while not learned_file.exists():
                await asyncio.sleep(1)

        try:
            await asyncio.wait_for(_poll_learned(), timeout=config.sentinel_timeout)
        except asyncio.TimeoutError:
            await self._speak(f"Não recebi resposta sobre o {app_name}. Tenta de novo mais tarde.")
            return

        exe_path = learned_file.read_text(encoding="utf-8").strip()
        learned_file.unlink(missing_ok=True)
        if exe_path and Path(exe_path).exists():
            from src.actions.action_loader import learn, dispatch
            learn(app_name, exe_path)
            await self._speak(f"Aprendi o caminho do {app_name}. Abrindo agora.")
            dispatch(app_name)
        else:
            await self._speak(f"OpenClaude não encontrou o {app_name}.")

    async def _monitor_openclaude_sentinel(self, run_id: int):
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

    async def _handle_ui_action(self, target: str, confidence: float):
        if not target:
            await self._speak("Qual elemento devo clicar?")
            return
        await self._speak(f"Vou tentar clicar em '{target}'.")
        from src.actions.ui_controller import find_and_click
        result = await find_and_click(target)
        if result.success:
            await self._speak(f"Consegui clicar em {target}.")
        else:
            await self._speak(f"Não consegui clicar em '{target}'.")

    async def _handle_learn_alias(self, alias: str, target: str):
        alias = alias.strip()
        target = target.strip()
        if not alias or not target:
            await self._speak("Nao entendi o alias. Fala no formato: aprende que X significa Y.")
            return
        self._pending_learning = PendingLearning(kind="alias", alias=alias, target=target)
        await self._speak(f"Quer que eu aprenda que '{alias}' significa '{target}'?")

    async def _handle_learn_preference(self, key: str, value, description: str):
        key = str(key).strip()
        if not key:
            await self._speak("Nao entendi qual preferencia devo aprender.")
            return
        self._pending_learning = PendingLearning(
            kind="preference",
            key=key,
            value=value,
            description=str(description or ""),
        )
        await self._speak(f"Quer que eu salve essa preferencia: {key}?")

    async def _handle_forget_alias(self, alias: str):
        alias = alias.strip()
        if not alias:
            await self._speak("Qual alias devo esquecer?")
            return
        removed = self._learning.forget_alias(alias)
        await self._speak("Esqueci esse alias." if removed else "Nao encontrei esse alias.")

    async def _handle_list_learning(self):
        aliases = self._learning.list_aliases()
        preferences = self._learning.list_preferences()
        if not aliases and not preferences:
            await self._speak("Ainda nao tenho aprendizados salvos.")
            return

        parts = []
        if aliases:
            rendered = "; ".join(f"{a['phrase']} vira {a['target']}" for a in aliases[:3])
            parts.append(f"Aliases: {rendered}")
        if preferences:
            rendered = "; ".join(p["key"] for p in preferences[:3])
            parts.append(f"Preferencias: {rendered}")
        await self._speak(". ".join(parts))

    async def _confirm_learning(self, command_text: str):
        pending = self._pending_learning
        self._pending_learning = None
        text = self._normalize_text(command_text)
        confirmed = any(w in text for w in ["sim", "pode", "claro", "confirma", "confirmo", "ok", "isso"])
        if not confirmed:
            await self._speak("Tudo bem, nao vou salvar esse aprendizado.")
            return

        if pending.kind == "alias":
            self._learning.learn_alias(pending.alias, pending.target)
            await self._speak(f"Aprendi. Quando voce disser '{pending.alias}', vou entender como '{pending.target}'.")
            return

        if pending.kind == "preference":
            self._learning.learn_preference(pending.key, pending.value, pending.description)
            await self._speak("Preferencia salva.")
            return

        await self._speak("Tipo de aprendizado desconhecido.")

    def _filter_tts_text(self, text: str) -> str:
        """
        Remove conteúdo interno que o usuário não precisa ouvir:
        - Paths absolutos do Windows (C:\\...)
        - Repetições do padrão 'CÓDIGO:' (já tratado antes)
        - Comandos internos excessivos
        """
        import re

        # Remove paths absolutos do Windows (C:\...)
        text = re.sub(r'[A-Z]:\\[^ ]+', '', text)

        # Remove múltiplos espaços resultantes
        text = ' '.join(text.split())

        return text.strip()

    async def _handle_conversation(self, command_text: str, confidence: float, model: Optional[str] = None):
        logger.debug(f"Conversa: {command_text}")
        question = command_text
        if self._last_code_action:
            question = (
                f"[Contexto: acabei de enviar ao OpenClaude a tarefa: '{self._last_code_action}'. "
                f"O terminal está aberto e pode ainda estar executando.]\n\n{command_text}"
            )
        response = await self._modules['integration'].ask_question(question, model=model)
        if not response:
            await self._speak("Não consegui responder agora. Pode repetir?")
            return

        if response.strip().startswith("CÓDIGO:"):
            task = response.strip()[len("CÓDIGO:"):].strip()
            if self._should_gate_execution("code_agent", command_text):
                logger.info("Action Gate bloqueou CODIGO vindo da conversa: %s", command_text)
                await self._speak("Entendi como conversa, nao como ordem de execucao.")
                return
            await self._handle_code_agent(task, confidence)
            return

        # Filtrar conteúdo interno antes do TTS
        filtered_response = self._filter_tts_text(response)
        if filtered_response:
            await self._speak(filtered_response)
        else:
            # Se filtrou tudo, fallback para resposta genérica
            await self._speak("Feito.")

        await self._log({
            'type': 'conversation',
            'question': command_text,
            'answer': response,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })

    def _should_gate_execution(self, intent_type: str, command_text: str) -> bool:
        """
        Mantem o modo Jarvis ouvindo sempre, mas bloqueia execucao quando a fala
        parece narrativa, pergunta, brainstorm ou reclamacao em vez de ordem direta.
        """
        executable_intents = {"action", "terminal", "task", "code_agent", "ui_action"}
        if intent_type not in executable_intents:
            return False
        return not self._is_explicit_execution_request(command_text)

    def _is_explicit_execution_request(self, command_text: str) -> bool:
        text = self._normalize_text(command_text)

        blockers = [
            "vou ",
            "eu vou ",
            "eu iria ",
            "eu falei que eu iria",
            "vou tentar",
            "estou pensando",
            "to pensando",
            "tô pensando",
            "eu acho",
            "nao pedi",
            "não pedi",
            "nao faz",
            "não faz",
            "nao precisa",
            "não precisa",
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
        if any(blocker in text for blocker in blockers):
            return False

        explicit_phrases = [
            "quero que voce",
            "quero que você",
            "preciso que voce",
            "preciso que você",
            "gostaria que voce",
            "gostaria que você",
            "coloca nos seus aprendizados",
            "coloque nos seus aprendizados",
        ]
        if any(phrase in text for phrase in explicit_phrases):
            return True

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
            "faça",
        ]
        first_word = text.split(" ", 1)[0] if text else ""
        return first_word in imperative_prefixes

    def _normalize_text(self, text: str) -> str:
        import unicodedata

        normalized = unicodedata.normalize("NFD", text.lower())
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return " ".join(without_accents.split())
