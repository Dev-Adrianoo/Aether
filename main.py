#!/usr/bin/env python3
"""
Aether Sensory System — ponto de entrada principal.
Orquestra visão, voz e integração com LLM.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Arquivo: tudo em DEBUG para diagnóstico
_file_handler = logging.FileHandler('aether.log')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))

# Console: só erros reais — o output visual vem dos print() nos módulos
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(logging.Formatter('WARN  %(message)s'))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
logger = logging.getLogger(__name__)


class AetherSensorySystem:

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.running = False
        self.modules = {}

    async def initialize(self):
        try:
            from src.vision.screenshot_manager import ScreenshotManager
            from src.voice.voice_listener import VoiceListener
            from src.voice.tts_engine import TTSEngine
            from src.integrations.openclaude_client import OpenClaudeClient
            from src.brain.obsidian_manager import ObsidianManager
            from config import config

            print("Aether iniciando...")

            from src.integrations.openclaude_subprocess import OpenClaudeSubprocess
            oc = OpenClaudeSubprocess()
            if oc.is_available():
                self.modules['openclaude'] = oc
                print("[OK] OpenClaude subprocess disponível")
            else:
                print("[WARN] OpenClaude não encontrado — modo voz desativado")

            self.modules['vision'] = ScreenshotManager()
            self.modules['hearing'] = VoiceListener(config={
                'print_feedback': True,
                'device_index': config.audio.device_index,
                'sample_rate': config.audio.sample_rate,
            })
            self.modules['speech'] = TTSEngine(use_edge_tts=config.tts.engine == 'edge-tts')
            self.modules['integration'] = OpenClaudeClient()
            self.modules['brain'] = ObsidianManager(
                vault_path=str(config.obsidian.vault_path),
                log_folder=config.obsidian.log_folder
            )

            await self.modules['speech'].initialize()

            openclaude_ok = await self.modules['integration'].initialize()
            if openclaude_ok:
                print("[OK] LLM conectado (DeepSeek)")
            else:
                print("[WARN] LLM offline — conversa livre indisponível")
                await self.modules['speech'].speak(
                    "Atenção: sem conexão com o LLM. Conversa livre indisponível."
                )

            self._setup_callbacks()
            return True

        except ImportError as e:
            print(f"[ERRO] Módulo não encontrado: {e}")
            return False
        except Exception as e:
            print(f"[ERRO] Falha na inicialização: {e}")
            return False

    def _setup_callbacks(self):
        vision = self.modules['vision']
        hearing = self.modules['hearing']

        vision.on_important_screenshot = self._handle_screenshot

        hearing.register_command_handler("screenshot", self._handle_screenshot_command)
        hearing.register_command_handler("stop", self._handle_stop_command)
        hearing.register_command_handler("help", self._handle_help_command)
        hearing.register_command_handler("status", self._handle_status_command)
        hearing.register_command_handler("action", self._handle_action)
        hearing.register_command_handler("task", self._handle_task_command)
        hearing.register_command_handler("openclaude", self._handle_openclaude_terminal)
        hearing.register_command_handler("conversation", self._handle_conversation)
        hearing.register_command_handler("unknown", self._handle_conversation)

    def _parse_monitor(self, command_text: str) -> int:
        text = command_text.lower()
        if any(w in text for w in ["direita", "segunda", "monitor 2", "tela 2", "dois"]):
            return 2
        if any(w in text for w in ["esquerda", "primeira", "monitor 1", "tela 1", "um"]):
            return 1
        return 1

    async def _handle_screenshot_command(self, command_text: str, confidence: float):
        monitor = self._parse_monitor(command_text)
        label = f"monitor {monitor}"
        analysis = await self.modules['vision'].capture_and_analyze(
            reason='voice_command', monitor_index=monitor
        )
        if analysis and analysis.get('filepath'):
            w, h = analysis.get('dimensions', (0, 0))
            await self.modules['speech'].speak(
                f"Print do {label} capturado. {w}x{h} pixels, salvo em screenshots."
            )
        else:
            await self.modules['speech'].speak("Erro ao capturar tela.")

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
            response = await self.modules['integration'].ask_question(
                f"Acabei de anotar a tarefa: '{task_text}'. Confirme de forma natural e breve."
            )
            await self.modules['speech'].speak(response or "Anotado.")
        else:
            await self.modules['speech'].speak("Qual é a tarefa que devo anotar?")

    async def _handle_openclaude_terminal(self, command_text: str, confidence: float):
        oc = self.modules.get('openclaude')
        if not oc:
            await self.modules['speech'].speak("OpenClaude não está disponível.")
            return
        text = command_text.lower()
        if any(w in text for w in ["mostra", "abre", "exibe", "abrir"]):
            oc.show_terminal()
            await self.modules['speech'].speak("Abrindo OpenClaude.")
        elif any(w in text for w in ["esconde", "fecha", "oculta", "fechar"]):
            oc.hide_terminal()
            await self.modules['speech'].speak("Fechando OpenClaude.")

    async def _handle_action(self, command_text: str, confidence: float):
        from src.actions.registry import dispatch
        feedback = dispatch(command_text)
        if feedback:
            await self.modules['speech'].speak(feedback)
        else:
            await self._handle_conversation(command_text, confidence)

    async def _handle_stop_command(self, command_text: str, confidence: float):
        await self.modules['speech'].speak("Encerrando")
        self.running = False

    async def _handle_status_command(self, command_text: str, confidence: float):
        await self.modules['speech'].speak(
            "Online e funcionando. LLM conectado, voz ativa."
        )

    async def _handle_help_command(self, command_text: str, confidence: float):
        await self.modules['speech'].speak(
            "Diga Aether seguido do seu comando. "
            "Posso capturar a tela, responder perguntas ou verificar meu status."
        )

    async def _handle_conversation(self, command_text: str, confidence: float):
        logger.debug(f"Conversa: {command_text}")
        response = await self.modules['integration'].ask_question(command_text)
        if response:
            await self.modules['speech'].speak(response)
            await self._log_to_obsidian({
                'type': 'conversation',
                'question': command_text,
                'answer': response,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat()
            })
        else:
            await self.modules['speech'].speak("Não consegui responder agora. Pode repetir?")

    async def _handle_screenshot(self, screenshot_data, analysis):
        logger.debug(f"Screenshot: {analysis.get('summary', '')}")
        if analysis.get('has_errors') or analysis.get('needs_attention'):
            await self.modules['integration'].send_visual_context(screenshot_data, analysis)

    async def _log_to_obsidian(self, data):
        await self.modules['brain'].save_interaction(data)

    async def run(self):
        if not await self.initialize():
            print("[ERRO] Falha na inicialização. Encerrando.")
            return

        self.running = True
        print("Pronto. Diga 'Aether' para ativar.\n")

        try:
            await asyncio.gather(
                self.modules['hearing'].start(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        self.running = False
        await self._save_session_summary()
        for module in self.modules.values():
            if hasattr(module, 'stop'):
                await module.stop()
            elif hasattr(module, 'shutdown'):
                await module.shutdown()
        print("\nAether encerrado.")

    async def _save_session_summary(self):
        try:
            integration = self.modules.get('integration')
            brain = self.modules.get('brain')
            if not integration or not brain:
                return
            summary = await integration.summarize_session()
            if summary:
                integration._append_session_to_recentes(summary)
                await brain.save_interaction({
                    'type': 'session_summary',
                    'summary': summary,
                    'timestamp': datetime.now().isoformat()
                })
                print("Sessão resumida e salva no vault.")
        except Exception as e:
            logger.warning(f"Erro ao salvar resumo da sessão: {e}")


async def main():
    aether = AetherSensorySystem()
    await aether.run()


if __name__ == "__main__":
    asyncio.run(main())
