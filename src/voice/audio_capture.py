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

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: int = None, energy_threshold: float = 0.0):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.energy_threshold = energy_threshold  # 0 = auto-calibrar no início
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

    async def calibrate(self, duration: float = 1.0) -> float:
        """
        Mede ruído ambiente e define energy_threshold automaticamente.
        Deve ser chamado antes de start_continuous_capture.
        """
        try:
            import sounddevice as sd_mod
            import numpy as np

            samples = int(duration * self.sample_rate)
            loop = asyncio.get_event_loop()

            def record():
                data = sd_mod.rec(
                    samples,
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=np.int16,
                    device=self.device,
                )
                sd_mod.wait()
                return data

            print("Calibrando microfone (1s de silêncio)...")
            data = await loop.run_in_executor(None, record)
            ambient_rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
            self.energy_threshold = max(ambient_rms * 2.5, 80.0)
            print(f"Threshold definido: {self.energy_threshold:.0f} RMS (ambiente: {ambient_rms:.0f})")
            return self.energy_threshold

        except Exception as e:
            logger.warning(f"Calibração falhou ({e}), usando threshold padrão 200")
            self.energy_threshold = 200.0
            return self.energy_threshold

    async def capture_until_silence(
        self,
        silence_duration: float = 1.5,
        max_duration: float = 30.0,
    ) -> Optional[bytes]:
        """
        Captura áudio até detectar silêncio após fala (VAD por energia).
        Retorna None se nenhuma fala for detectada no período.
        """
        try:
            import sounddevice as sd_mod
            import numpy as np
            import io
            import wave

            CHUNK = 0.1  # 100ms por chunk
            chunk_samples = int(CHUNK * self.sample_rate)
            max_chunks = int(max_duration / CHUNK)
            silence_needed = int(silence_duration / CHUNK)
            min_speech_chunks = 3  # ignora sons < 300ms (cliques, ruídos)

            loop = asyncio.get_event_loop()
            audio_chunks: list = []
            speech_chunks = 0
            silence_count = 0

            def record_chunk():
                data = sd_mod.rec(
                    chunk_samples,
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=np.int16,
                    device=self.device,
                )
                sd_mod.wait()
                return data

            for _ in range(max_chunks):
                if not self.running:
                    break

                chunk = await loop.run_in_executor(None, record_chunk)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
                logger.debug(f"VAD RMS: {rms:.1f} / threshold: {self.energy_threshold:.1f}")

                if rms >= self.energy_threshold:
                    audio_chunks.append(chunk)
                    speech_chunks += 1
                    silence_count = 0
                elif speech_chunks >= min_speech_chunks:
                    audio_chunks.append(chunk)
                    silence_count += 1
                    if silence_count >= silence_needed:
                        break
                elif speech_chunks > 0:
                    # fala muito curta — provavelmente ruído, descarta
                    audio_chunks.clear()
                    speech_chunks = 0

            if not audio_chunks:
                return None

            combined = np.concatenate(audio_chunks, axis=0)
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(combined.tobytes())
            return buffer.getvalue()

        except asyncio.CancelledError:
            try:
                import sounddevice as sd_mod
                sd_mod.stop()
            except Exception:
                pass
            raise
        except Exception as e:
            logger.error(f"Erro na captura VAD: {e}")
            return None

    async def start_continuous_capture(self, callback):
        """Captura contínua usando VAD — grava até silêncio detectado"""
        self.running = True

        if self.energy_threshold == 0.0:
            await self.calibrate()

        while self.running:
            try:
                audio_bytes = await self.capture_until_silence()
                if audio_bytes and self.running:
                    await callback(audio_bytes)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop de captura: {e}")
                await asyncio.sleep(0.1)

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