"""
Sistema de Audição do Aether
Wake word "Aether" + reconhecimento de comandos básicos
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class VoiceListener:
    """Ouve por wake word "Aether" e processa comandos de voz"""

    def __init__(self, config_path=None):
        self.wake_word = "aether"
        self.listening_active = False
        self.energy_threshold = 4000  # Sensibilidade do microfone
        self.pause_threshold = 0.8  # Segundos de silêncio para fim de fala
        self.phrase_time_limit = 5  # Tempo máximo de uma frase

        # Callbacks
        self.on_command_detected: Optional[Callable] = None
        self.on_wake_word_detected: Optional[Callable] = None

        # Estado
        self.last_wake_word_time = 0
        self.wake_word_cooldown = 2  # Segundos entre ativações

        logger.info("VoiceListener inicializado (wake word: 'Aether')")

    async def start_listening(self):
        """Inicia escuta contínua por wake word"""
        self.listening_active = True
        logger.info("Escuta por wake word iniciada")

        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = self.energy_threshold
            self.recognizer.pause_threshold = self.pause_threshold
            self.recognizer.dynamic_energy_threshold = True

            with sr.Microphone() as source:
                logger.info("Microfone configurado")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("Ruído ambiente ajustado")

                while self.listening_active:
                    try:
                        # Ouvir continuamente
                        audio = await asyncio.to_thread(
                            self.recognizer.listen,
                            source,
                            timeout=None,
                            phrase_time_limit=self.phrase_time_limit
                        )

                        # Tentar reconhecer
                        text = await self._recognize_speech(audio)

                        if text:
                            await self._process_audio_text(text)

                    except sr.WaitTimeoutError:
                        # Timeout normal, continuar ouvindo
                        continue
                    except Exception as e:
                        logger.error(f"Erro na escuta: {e}")
                        await asyncio.sleep(1)

        except ImportError as e:
            logger.error(f"SpeechRecognition não instalado: {e}")
            self.listening_active = False
        except Exception as e:
            logger.error(f"Erro fatal no VoiceListener: {e}")
            self.listening_active = False

    async def _recognize_speech(self, audio):
        """Reconhece fala usando SpeechRecognition (Google Web API)"""
        try:
            import speech_recognition as sr

            # Tentar reconhecer com Google Web Speech API
            text = await asyncio.to_thread(
                self.recognizer.recognize_google,
                audio,
                language="pt-BR"
            )

            logger.debug(f"Texto reconhecido: '{text}'")
            return text.lower()

        except sr.UnknownValueError:
            # Fala não entendida
            logger.debug("Fala não reconhecida")
            return None
        except sr.RequestError as e:
            logger.error(f"Erro na API de reconhecimento: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro no reconhecimento: {e}")
            return None

    async def _process_audio_text(self, text):
        """Processa texto reconhecido para wake word e comandos"""
        current_time = time.time()

        # Verificar wake word
        if self.wake_word in text:
            # Cooldown para evitar ativações múltiplas
            if current_time - self.last_wake_word_time < self.wake_word_cooldown:
                logger.debug("Wake word ignorada (cooldown)")
                return

            self.last_wake_word_time = current_time
            logger.info(f"Wake word detectada: '{self.wake_word}'")

            # Callback para wake word
            if self.on_wake_word_detected:
                await self.on_wake_word_detected()

            # Extrair comando (tudo depois do wake word)
            command_start = text.find(self.wake_word) + len(self.wake_word)
            command_text = text[command_start:].strip()

            if command_text:
                await self._process_command(command_text)
            else:
                logger.info("Wake word sem comando")

        else:
            # Texto sem wake word - pode ser comando se já estivermos "acordados"
            # (implementar estado "acordado" depois)
            logger.debug(f"Texto sem wake word: '{text}'")

    async def _process_command(self, command_text):
        """Processa um comando de voz"""
        logger.info(f"Comando processado: '{command_text}'")

        # Análise básica do comando
        confidence = self._calculate_confidence(command_text)
        command_type = self._classify_command(command_text)

        # Log do comando
        await self._log_command(command_text, confidence, command_type)

        # Callback para comando detectado
        if self.on_command_detected:
            await self.on_command_detected(command_text, confidence)

    def _calculate_confidence(self, text):
        """Calcula confiança no reconhecimento (simplificado)"""
        # Baseado em: comprimento, palavras conhecidas, etc.
        if len(text.split()) < 2:
            return 0.5  # Baixa confiança para comandos muito curtos

        # Palavras-chave que aumentam confiança
        confidence_keywords = ["tela", "print", "captura", "mostra", "olha", "foto"]
        text_lower = text.lower()

        confidence = 0.5  # Base
        for keyword in confidence_keywords:
            if keyword in text_lower:
                confidence += 0.1

        return min(confidence, 0.95)  # Máximo 95%

    def _classify_command(self, text):
        """Classifica o tipo de comando"""
        text_lower = text.lower()

        if any(word in text_lower for word in ["tela", "print", "screenshot", "foto", "captura", "mostra", "olha"]):
            return "screenshot"
        elif any(word in text_lower for word in ["para", "pare", "stop", "encerra"]):
            return "stop"
        elif any(word in text_lower for word in ["ajuda", "help", "comandos"]):
            return "help"
        elif any(word in text_lower for word in ["status", "como", "tá"]):
            return "status"
        else:
            return "unknown"

    async def _log_command(self, text, confidence, command_type):
        """Registra comando no log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": text,
            "confidence": confidence,
            "type": command_type,
            "wake_word": self.wake_word
        }

        # Salvar em arquivo (simplificado)
        try:
            from pathlib import Path
            log_dir = Path("data/audio_logs")
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / "commands.jsonl"
            import json
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            logger.debug(f"Comando registrado: {command_type} ({confidence:.2f})")

        except Exception as e:
            logger.error(f"Erro ao registrar comando: {e}")

    async def test_microphone(self):
        """Testa o microfone e reconhecimento básico"""
        logger.info("Testando microfone...")

        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                print("🎤 Fale algo (teste de 3 segundos)...")
                recognizer.adjust_for_ambient_noise(source, duration=1)

                try:
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
                    text = recognizer.recognize_google(audio, language="pt-BR")

                    print(f"✅ Reconhecido: '{text}'")
                    return True

                except sr.UnknownValueError:
                    print("❌ Não entendi o que você disse")
                    return False
                except sr.RequestError as e:
                    print(f"❌ Erro na API: {e}")
                    return False

        except Exception as e:
            print(f"❌ Erro no teste: {e}")
            return False

    async def shutdown(self):
        """Encerra a escuta"""
        self.listening_active = False
        logger.info("VoiceListener encerrado")