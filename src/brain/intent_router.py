"""
IntentRouter â€" recebe texto classificado e despacha para o handler correto.
main.py instancia, injeta dependÃªncias e delega. Sem lÃ³gica de roteamento em main.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

from src.brain.action_gate import ActionGate
from src.brain.conversation_state import ConversationState
from src.brain.fast_command_router import FastCommandRouter
from src.brain.handlers.code_agent_handler import CodeAgentHandler
from src.brain.handlers.learning_handler import LearningHandler
from src.brain.handlers.task_handler import TaskHandler
from src.brain.handlers.terminal_handler import TerminalHandler
from src.brain.handlers.ui_action_handler import UIActionHandler
from src.learning.learning_manager import LearningManager

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
        self._raw_speak = speak
        self._speak = self._speak_and_remember
        self._modules = modules
        self._stt_corrector = stt_corrector
        self._base_dir = base_dir
        self._handle_screenshot_command = screenshot_handler
        self._save_correction = save_correction_fn
        self._log = log_fn

        self._last_recognized: str = ""
        self._conversation_state = ConversationState()
        self._learning = LearningManager(base_dir)
        self._action_gate = ActionGate()
        self._fast_command_router = FastCommandRouter()
        self._ui_action_handler = UIActionHandler(self._speak)
        self._terminal_handler = TerminalHandler(self._speak, self._modules.get('openclaude'))
        self._learning_handler = LearningHandler(self._speak, self._learning)
        self._task_handler = TaskHandler(self._speak, self._modules.get('integration'))
        self._code_agent_handler = CodeAgentHandler(
            speak=self._speak,
            openclaude=self._modules.get('openclaude'),
            base_dir=base_dir,
            conversation_fallback_fn=self._handle_conversation,
        )

    async def _speak_and_remember(self, text: str):
        self._conversation_state.record_assistant(text)
        await self._raw_speak(text)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def route(self, command_text: str, confidence: float):
        """Classifica a intenÃ§Ã£o via LLM e despacha para o handler correto."""
        if self._learning_handler.has_pending:
            await self._learning_handler.confirm_learning(command_text)
            return

        if self._code_agent_handler.has_pending_learn:
            await self._code_agent_handler.confirm_learn_app(command_text, confidence)
            return

        corrected = self._stt_corrector.apply(command_text)
        if corrected != command_text:
            print(f"[STT corrigido] '{command_text}' -> '{corrected}'")
        command_text = corrected

        alias_target = self._learning.resolve_alias(command_text)
        if alias_target:
            logger.info("Alias aplicado: %s -> %s", command_text, alias_target)
            command_text = alias_target

        if await self._handle_pending_context(command_text, confidence):
            return

        fast_command = self._fast_command_router.route(command_text)
        if fast_command and fast_command.type == "screenshot":
            await self._handle_screenshot_command(
                "direita" if fast_command.monitor == 2 else "esquerda", confidence
            )
            return

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
        if self._action_gate.should_block(intent_type, command_text):
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
            await self._code_agent_handler.handle_action(intent.get("app", ""), confidence)

        elif intent_type == "terminal":
            action = intent.get("action", "open")
            shell = intent.get("shell", "powershell")
            await self._handle_openclaude_terminal(
                f"{'feche' if action == 'close' else 'abre'} {shell}", confidence
            )

        elif intent_type == "task":
            await self._handle_task_command(intent.get("text", ""), confidence)

        elif intent_type == "code_agent":
            await self._code_agent_handler.handle_code_agent(intent.get("prompt", command_text))

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
            await self._learning_handler.handle_learn_alias(intent.get("alias", ""), intent.get("target", ""))

        elif intent_type == "learn_preference":
            await self._learning_handler.handle_learn_preference(
                intent.get("key", ""),
                intent.get("value", True),
                intent.get("description", ""),
            )

        elif intent_type == "forget_alias":
            await self._learning_handler.handle_forget_alias(intent.get("alias", ""))

        elif intent_type == "list_learning":
            await self._learning_handler.handle_list_learning()

        elif intent_type == "conversation":
            # sempre passa pelo ask_question â€" classify não tem system prompt nem vault
            await self._handle_conversation(
                command_text, confidence,
                model=model_for_intent("conversation")
            )

        else:
            await self._handle_conversation(command_text, confidence)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _handle_pending_context(self, command_text: str, confidence: float) -> bool:
        pending = self._conversation_state.consume_pending_context(command_text)
        if not pending:
            return False

        if pending["type"] == "negative":
            await self._speak("Tudo bem.")
            return True

        if pending["type"] == "screenshot":
            await self._handle_screenshot_command(command_text, confidence)
            return True

        if pending["type"] == "ui_action":
            await self._handle_ui_action(command_text, confidence)
            return True

        return False

    async def _handle_task_command(self, command_text: str, confidence: float):
        await self._task_handler.handle(command_text)

    async def _handle_openclaude_terminal(self, command_text: str, confidence: float):
        await self._terminal_handler.handle(command_text)

    async def _handle_ui_action(self, target: str, confidence: float):
        await self._ui_action_handler.handle(target, confidence)

    def _filter_tts_text(self, text: str) -> str:
        """
        Remove conteção interno que o usuário não precisa ouvir:
        - Paths absolutos do Windows (C:\\...)
        - Repetições do padrão CODIGO:' (JÁ tratado antes)
        - Comandos internos excessivos
        """
        import re

        # Remove paths absolutos do Windows (C:\...)
        text = re.sub(r'[A-Z]:\\[^ ]+', '', text)

        # Remove mÃºltiplos espaÃ§os resultantes
        text = ' '.join(text.split())

        return text.strip()

    async def _handle_conversation(self, command_text: str, confidence: float, model: Optional[str] = None):
        logger.debug(f"Conversa: {command_text}")
        question = command_text
        context = self._conversation_state.recent_context_text()
        if self._code_agent_handler.last_code_action:
            question = (
                f"[Contexto: acabei de enviar ao OpenClaude a tarefa: '{self._code_agent_handler.last_code_action}'. "
                f"O terminal esta aberto e pode ainda estar executando.]\n\n{command_text}"
            )
        elif context:
            question = f"[Contexto recente]\n{context}\n\n[Mensagem atual]\n{command_text}"
        response = await self._modules['integration'].ask_question(question, model=model)
        if not response:
            await self._speak("Não consegui responder agora. Pode repetir?")
            return

        if response.strip().startswith("CÓDIGO:"):
            task = response.strip()[len("CÓDIGO:"):].strip()
            if self._action_gate.should_block("code_agent", command_text):
                logger.info("Action Gate bloqueou CODIGO vindo da conversa: %s", command_text)
                await self._speak("Entendi como conversa, nao como ordem de execucao.")
                return
            await self._code_agent_handler.handle_code_agent(task)
            return

        # Filtrar conteÃºdo interno antes do TTS
        filtered_response = self._filter_tts_text(response)
        if filtered_response:
            await self._speak(filtered_response)
        else:
            # Se filtrou tudo, fallback para resposta genÃ©rica
            await self._speak("Feito.")

        await self._log({
            'type': 'conversation',
            'question': command_text,
            'answer': response,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })
        self._conversation_state.remember_turn(command_text, response)

    def _normalize_text(self, text: str) -> str:
        import unicodedata

        normalized = unicodedata.normalize("NFD", text.lower())
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return " ".join(without_accents.split())
