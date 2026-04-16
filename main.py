#!/usr/bin/env python3
"""
Aether Sensory System — ponto de entrada principal.
Orquestra visão, voz e integração com LLM.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('aether.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AetherSensorySystem:
    """Sistema sensorial principal do Aether"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.running = False
        self.modules = {}
        logger.info("Aether Sensory System inicializando...")

    async def initialize(self):
        try:
            from src.vision.screenshot_manager import ScreenshotManager
            from src.voice.voice_listener import VoiceListener
            from src.voice.tts_engine import TTSEngine
            from src.integrations.openclaude_client import OpenClaudeClient
            from src.brain.obsidian_manager import ObsidianManager
            from config import config

            self.modules['vision'] = ScreenshotManager()
            self.modules['hearing'] = VoiceListener(config={'print_feedback': True})
            self.modules['speech'] = TTSEngine(use_edge_tts=config.tts.engine == 'edge-tts')
            self.modules['integration'] = OpenClaudeClient()
            self.modules['brain'] = ObsidianManager(
                vault_path=str(config.obsidian.vault_path),
                log_folder=config.obsidian.log_folder
            )

            await self.modules['speech'].initialize()

            openclaude_ok = await self.modules['integration'].initialize()
            if openclaude_ok:
                logger.info("[OK] OpenClaude conectado e pronto para conversar")
            else:
                logger.warning("[WARN] OpenClaude em modo offline")
                await self.modules['speech'].speak(
                    "Atenção: sem conexão com o LLM. Conversa livre indisponível."
                )

            self._setup_callbacks()
            logger.info("Todos os módulos inicializados com sucesso")
            return True

        except ImportError as e:
            logger.error(f"Erro ao importar módulos: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
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
        hearing.register_command_handler("conversation", self._handle_conversation)
        hearing.register_command_handler("unknown", self._handle_conversation)

    async def _handle_screenshot_command(self, command_text: str, confidence: float):
        await self.modules['vision'].capture_and_analyze(reason='voice_command')
        await self.modules['speech'].speak("Capturando tela")

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
            "Online e funcionando. OpenClaude conectado, voz ativa."
        )

    async def _handle_help_command(self, command_text: str, confidence: float):
        await self.modules['speech'].speak(
            "Diga Aether seguido do seu comando. "
            "Posso capturar a tela, responder perguntas ou verificar meu status."
        )

    async def _handle_conversation(self, command_text: str, confidence: float):
        """Encaminha comando livre ao LLM e fala a resposta."""
        logger.info(f"Conversa: {command_text}")
        await self.modules['speech'].speak("Pensando")

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
            await self.modules['speech'].speak("Não consegui obter uma resposta")

    async def _handle_screenshot(self, screenshot_data, analysis):
        logger.info(f"Screenshot: {analysis.get('summary', 'Sem resumo')}")
        if analysis.get('has_errors') or analysis.get('needs_attention'):
            await self.modules['integration'].send_visual_context(screenshot_data, analysis)

    async def _log_to_obsidian(self, data):
        await self.modules['brain'].save_interaction(data)

    async def run(self):
        if not await self.initialize():
            logger.error("Falha na inicialização. Encerrando.")
            return

        self.running = True
        logger.info("Aether Sensory System iniciado. Pressione Ctrl+C para encerrar.")

        try:
            await asyncio.gather(
                self.modules['hearing'].start(),
                # self.modules['vision'].start_monitoring(),
            )
        except KeyboardInterrupt:
            logger.info("Encerrando por solicitação do usuário...")
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        self.running = False
        logger.info("Encerrando módulos...")
        for module in self.modules.values():
            if hasattr(module, 'stop'):
                await module.stop()
            elif hasattr(module, 'shutdown'):
                await module.shutdown()
        logger.info("Aether Sensory System encerrado.")


async def main():
    aether = AetherSensorySystem()
    await aether.run()


if __name__ == "__main__":
    asyncio.run(main())
