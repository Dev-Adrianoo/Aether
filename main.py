#!/usr/bin/env python3
"""
Lumina — ponto de entrada principal.
Orquestra visão, voz e integração com LLM.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Arquivo: tudo em DEBUG para diagnóstico
_file_handler = logging.FileHandler('lumina.log')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))

# Console: só erros reais — o output visual vem dos print() nos módulos
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(logging.Formatter('WARN  %(message)s'))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
logger = logging.getLogger(__name__)


class LuminaSensorySystem:

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.running = False
        self.modules = {}
        from src.voice.stt_corrector import STTCorrector
        self.stt_corrector = STTCorrector()
        self.router = None

    async def initialize(self):
        try:
            from src.vision.screenshot_manager import ScreenshotManager
            from src.voice.voice_listener import VoiceListener
            from src.voice.tts_engine import TTSEngine
            from src.integrations.openclaude_client import OpenClaudeClient
            from src.brain.obsidian_manager import ObsidianManager
            from src.brain.intent_router import IntentRouter
            from config import config

            print("Lumina iniciando...")

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
                'channels': config.audio.channels,
                'energy_threshold': config.audio.energy_threshold,
                'post_tts_mute_seconds': config.audio.post_tts_mute_seconds,
                'wake_cooldown': config.audio.wake_cooldown_seconds,
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
                await self._speak(
                    "Atenção: sem conexão com o LLM. Conversa livre indisponível."
                )

            self.router = IntentRouter(
                speak=self._speak,
                modules=self.modules,
                stt_corrector=self.stt_corrector,
                base_dir=self.base_dir,
                screenshot_handler=self._handle_screenshot_command,
                save_correction_fn=self._save_correction_to_vault,
                log_fn=self._log_to_obsidian,
            )

            self._setup_callbacks()
            return True

        except ImportError as e:
            print(f"[ERRO] Módulo não encontrado: {e}")
            return False
        except Exception as e:
            print(f"[ERRO] Falha na inicialização: {e}")
            return False

    async def _speak(self, text: str):
        """Fala e muta o microfone durante a reprodução para evitar loopback."""
        hearing = self.modules.get('hearing')
        post_tts_mute = 0.25
        if hearing:
            post_tts_mute = float(hearing.config.get('post_tts_mute_seconds', post_tts_mute))
        if hearing:
            hearing.is_speaking = True
            if hasattr(hearing, 'mute_for'):
                hearing.mute_for(3600)
        try:
            await self.modules['speech'].speak(text)
        finally:
            if hearing:
                hearing.is_speaking = False
                if hasattr(hearing, 'mute_for'):
                    hearing.mute_for(post_tts_mute)

    def _setup_callbacks(self):
        vision = self.modules['vision']
        hearing = self.modules['hearing']

        vision.on_important_screenshot = self._handle_screenshot

        hearing.register_command_handler("screenshot", self._handle_screenshot_command)
        hearing.register_command_handler("stop", self._handle_stop_command)
        hearing.register_command_handler("help", self._handle_help_command)
        hearing.register_command_handler("status", self._handle_status_command)
        hearing.register_command_handler("action", self.router.route)
        hearing.register_command_handler("task", self.router.route)
        hearing.register_command_handler("llm_route", self.router.route)
        hearing.register_command_handler("openclaude", self.router.route)
        hearing.register_command_handler("unknown", self.router.route)

    def _parse_monitor(self, command_text: str) -> int:
        text = command_text.lower()
        if any(w in text for w in ["direita", "segunda", "monitor 2", "tela 2", "dois"]):
            return 2
        return 1

    async def _handle_screenshot_command(self, command_text: str, confidence: float):
        monitor = self._parse_monitor(command_text)
        analysis = await self.modules['vision'].capture_and_analyze(
            reason='voice_command', monitor_index=monitor
        )
        if analysis and analysis.get('filepath'):
            w, h = analysis.get('dimensions', (0, 0))
            llm = self.modules.get('integration')
            if llm:
                llm.inject_screenshot_context(analysis, monitor=monitor)
            if self._should_answer_after_screenshot(command_text) and llm:
                answer = await llm.ask_question(
                    "Use o screenshot capturado agora para responder ao pedido do usuario. "
                    "Fale de forma direta o que esta visivel e, se houver problema ou erro, diga o provavel significado."
                )
                await self._speak(answer or "Capturei, mas nao consegui analisar agora.")
                return
            await self._speak(
                f"Print do monitor {monitor} capturado. {w}x{h} pixels. Pode me perguntar o que você vê."
            )
        else:
            await self._speak("Erro ao capturar tela.")

    def _should_answer_after_screenshot(self, command_text: str) -> bool:
        text = command_text.lower()
        triggers = [
            "me fala",
            "me diga",
            "o que voce ve",
            "o que você vê",
            "o que ve",
            "o que vê",
            "veja",
            "analisa",
            "analise",
            "o que acha",
            "problema",
            "erro",
        ]
        return any(trigger in text for trigger in triggers)

    async def _handle_stop_command(self, command_text: str, confidence: float):
        await self._speak("Encerrando")
        self.running = False

    async def _handle_status_command(self, command_text: str, confidence: float):
        await self._speak("Online e funcionando. LLM conectado, voz ativa.")

    async def _handle_help_command(self, command_text: str, confidence: float):
        await self._speak(
            "Diga Lumina seguido do seu comando. "
            "Posso capturar a tela, responder perguntas ou verificar meu status."
        )

    async def _handle_screenshot(self, screenshot_data, analysis):
        logger.debug(f"Screenshot: {analysis.get('summary', '')}")
        if analysis.get('has_errors') or analysis.get('needs_attention'):
            await self.modules['integration'].send_visual_context(screenshot_data, analysis)

    async def _save_correction_to_vault(self, wrong: str, right: str):
        from config import config
        vault = config.obsidian.dev_vault_path
        corrections_note = vault / "04_APRENDIZADOS" / "LEARN_STT_corrections.md"
        entry = f"- `{wrong}` -> `{right}`  <!-- {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"
        if not corrections_note.exists():
            corrections_note.write_text("# Correções STT\n\nMapeamentos aprendidos automaticamente.\n\n", encoding="utf-8")
        with open(corrections_note, "a", encoding="utf-8") as f:
            f.write(entry)

    async def _log_to_obsidian(self, data):
        await self.modules['brain'].save_interaction(data)

    async def run(self):
        if not await self.initialize():
            print("[ERRO] Falha na inicialização. Encerrando.")
            return

        self.running = True
        print("Pronto. Diga 'Lumina' para ativar.\n")

        interrupted = False
        try:
            await asyncio.gather(
                self.modules['hearing'].start(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            interrupted = True
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        finally:
            await self.shutdown(save_summary=not interrupted)

    async def shutdown(self, save_summary: bool = True):
        self.running = False
        for module in self.modules.values():
            if hasattr(module, 'stop'):
                await module.stop()
            elif hasattr(module, 'shutdown'):
                await module.shutdown()
        if save_summary:
            await self._save_session_summary()
        print("\nLumina encerrada.")

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
        except (asyncio.CancelledError, KeyboardInterrupt, GeneratorExit):
            return
        except Exception as e:
            logger.warning(f"Erro ao salvar resumo da sessão: {e}")


async def main():
    lumina = LuminaSensorySystem()
    await lumina.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLumina encerrada.")
