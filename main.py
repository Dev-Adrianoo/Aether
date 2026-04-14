#!/usr/bin/env python3
"""
Aether Sensory System - Main Entry Point
Sistema de visão, audição e fala para assistente de desenvolvimento
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
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
        """Inicializa todos os módulos do sistema"""
        try:
            # Importar módulos dinamicamente para evitar dependências circulares
            from src.vision.screenshot_manager import ScreenshotManager
            from src.hearing.voice_listener import VoiceListener
            from src.speech.tts_engine import TTSEngine
            from src.integration.openclaude_client import OpenClaudeClient
            from src.brain.obsidian_manager import ObsidianManager

            # Inicializar módulos
            self.modules['vision'] = ScreenshotManager()
            self.modules['hearing'] = VoiceListener()
            self.modules['speech'] = TTSEngine()
            self.modules['integration'] = OpenClaudeClient()
            self.modules['brain'] = ObsidianManager()

            # Configurar callbacks
            self._setup_callbacks()

            logger.info("Todos os módulos inicializados com sucesso")
            return True

        except ImportError as e:
            logger.error(f"Erro ao importar módulos: {e}")
            logger.info("Instale as dependências com: pip install -r requirements.txt")
            return False
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            return False

    def _setup_callbacks(self):
        """Configura callbacks entre módulos"""
        # Quando ouvir comando, processar e possivelmente falar
        self.modules['hearing'].on_command_detected = self._handle_command

        # Quando capturar screenshot importante, enviar para OpenClaude
        self.modules['vision'].on_important_screenshot = self._handle_screenshot

        # Registrar interações no Obsidian
        self.modules['brain'].log_interaction = self._log_to_obsidian

    async def _handle_command(self, command_text, confidence):
        """Processa comando de voz detectado"""
        logger.info(f"Comando detectado: {command_text} (confiança: {confidence})")

        # Log no Obsidian
        await self._log_to_obsidian({
            'type': 'voice_command',
            'text': command_text,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })

        # Se for comando de screenshot
        trigger_words = ['tela', 'print', 'screenshot', 'foto', 'mostra', 'olha']
        if any(word in command_text.lower() for word in trigger_words):
            logger.info("Trigger word detectada - capturando screenshot")
            await self.modules['vision'].capture_and_analyze(reason='voice_trigger')

            # Feedback por voz
            await self.modules['speech'].speak("Capturando tela para análise")

        # Outros comandos podem ser processados aqui

    async def _handle_screenshot(self, screenshot_data, analysis):
        """Processa screenshot importante"""
        logger.info(f"Screenshot analisado: {analysis.get('summary', 'Sem resumo')}")

        # Enviar para OpenClaude se for importante
        if analysis.get('has_errors') or analysis.get('needs_attention'):
            await self.modules['integration'].send_visual_context(screenshot_data, analysis)

    async def _log_to_obsidian(self, data):
        """Registra interação no Obsidian"""
        await self.modules['brain'].save_interaction(data)

    async def run(self):
        """Executa o loop principal do sistema"""
        if not await self.initialize():
            logger.error("Falha na inicialização. Encerrando.")
            return

        self.running = True
        logger.info("Aether Sensory System iniciado. Pressione Ctrl+C para encerrar.")

        try:
            # Iniciar módulos assíncronos
            tasks = [
                self.modules['hearing'].start_listening(),
                self.modules['vision'].start_monitoring(),
            ]

            # Executar todas as tarefas em paralelo
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("Encerrando por solicitação do usuário...")
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Encerra o sistema graciosamente"""
        self.running = False
        logger.info("Encerrando módulos...")

        # Encerrar módulos
        for name, module in self.modules.items():
            if hasattr(module, 'shutdown'):
                await module.shutdown()

        logger.info("Aether Sensory System encerrado.")

async def main():
    """Função principal"""
    aether = AetherSensorySystem()
    await aether.run()

if __name__ == "__main__":
    asyncio.run(main())