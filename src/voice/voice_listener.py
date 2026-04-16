"""
VoiceListener refatorado seguindo SOLID principles.
Dependency Injection, Single Responsibility, Open/Closed.
"""

import asyncio
import logging
from typing import Optional, Callable

from .audio_capture import AudioCaptureFactory, AudioCapture
from .speech_recognizer import SpeechRecognizer
from .command_processor import CommandProcessor

logger = logging.getLogger(__name__)

class VoiceListener:
    """
    Sistema completo de escuta por voz.
    Composto por: Captura → Reconhecimento → Processamento
    """

    def __init__(
        self,
        audio_capture: Optional[AudioCapture] = None,
        speech_recognizer: Optional[SpeechRecognizer] = None,
        command_processor: Optional[CommandProcessor] = None,
        config: Optional[dict] = None
    ):
        # Dependency Injection ou criação padrão
        self.audio_capture = audio_capture or AudioCaptureFactory.create_capture(
            method="sounddevice",
            device=47,        # WDM-KS USB mic (RMS ~270 com voz)
            sample_rate=44100  # MME device 1 retorna zeros; WDM-KS exige 44100Hz
        )
        self.speech_recognizer = speech_recognizer or SpeechRecognizer(language="pt-BR")
        self.command_processor = command_processor or CommandProcessor(wake_word="aether")

        # Estado
        self.running = False
        self.config = config or {}

        # Feedback
        self._print = self.config.get('print_feedback', True)

    async def start(self):
        """Inicia o sistema de escuta"""
        if self.running:
            logger.warning("Sistema já está rodando")
            return

        self.running = True
        logger.info("Sistema de voz iniciado")

        if self._print:
            print("\n" + "="*50)
            print("🎤 AETHER VOICE SYSTEM")
            print("="*50)
            print("Diga 'Aether' seguido de comando:")
            print("  • 'Aether, captura tela'")
            print("  • 'Aether, mostra print'")
            print("  • 'Aether, para'")
            print("="*50 + "\n")

        # Iniciar captura contínua
        await self.audio_capture.start_continuous_capture(self._process_audio_callback)

    async def _process_audio_callback(self, audio_bytes: bytes):
        """Callback chamado quando áudio é capturado"""
        if not self.running:
            return

        try:
            if self._print:
                print("🔍 Processando áudio...", end='\r')

            # Reconhecer fala
            text = await self.speech_recognizer.recognize(audio_bytes)

            if text:
                if self._print:
                    print(f"📝 Reconhecido: '{text}'")

                # Processar texto
                wake_detected = await self.command_processor.process_text(text)

                if wake_detected and self._print:
                    print("🔔 Wake word detectada!")

            elif self._print:
                print("❌ Nada reconhecido", end='\r')

        except Exception as e:
            logger.error(f"Erro no processamento de áudio: {e}")
            if self._print:
                print(f"⚠️  Erro: {e}")

    def register_command_handler(self, command_type: str, handler: Callable):
        """Registra handler para tipo de comando"""
        self.command_processor.register_command(command_type, handler)

    def set_wake_callback(self, callback: Callable):
        """Define callback para wake word"""
        self.command_processor.on_wake_detected = callback

    def set_command_callback(self, callback: Callable):
        """Define callback para comandos"""
        self.command_processor.on_command_detected = callback

    async def stop(self):
        """Para o sistema de escuta"""
        self.running = False
        await self.audio_capture.stop()
        logger.info("Sistema de voz encerrado")

        if self._print:
            print("\n👋 Sistema de voz encerrado")

    async def test_microphone(self) -> bool:
        """Testa o microfone e reconhecimento"""
        print("🎤 Testando microfone...")

        try:
            # Capturar 3 segundos de áudio
            audio_bytes = await self.audio_capture.capture_audio(3.0)

            if not audio_bytes:
                print("❌ Falha na captura de áudio")
                return False

            print("✅ Áudio capturado. Reconhecendo...")

            # Reconhecer
            text = await self.speech_recognizer.recognize(audio_bytes)

            if text:
                print(f"✅ Reconhecido: '{text}'")
                return True
            else:
                print("❌ Nada reconhecido")
                return False

        except Exception as e:
            print(f"❌ Erro no teste: {e}")
            return False