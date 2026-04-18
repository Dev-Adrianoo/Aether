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
        self.requested_device = device
        self.energy_threshold = energy_threshold  # 0 = auto-calibrar no início
        self.running = False
        self._configure_input_device()

        if device is not None:
            logger.info(f"SoundDevice usando dispositivo {self.device}")

    def _configure_input_device(self):
        """Valida dispositivo/taxa e ajusta para uma combinacao suportada."""
        try:
            import sounddevice as sd
        except ImportError:
            return

        try:
            sd.check_input_settings(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype="int16",
            )
            return
        except Exception as original_error:
            logger.warning(
                "Configuracao de audio invalida "
                f"(device={self.device}, sample_rate={self.sample_rate}, channels={self.channels}): {original_error}"
            )

        if self.device is not None:
            try:
                info = sd.query_devices(self.device)
                fallback_rate = int(float(info.get("default_samplerate", self.sample_rate)))
                sd.check_input_settings(
                    device=self.device,
                    channels=self.channels,
                    samplerate=fallback_rate,
                    dtype="int16",
                )
                logger.warning(
                    f"Dispositivo {self.device} nao aceita {self.sample_rate}Hz; usando {fallback_rate}Hz."
                )
                self.sample_rate = fallback_rate
                return
            except Exception as device_error:
                logger.warning(
                    f"Dispositivo de audio {self.device} indisponivel/incompativel ({device_error}); "
                    "tentando selecao dinamica."
                )

        try:
            sd.check_input_settings(
                device=None,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype="int16",
            )
            self.device = None
        except Exception as default_error:
            logger.warning(
                f"Dispositivo padrao nao aceita {self.sample_rate}Hz ({default_error}); tentando taxa padrao."
            )
            try:
                default_input = sd.default.device[0]
                info = sd.query_devices(default_input)
                fallback_rate = int(float(info.get("default_samplerate", self.sample_rate)))
                sd.check_input_settings(
                    device=None,
                    channels=self.channels,
                    samplerate=fallback_rate,
                    dtype="int16",
                )
                self.device = None
                self.sample_rate = fallback_rate
            except Exception as final_error:
                logger.error(f"Nenhuma configuracao de entrada de audio valida encontrada: {final_error}")

    def _input_stream_candidates(self, sd):
        """Gera candidatos de microfone para alternar entre Quest, USB e padrao."""
        candidates = []

        def add(device, sample_rate):
            key = (device, int(sample_rate) if sample_rate else None)
            if key not in candidates:
                candidates.append(key)

        if self.device is not None:
            add(self.device, self.sample_rate)
        elif self.requested_device is None:
            add(None, self.sample_rate)

        if self.device is not None:
            try:
                info = sd.query_devices(self.device)
                add(self.device, info.get("default_samplerate", self.sample_rate))
            except Exception:
                pass

        try:
            devices = sd.query_devices()
        except Exception:
            devices = []

        ranked = []
        for idx, info in enumerate(devices):
            try:
                if info.get("max_input_channels", 0) <= 0:
                    continue
                name = str(info.get("name", "")).lower()
                if any(token in name for token in ("usb audio", "quest", "oculus", "headset microphone")):
                    rank = 0
                else:
                    rank = 1
                ranked.append((rank, idx, info))
            except AttributeError:
                continue

        for _, idx, info in sorted(ranked):
            add(idx, info.get("default_samplerate", self.sample_rate))

        add(None, self.sample_rate)

        try:
            default_input = sd.default.device[0]
            if default_input is not None and default_input >= 0:
                info = sd.query_devices(default_input)
                add(default_input, info.get("default_samplerate", self.sample_rate))
        except Exception:
            pass

        return candidates

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

    def _make_queue_stream(self, chunk_samples: int):
        """Abre um InputStream contínuo e retorna (stream, queue)."""
        import sounddevice as sd
        import queue as q_mod
        import numpy as np

        audio_q: q_mod.Queue = q_mod.Queue()

        def _cb(indata, frames, time_info, status):
            audio_q.put(indata.copy())

        last_error = None
        for device, sample_rate in self._input_stream_candidates(sd):
            try:
                sample_rate = int(float(sample_rate or self.sample_rate))
                stream = sd.InputStream(
                    samplerate=sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    device=device,
                    blocksize=chunk_samples,
                    callback=_cb,
                )
                if device != self.device or sample_rate != self.sample_rate:
                    logger.warning(
                        f"Audio input alternado para device={device}, sample_rate={sample_rate}."
                    )
                self.device = device
                self.sample_rate = sample_rate
                return stream, audio_q
            except Exception as e:
                last_error = e
                logger.warning(f"Falha ao abrir audio input device={device}, sample_rate={sample_rate}: {e}")

        raise last_error or RuntimeError("Nenhum dispositivo de entrada de audio disponivel")

    async def calibrate(self, duration: float = 1.0) -> float:
        """
        Mede ruído ambiente com InputStream e define energy_threshold.
        Deve ser chamado antes de start_continuous_capture.
        """
        try:
            import numpy as np

            CHUNK = int(0.1 * self.sample_rate)
            n_chunks = max(1, int(duration / 0.1))
            loop = asyncio.get_event_loop()

            print("Calibrando microfone (1s de silêncio)...")
            stream, audio_q = self._make_queue_stream(CHUNK)
            chunks = []
            with stream:
                for _ in range(n_chunks):
                    chunk = await loop.run_in_executor(None, lambda: audio_q.get(timeout=2.0))
                    chunks.append(chunk)

            combined = np.concatenate(chunks, axis=0)
            ambient_rms = float(np.sqrt(np.mean(combined.astype(np.float64) ** 2)))
            self.energy_threshold = max(ambient_rms * 4, 200.0)
            print(f"Threshold definido: {self.energy_threshold:.0f} RMS (ambiente: {ambient_rms:.0f})")
            return self.energy_threshold

        except Exception as e:
            logger.warning(f"Calibração falhou ({e}), usando threshold padrão 150")
            self.energy_threshold = 150.0
            return self.energy_threshold

    async def capture_until_silence(
        self,
        silence_duration: float = 1.2,
        max_duration: float = 30.0,
    ) -> Optional[bytes]:
        """
        Captura áudio até detectar silêncio após fala (VAD por energia).
        Usa InputStream contínuo — sem abrir/fechar stream a cada chunk.
        """
        try:
            import numpy as np
            import io
            import wave

            CHUNK = int(0.1 * self.sample_rate)
            max_chunks = int(max_duration / 0.1)
            silence_needed = int(silence_duration / 0.1)
            min_speech_chunks = 2

            loop = asyncio.get_event_loop()
            audio_chunks: list = []
            speech_chunks = 0
            silence_count = 0

            stream, audio_q = self._make_queue_stream(CHUNK)
            with stream:
                for _ in range(max_chunks):
                    if not self.running:
                        break

                    chunk = await loop.run_in_executor(None, lambda: audio_q.get(timeout=2.0))
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

    @staticmethod
    def list_audio_devices() -> dict:
        """
        Lista todos os dispositivos de áudio de entrada (microfones) disponíveis.
        Retorna dicionário com {índice: nome} para dispositivos de entrada.

        Exemplo de uso: python -c "from src.voice.audio_capture import AudioCaptureFactory; print(AudioCaptureFactory.list_audio_devices())"
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = {}

            for i, device in enumerate(devices):
                if device.get('max_input_channels', 0) > 0:
                    input_devices[i] = {
                        'name': device['name'],
                        'input_channels': device.get('max_input_channels', 0),
                        'default_samplerate': device.get('default_samplerate', 'N/A'),
                        'hostapi': device.get('hostapi', 'N/A')
                    }

            return input_devices

        except ImportError:
            # Fallback para PyAudio
            try:
                import pyaudio
                p = pyaudio.PyAudio()
                input_devices = {}

                for i in range(p.get_device_count()):
                    device_info = p.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        input_devices[i] = {
                            'name': device_info['name'],
                            'input_channels': device_info.get('maxInputChannels', 0),
                            'default_samplerate': device_info.get('defaultSampleRate', 'N/A')
                        }

                p.terminate()
                return input_devices

            except ImportError:
                return {"error": "Nenhuma biblioteca de áudio disponível. Instale sounddevice ou pyaudio."}
        except Exception as e:
            return {"error": f"Erro ao listar dispositivos: {str(e)}"}
