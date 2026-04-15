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
            # Importar módulos
            from src.vision.screenshot_manager import ScreenshotManager
            from src.voice.voice_listener import VoiceListener
            from src.voice.tts_engine import TTSEngine
            from src.integrations.openclaude_client import OpenClaudeClient
            from src.brain.obsidian_manager import ObsidianManager
            from config import config

            # Inicializar módulos
            self.modules['vision'] = ScreenshotManager()
            self.modules['hearing'] = VoiceListener(config={'print_feedback': True})

            # Usar configuração do sistema para TTS
            from config import config
            use_edge_tts = config.tts.engine == 'edge-tts'
            self.modules['speech'] = TTSEngine(use_edge_tts=use_edge_tts)

            self.modules['integration'] = OpenClaudeClient()
            self.modules['brain'] = ObsidianManager(
                vault_path=str(config.obsidian.vault_path),
                log_folder=config.obsidian.log_folder
            )

            # Inicializar módulos assíncronos
            await self.modules['speech'].initialize()

            # Inicializar OpenClaude
            openclaude_ok = await self.modules['integration'].initialize()
            if openclaude_ok:
                logger.info("[OK] OpenClaude conectado e pronto para conversar")
            else:
                logger.warning("[WARN] OpenClaude em modo offline")

            # Configurar callbacks
            self._setup_callbacks()

            logger.info("Todos os módulos inicializados com sucesso")
            return True

        except ImportError as e:
            logger.error(f"Erro ao importar módulos: {e}")
            logger.info("Instale as dependências: pip install pyttsx3 sounddevice scipy")
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

        # Registrar handlers de comandos
        self._register_command_handlers()

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

    def _register_command_handlers(self):
        """Registra handlers para tipos de comandos"""
        # Handler para screenshot
        self.modules['hearing'].register_command_handler(
            "screenshot",
            lambda cmd, conf: self._handle_screenshot_command(cmd, conf)
        )

        # Handler para conversação geral
        self.modules['hearing'].register_command_handler(
            "unknown",  # Comandos não classificados
            lambda cmd, conf: self._handle_conversation(cmd, conf)
        )

        # Handler para conversação direta
        self.modules['hearing'].register_command_handler(
            "conversation",
            lambda cmd, conf: self._handle_conversation(cmd, conf)
        )

        # Handler para ajuda
        self.modules['hearing'].register_command_handler(
            "help",
            lambda cmd, conf: self._handle_help_command(cmd, conf)
        )

        # Handler para status
        self.modules['hearing'].register_command_handler(
            "status",
            lambda cmd, conf: self._handle_status_command(cmd, conf)
        )

    async def _handle_screenshot_command(self, command_text: str, confidence: float):
        """Handler para comandos de screenshot"""
        logger.info(f"Executando comando de screenshot: {command_text}")
        await self.modules['vision'].capture_and_analyze(reason='voice_command')
        await self.modules['speech'].speak("Capturando tela para análise")

    async def _handle_conversation(self, command_text: str, confidence: float):
        """Handler para conversação geral com OpenClaude"""
        logger.info(f"Processando conversação: {command_text}")

        # Feedback de que está processando
        await self.modules['speech'].speak("Deixe-me pensar")

        # Perguntar ao OpenClaude
        response = await self.modules['integration'].ask_question(command_text)

        if response:
            # Falar a resposta
            await self.modules['speech'].speak(response)

            # Log no Obsidian
            await self._log_to_obsidian({
                'type': 'conversation',
                'question': command_text,
                'answer': response,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat()
            })
        else:
            await self.modules['speech'].speak("Não consegui obter uma resposta")

    async def _handle_status_command(self, command_text: str, confidence: float):
        """Handler para comando de status"""
        status_text = """
        Estou online e funcionando!
        • OpenClaude: conectado
        • Reconhecimento de voz: ativo
        • TTS: pronto para falar
        • Sistema: operacional
        """
        await self.modules['speech'].speak(status_text)

    async def _handle_help_command(self, command_text: str, confidence: float):
        """Handler para comando de ajuda"""
        help_text = """
        Posso ajudar com:
        • 'captura tela' ou 'tira print' - tira um screenshot
        • Qualquer pergunta - converso com você usando OpenClaude
        • 'status' ou 'como tá' - verifica meu status
        • 'para' - encerra o sistema
        """
        await self.modules['speech'].speak(help_text)

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
                self.modules['hearing'].start(),
                # self.modules['vision'].start_monitoring(),  # Temporariamente desativado
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
            if hasattr(module, 'stop'):
                await module.stop()
            elif hasattr(module, 'shutdown'):
                await module.shutdown()

        logger.info("Aether Sensory System encerrado.")

async def main():
    """Função principal"""
    aether = AetherSensorySystem()
    await aether.run()

if __name__ == "__main__":
    asyncio.run(main())