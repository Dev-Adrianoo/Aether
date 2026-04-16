"""
Interface e implementações para captura de áudio.
Seguindo Dependency Injection e Open/Closed Principle.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

class AudioCapture(ABC):
    """Interface para captura de áudio"""

    @abstractmethod
    async def capture_audio(self, duration: float) -> Optional[bytes]:
        """Captura áudio por determinado tempo"""
        pass

    @abstractmethod
    async def start_continuous_capture(self, callback):
        """Inicia captura contínua chamando callback com áudio"""
        pass

    @abstractmethod
    async def stop(self):
        """Para a captura de áudio"""
        pass

class SoundDeviceCapture(AudioCapture):
    """Implementação usando sounddevice"""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: int = None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.running = False

        if device is not None:
            logger.info(f"SoundDevice usando dispositivo {device}")

    async def capture_audio(self, duration: float) -> Optional[bytes]:
        """Captura áudio usando sounddevice e converte para WAV"""
        try:
            import sounddevice as sd
            import numpy as np
            import io
            import wave

            loop = asyncio.get_event_loop()
            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=np.int16,
                device=self.device
            )
            await loop.run_in_executor(None, sd.wait)

            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_data.tobytes())

            return buffer.getvalue()

        except asyncio.CancelledError:
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
            raise
        except ImportError:
            logger.error("sounddevice não instalado")
            return None
        except Exception as e:
            logger.error(f"Erro na captura com sounddevice: {e}")
            return None

    async def start_continuous_capture(self, callback):
        """Captura contínua em loop"""
        self.running = True

        while self.running:
            try:
                audio_bytes = await self.capture_audio(8.0)
                if audio_bytes and self.running:
                    await callback(audio_bytes)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de captura: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        """Para a captura"""
        self.running = False
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

class PyAudioCapture(AudioCapture):
    """Implementação usando PyAudio (fallback)"""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.running = False

    async def capture_audio(self, duration: float) -> Optional[bytes]:
        """Captura áudio usando PyAudio"""
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                audio = recognizer.listen(source, timeout=duration, phrase_time_limit=duration)

                # Converter para bytes
                return audio.get_wav_data()

        except ImportError:
            logger.error("speech_recognition não instalado")
            return None
        except Exception as e:
            logger.error(f"Erro na captura com PyAudio: {e}")
            return None

    async def start_continuous_capture(self, callback):
        """Captura contínua com PyAudio"""
        self.running = True

        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)

                while self.running:
                    try:
                        audio = recognizer.listen(source, timeout=None, phrase_time_limit=5)
                        audio_bytes = audio.get_wav_data()

                        if audio_bytes and self.running:
                            await callback(audio_bytes)

                    except Exception as e:
                        logger.error(f"Erro na captura: {e}")
                        await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Erro na inicialização do PyAudio: {e}")
            self.running = False

    async def stop(self):
        """Para a captura"""
        self.running = False

class AudioCaptureFactory:
    """Factory para criar instâncias de captura de áudio"""

    @staticmethod
    def create_capture(method: str = "auto", **kwargs) -> AudioCapture:
        """
        Cria instância de captura de áudio.

        Args:
            method: "sounddevice", "pyaudio", ou "auto" (tenta sounddevice primeiro)
            **kwargs: Parâmetros para o construtor
        """
        if method == "sounddevice":
            return SoundDeviceCapture(**kwargs)
        elif method == "pyaudio":
            return PyAudioCapture(**kwargs)
        else:  # auto
            try:
                import sounddevice
                return SoundDeviceCapture(**kwargs)
            except ImportError:
                try:
                    import speech_recognition
                    return PyAudioCapture(**kwargs)
                except ImportError:
                    raise RuntimeError("Nenhum backend de áudio disponível")