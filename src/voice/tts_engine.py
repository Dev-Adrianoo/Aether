"""
Sistema de Text-to-Speech (TTS) do Iris
Suporta pyttsx3 (offline) e edge-tts (online)
Usa configuração do config.py
"""

import asyncio
import logging
from typing import Optional
from config import config

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

logger = logging.getLogger(__name__)

class TTSEngine:
    """Motor de síntese de voz para feedback auditivo"""

    def __init__(self, use_edge_tts=None):
        # Usar configuração do sistema se não especificado
        if use_edge_tts is None:
            self.use_edge_tts = config.tts.engine == 'edge-tts'
        else:
            self.use_edge_tts = use_edge_tts

        self.engine = None
        self.voice = None
        self.voice_name = config.tts.voice
        self.rate = config.tts.rate

        logger.info(f"TTSEngine inicializado: engine={config.tts.engine}, voice={self.voice_name}, rate={self.rate}")

    async def initialize(self):
        """Inicializa o motor de TTS"""
        try:
            if self.use_edge_tts:
                # edge-tts para qualidade melhor (online)
                if edge_tts is None:
                    raise ImportError("edge_tts não instalado")
                self.engine = edge_tts
                logger.info("Edge-TTS configurado (online)")
            else:
                # pyttsx3 para uso offline
                if pyttsx3 is None:
                    raise ImportError("pyttsx3 não instalado")
                self.engine = pyttsx3.init()
                self.engine.setProperty('rate', self.rate)  # Velocidade da configuração
                self.engine.setProperty('volume', 0.9)  # Volume alto

                # Configurar voz em português se disponível
                voices = self.engine.getProperty('voices')
                for voice in voices:
                    if 'portuguese' in voice.name.lower() or 'pt' in voice.id.lower():
                        self.engine.setProperty('voice', voice.id)
                        self.voice = voice
                        break

                logger.info("pyttsx3 configurado (offline)")

            return True

        except ImportError as e:
            logger.error(f"Biblioteca TTS não instalada: {e}")
            logger.info("Instale: pip install pyttsx3 edge-tts")
            return False
        except Exception as e:
            logger.error(f"Erro na inicialização do TTS: {e}")
            return False

    async def speak(self, text: str, wait: bool = True):
        """Fala o texto fornecido"""
        if not text or not text.strip():
            return

        # Limpar emojis para log no Windows
        import re
        text_for_log = re.sub(r'[^\w\s.,!?;:()\-—]', '', text)
        logger.info(f"Falando: '{text_for_log[:50]}...'")

        try:
            if self.use_edge_tts and self.engine:
                voice_map = {
                    'pt-br': 'pt-BR-FranciscaNeural',
                    'pt-pt': 'pt-PT-RaquelNeural',
                    'en-us': 'en-US-AriaNeural',
                    'en-gb': 'en-GB-SoniaNeural'
                }
                voice = voice_map.get(self.voice_name, 'pt-BR-FranciscaNeural')

                communicate = edge_tts.Communicate(text, voice)

                audio_data = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data.extend(chunk["data"])

                if audio_data:
                    await self._play_audio(audio_data)
                    logger.debug(f"Áudio reproduzido: {len(audio_data)} bytes, voz: {voice}")
                else:
                    logger.warning("Nenhum áudio gerado pelo edge-tts")

                print(f"🔊 Iris diz: {text}")

            elif self.engine:
                # pyttsx3 (síncrono)
                self.engine.say(text)
                if wait:
                    self.engine.runAndWait()
                else:
                    self.engine.startLoop(False)
                    self.engine.iterate()
                    self.engine.endLoop()

                print(f"🔊 Iris diz: {text}")
            else:
                # Fallback: apenas imprimir
                print(f"🔊 [TTS] {text}")

        except Exception as e:
            logger.error(f"Erro ao falar texto: {e}")
            print(f"🔊 [Fallback] {text}")

    async def test_voice(self, test_count: int = 2):
        """Testa a voz do sistema múltiplas vezes para verificar bloqueio"""
        test_phrases = [
            "Olá, eu sou o Iris.",
            "Sistema de visão e audição ativo.",
            "Pronto para ajudar no desenvolvimento.",
            "Teste de voz concluído com sucesso."
        ]

        logger.info(f"Iniciando teste de voz ({test_count} ciclos)...")

        for cycle in range(test_count):
            logger.info(f"Ciclo de teste {cycle + 1}/{test_count}")
            for phrase in test_phrases:
                await self.speak(phrase)
                await asyncio.sleep(1.0)  # Dar tempo entre frases

            if cycle < test_count - 1:
                await asyncio.sleep(2.0)  # Pausa entre ciclos

        logger.info(f"Teste de voz concluído ({test_count} ciclos completos)")

    async def test_single_phrase_multiple_times(self, phrase: str = "Teste de voz", times: int = 3):
        """Testa falar a mesma frase múltiplas vezes para verificar bloqueio"""
        logger.info(f"Testando frase '{phrase}' {times} vezes...")

        for i in range(times):
            logger.info(f"Tentativa {i + 1}/{times}")
            await self.speak(f"{phrase} - tentativa {i + 1}")
            await asyncio.sleep(1.5)

        logger.info("Teste de repetição concluído")

    async def _play_audio(self, audio_data: bytearray):
        """Reproduz áudio usando pyaudio (fallback para pygame ou apenas log)"""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmpfile:
            tmp_path = tmpfile.name
            tmpfile.write(audio_data)

        try:
            try:
                import pydub
                from pydub.playback import play

                # Carregar e reproduzir
                audio = pydub.AudioSegment.from_mp3(tmp_path)
                play(audio)
                logger.debug("Áudio reproduzido com pydub")

            except ImportError:
                try:
                    import pygame

                    pygame.mixer.init()
                    pygame.mixer.music.load(tmp_path)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy():
                        import asyncio
                        await asyncio.sleep(0.1)

                    logger.debug("Áudio reproduzido com pygame")

                except ImportError:
                    try:
                        import playsound
                        playsound.playsound(tmp_path)
                        logger.debug("Áudio reproduzido com playsound")

                    except ImportError:
                        logger.warning("Nenhuma biblioteca de reprodução disponível")
                        logger.info("Instale: pip install pydub pygame playsound")
                        logger.debug(f"Áudio gerado mas não reproduzido: {len(audio_data)} bytes")

        except Exception as e:
            logger.error(f"Erro ao reproduzir áudio: {e}")
            # Fallback silencioso - pelo menos o texto é impresso
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass

    async def shutdown(self):
        if self.engine and not self.use_edge_tts:
            self.engine.stop()

        logger.info("TTSEngine encerrado")