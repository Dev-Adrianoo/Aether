"""
Reconhecimento de fala independente da captura de áudio.
Single Responsibility Principle.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SpeechRecognizer:
    """Reconhece fala a partir de áudio"""

    def __init__(self, language: str = "pt-BR"):
        self.language = language
        self._recognizer = None

    async def recognize(self, audio_bytes: bytes) -> Optional[str]:
        """Reconhece fala a partir de bytes de áudio"""
        try:
            import speech_recognition as sr
            import tempfile
            import os

            # Criar recognizer se necessário
            if self._recognizer is None:
                self._recognizer = sr.Recognizer()

            # Salvar áudio em arquivo temporário
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpfile:
                tmp_path = tmpfile.name
                tmpfile.write(audio_bytes)

            try:
                # Processar arquivo
                with sr.AudioFile(tmp_path) as source:
                    audio = self._recognizer.record(source)

                    # Tentar Google Speech Recognition primeiro (online, melhor qualidade)
                    try:
                        text = await asyncio.to_thread(
                            self._recognizer.recognize_google,
                            audio,
                            language=self.language
                        )
                        logger.debug(f"Google reconheceu: {text}")
                        return text.lower()

                    except (sr.UnknownValueError, sr.RequestError) as google_error:
                        logger.debug(f"Google falhou: {google_error}")

                        # Fallback: CMU Sphinx (offline, pior qualidade mas funciona)
                        try:
                            text = await asyncio.to_thread(
                                self._recognizer.recognize_sphinx,
                                audio,
                                language=self.language
                            )
                            logger.debug(f"Sphinx reconheceu: {text}")
                            return text.lower()

                        except Exception as sphinx_error:
                            logger.debug(f"Sphinx também falhou: {sphinx_error}")
                            return None

            finally:
                # Limpar arquivo temporário
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        except sr.UnknownValueError:
            logger.debug("Fala não reconhecida por nenhum método")
            return None
        except ImportError:
            logger.error("speech_recognition não instalado")
            return None
        except Exception as e:
            logger.error(f"Erro no reconhecimento: {e}")
            return None

    async def recognize_from_file(self, file_path: str) -> Optional[str]:
        """Reconhece fala a partir de arquivo"""
        try:
            with open(file_path, 'rb') as f:
                audio_bytes = f.read()
            return await self.recognize(audio_bytes)
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return None