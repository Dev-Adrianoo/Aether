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

        # Verificar se CMU Sphinx está disponível
        self._check_sphinx_availability()

    def _check_sphinx_availability(self):
        """Verifica se CMU Sphinx está disponível e configurado"""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()

            # Tentar importar para ver se está instalado
            import pocketsphinx

            # Verificar se modelo de idioma português está disponível
            # Nota: CMU Sphinx tem suporte limitado a português
            # Em produção, pode ser necessário baixar modelos específicos
            logger.info("✅ CMU Sphinx disponível para reconhecimento offline")
            self.sphinx_available = True

        except ImportError as e:
            logger.warning(f"CMU Sphinx não disponível: {e}")
            logger.info("Para reconhecimento offline, instale: pip install pocketsphinx")
            self.sphinx_available = False
        except Exception as e:
            logger.warning(f"Erro ao verificar CMU Sphinx: {e}")
            self.sphinx_available = False

    async def start_listening(self):
        """Inicia escuta contínua por wake word"""
        self.listening_active = True
        logger.info("Escuta por wake word iniciada")

        # Feedback inicial
        print("🎤 Sistema de áudio inicializado. Diga 'Aether' seguido de um comando.")
        print("   Exemplo: 'Aether, captura tela' ou 'Aether, mostra print'")

        # Primeiro tentar com sounddevice (alternativa)
        try:
            await self._start_listening_with_sounddevice()
        except Exception as e:
            logger.error(f"SoundDevice falhou: {e}")
            logger.info("Tentando fallback para speech_recognition...")

            # Fallback para speech_recognition tradicional
            try:
                import speech_recognition as sr
                self.recognizer = sr.Recognizer()
                self.recognizer.energy_threshold = self.energy_threshold
                self.recognizer.pause_threshold = self.pause_threshold
                self.recognizer.dynamic_energy_threshold = True

                with sr.Microphone() as source:
                    logger.info("Microfone configurado (PyAudio fallback)")
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    logger.info("Ruído ambiente ajustado")

                    while self.listening_active:
                        try:
                            # Feedback visual de escuta
                            print("👂 Ouvindo...", end='\r')

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

            except Exception as e:
                logger.error(f"Todos os métodos de áudio falharam: {e}")
                self.listening_active = False

    async def _start_listening_with_sounddevice(self):
        """Alternativa usando sounddevice para captura de áudio"""
        try:
            import sounddevice as sd
            import numpy as np
            import wave
            import tempfile
            import os

            # Configurações de áudio
            sample_rate = 16000  # Hz
            channels = 1
            dtype = np.int16

            logger.info(f"SoundDevice configurado: {sample_rate}Hz, {channels} canal(ais)")

            while self.listening_active:
                try:
                    # Feedback visual de escuta
                    print("👂 Ouvindo...", end='\r')

                    # Gravar áudio
                    duration = self.phrase_time_limit  # segundos
                    logger.debug(f"Gravando áudio por {duration}s...")

                    audio_data = sd.rec(
                        int(duration * sample_rate),
                        samplerate=sample_rate,
                        channels=channels,
                        dtype=dtype
                    )
                    sd.wait()  # Aguardar gravação terminar

                    # Feedback de gravação concluída
                    print("✅ Gravação concluída. Processando...", end='\r')

                    # Salvar em arquivo WAV temporário
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpfile:
                        tmp_path = tmpfile.name

                        # Salvar como WAV
                        import scipy.io.wavfile
                        scipy.io.wavfile.write(tmp_path, sample_rate, audio_data)

                        # Usar speech_recognition para processar o arquivo
                        import speech_recognition as sr
                        recognizer = sr.Recognizer()

                        with sr.AudioFile(tmp_path) as source:
                            audio = recognizer.record(source)
                            text = await self._recognize_speech(audio)

                            if text:
                                await self._process_audio_text(text)
                            else:
                                print("❌ Nenhum texto reconhecido", end='\r')

                    # Limpar arquivo temporário
                    os.unlink(tmp_path)

                except Exception as e:
                    logger.error(f"Erro na gravação com sounddevice: {e}")
                    print(f"⚠️  Erro: {e}")
                    await asyncio.sleep(1)

        except ImportError as e:
            logger.error(f"SoundDevice não disponível: {e}")
            self.listening_active = False
        except Exception as e:
            logger.error(f"Erro no sounddevice: {e}")
            self.listening_active = False

    async def _recognize_speech(self, audio):
        """Reconhece fala com fallback para CMU Sphinx (offline)"""
        try:
            import speech_recognition as sr

            # Criar recognizer se não existir (para modo sounddevice)
            if not hasattr(self, 'recognizer'):
                self.recognizer = sr.Recognizer()

            # PRIMEIRO: Tentar reconhecer com Google Web Speech API (online, melhor qualidade)
            try:
                text = await asyncio.to_thread(
                    self.recognizer.recognize_google,
                    audio,
                    language="pt-BR"
                )
                logger.debug(f"✅ Google Speech reconheceu: '{text}'")
                return text.lower()

            except sr.RequestError as e:
                # Erro de conexão com Google API - tentar CMU Sphinx (offline)
                logger.warning(f"Google Speech API falhou: {e}")

                if hasattr(self, 'sphinx_available') and self.sphinx_available:
                    logger.info("Tentando reconhecimento offline com CMU Sphinx...")
                    try:
                        # CMU Sphinx funciona offline, mas precisa do pacote de idioma
                        text = await asyncio.to_thread(
                            self.recognizer.recognize_sphinx,
                            audio,
                            language="pt-BR"
                        )
                        if text and text.strip():
                            logger.debug(f"✅ CMU Sphinx reconheceu: '{text}'")
                            return text.lower()
                        else:
                            logger.debug("CMU Sphinx não reconheceu fala")
                            return None

                    except Exception as sphinx_error:
                        logger.error(f"CMU Sphinx também falhou: {sphinx_error}")
                        return None
                else:
                    logger.info("CMU Sphinx não disponível para fallback offline")
                    return None

            except sr.UnknownValueError:
                # Fala não entendida por Google
                logger.debug("Google Speech não entendeu a fala")

                # Tentar CMU Sphinx como fallback se disponível
                if hasattr(self, 'sphinx_available') and self.sphinx_available:
                    try:
                        text = await asyncio.to_thread(
                            self.recognizer.recognize_sphinx,
                            audio,
                            language="pt-BR"
                        )
                        if text and text.strip():
                            logger.debug(f"✅ CMU Sphinx (fallback) reconheceu: '{text}'")
                            return text.lower()
                    except Exception:
                        pass  # Ignorar erro do Sphinx

                return None

        except Exception as e:
            logger.error(f"Erro geral no reconhecimento: {e}")
            return None

    async def _process_audio_text(self, text):
        """Processa texto reconhecido para wake word e comandos"""
        current_time = time.time()

        # Feedback visual do texto reconhecido
        print(f"📝 Reconhecido: '{text}'")

        # Verificar wake word
        if self.wake_word in text:
            # Cooldown para evitar ativações múltiplas
            if current_time - self.last_wake_word_time < self.wake_word_cooldown:
                logger.debug("Wake word ignorada (cooldown)")
                print("⏳ Wake word em cooldown...")
                return

            self.last_wake_word_time = current_time
            logger.info(f"Wake word detectada: '{self.wake_word}'")
            print(f"🔔 WAKE WORD DETECTADA: '{self.wake_word}'")

            # Callback para wake word
            if self.on_wake_word_detected:
                await self.on_wake_word_detected()

            # Extrair comando (tudo depois do wake word)
            command_start = text.find(self.wake_word) + len(self.wake_word)
            command_text = text[command_start:].strip()

            if command_text:
                print(f"🎯 Comando extraído: '{command_text}'")
                await self._process_command(command_text)
            else:
                logger.info("Wake word sem comando")
                print("❓ Wake word sem comando")

        else:
            # Texto sem wake word - pode ser comando se já estivermos "acordados"
            # (implementar estado "acordado" depois)
            logger.debug(f"Texto sem wake word: '{text}'")
            print(f"⚠️  Texto sem wake word: '{text}'")

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