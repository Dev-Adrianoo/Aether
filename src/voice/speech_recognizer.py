"""
Reconhecimento de fala independente da captura de áudio.
Groq Whisper (primário, rápido e preciso) + Google Speech (fallback).
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SpeechRecognizer:

    def __init__(self, language: str = "pt-BR"):
        self.language = language
        self.language_code = language.split("-")[0].lower()
        from config import config
        self.backend = config.stt.backend
        self.local_model_name = config.stt.local_model
        self.local_device = config.stt.local_device
        self.local_compute_type = config.stt.local_compute_type
        self.local_cache_dir = config.stt.local_cache_dir
        self._local_model = None
        self._local_available = False
        self._local_cuda_failed = False
        self._groq_client = None
        self._sr_recognizer = None
        self._groq_available = False
        self._init_local_whisper()
        self._init_groq()

    def _init_local_whisper(self):
        if self.backend not in ("auto", "local", "faster-whisper"):
            return
        device = self.local_device
        compute_type = self.local_compute_type
        if device == "cuda" and not self._cuda_runtime_dlls_available():
            logger.warning("CUDA runtime incompleto para faster-whisper; usando CPU/int8.")
            print("[WARN] CUDA/cuDNN nao encontrados no PATH; STT local vai usar CPU/int8.")
            device = "cpu"
            compute_type = "int8"
            self.local_device = device
            self.local_compute_type = compute_type

        self._local_model = self._create_local_model(
            device,
            compute_type,
        )
        self._local_available = self._local_model is not None

    def _cuda_runtime_dlls_available(self) -> bool:
        # Injeta o bin\ do CUDA no PATH da sessão e deixa o faster-whisper validar
        cuda_root = None
        cuda_path_env = os.environ.get("CUDA_PATH", "").strip()
        if cuda_path_env:
            p = Path(cuda_path_env)
            if p.exists():
                cuda_root = p

        if cuda_root is None:
            toolkit = Path("C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA")
            if toolkit.exists():
                versions = sorted(toolkit.iterdir(), reverse=True)
                cuda_root = versions[0] if versions else None

        if cuda_root is None:
            return False

        bin_dir = cuda_root / "bin"
        if not bin_dir.exists():
            return False

        bin_str = str(bin_dir)
        if bin_str not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")
        print(f"[INFO] CUDA bin injetado no PATH: {bin_str}")
        return True

    def _create_local_model(self, device: str, compute_type: str):
        try:
            from faster_whisper import WhisperModel

            self.local_cache_dir.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("HF_HOME", str(self.local_cache_dir))
            os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(self.local_cache_dir / "hub"))

            model = WhisperModel(
                self.local_model_name,
                device=device,
                compute_type=compute_type,
            )
            logger.info(
                "faster-whisper local disponivel: model=%s device=%s compute=%s",
                self.local_model_name,
                device,
                compute_type,
            )
            print(f"[OK] STT local faster-whisper ativo ({self.local_model_name}/{device})")
            return model
        except ImportError:
            if self.backend in ("local", "faster-whisper"):
                print("[WARN] faster-whisper nao instalado; STT local indisponivel")
            logger.info("faster-whisper nao instalado")
        except Exception as e:
            logger.warning(f"faster-whisper indisponivel: {e}")
            if self.backend in ("local", "faster-whisper"):
                print(f"[WARN] STT local indisponivel: {e}")
        return None

    def _init_groq(self):
        if self.backend in ("local", "faster-whisper"):
            return
        try:
            from groq import Groq
            from config import config
            api_key = config.groq.api_key
            if api_key:
                self._groq_client = Groq(api_key=api_key)
                self._groq_available = True
                logger.info("Groq Whisper disponível")
            else:
                logger.warning("GROQ_API_KEY não configurada — usando Google Speech")
                print("[WARN] GROQ_API_KEY ausente no .env — STT caiu pro Google Speech")
        except ImportError:
            logger.warning("groq não instalado — usando Google Speech. Instale: pip install groq")
            print("[WARN] pacote groq não instalado — STT caiu pro Google Speech")

    async def recognize(self, audio_bytes: bytes) -> Optional[str]:
        if self._local_available:
            result = await self._recognize_local(audio_bytes)
            if result:
                return result
            logger.debug("Whisper local falhou — tentando fallback")

        if self._groq_available:
            result = await self._recognize_groq(audio_bytes)
            if result:
                return result
            logger.debug("Groq falhou — tentando Google Speech")

        return await self._recognize_google(audio_bytes)

    @staticmethod
    def _audio_rms(audio_bytes: bytes) -> float:
        """Calcula RMS médio do payload PCM de um WAV (descarta header de 44 bytes)."""
        import struct
        import math
        pcm = audio_bytes[44:]
        if len(pcm) < 2:
            return 0.0
        samples = struct.unpack_from(f"<{len(pcm)//2}h", pcm)
        return math.sqrt(sum(s * s for s in samples) / len(samples))

    async def _recognize_local(self, audio_bytes: bytes) -> Optional[str]:
        if self._audio_rms(audio_bytes) < 150:
            logger.debug("RMS muito baixo — descartando antes do Whisper local")
            return None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
                f.write(audio_bytes)

            def transcribe():
                kwargs = {
                    "language": self.language_code,
                    "beam_size": 5,
                    "vad_filter": False,
                    "condition_on_previous_text": False,
                    "initial_prompt": (
                        "Conversa em português brasileiro com uma assistente de voz chamada Lumina. "
                        "Saudações: 'Lumina, tá aí?', 'Lumina, você está aí?', 'Lumina, tô aqui'. "
                        "Comandos comuns: 'Lumina, tira print', 'tira print da tela direita', "
                        "'abre o terminal', 'abre o VS Code', 'abre o Obsidian', "
                        "'me fala o que tem na tela', 'anota uma tarefa', "
                        "'aprende que X significa Y', 'lista seus aprendizados', "
                        "'clique no botão Yes I accept', 'fecha o terminal'. "
                        "Fala informal: 'tá', 'tô', 'pra', 'né', 'tá bom', 'pode'."
                    ),
                }
                try:
                    segments, _ = self._local_model.transcribe(tmp_path, **kwargs)
                except TypeError:
                    kwargs.pop("initial_prompt", None)
                    segments, _ = self._local_model.transcribe(tmp_path, **kwargs)
                return " ".join(segment.text.strip() for segment in segments).strip()

            text = await asyncio.to_thread(transcribe)
            if text:
                logger.debug(f"Whisper local reconheceu: {text}")
                return text.lower()
            return None
        except Exception as e:
            if self._is_cuda_runtime_error(e):
                return await self._retry_local_on_cpu(audio_bytes, str(e))
            logger.warning(f"Whisper local erro: {e}")
            return None
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _is_cuda_runtime_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return any(token in message for token in ["cublas", "cudnn", "cuda", "cufft"])

    async def _retry_local_on_cpu(self, audio_bytes: bytes, reason: str) -> Optional[str]:
        if self._local_cuda_failed:
            return None

        self._local_cuda_failed = True
        logger.warning(f"Whisper local CUDA indisponivel ({reason}); tentando CPU/int8.")
        print("[WARN] STT local CUDA indisponivel; usando faster-whisper CPU/int8 nesta sessao.")

        self._local_model = await asyncio.to_thread(self._create_local_model, "cpu", "int8")
        if not self._local_model:
            self._local_available = False
            return None

        self.local_device = "cpu"
        self.local_compute_type = "int8"
        self._local_available = True
        return await self._recognize_local(audio_bytes)

    async def _recognize_groq(self, audio_bytes: bytes) -> Optional[str]:
        if self._audio_rms(audio_bytes) < 150:
            logger.debug("RMS muito baixo — descartando antes do Groq")
            return None
        try:
            # Groq espera um file-like com nome — usamos tupla (filename, bytes)
            result = await asyncio.to_thread(
                self._groq_client.audio.transcriptions.create,
                file=("audio.wav", audio_bytes),
                model="whisper-large-v3-turbo",
                language="pt",
                response_format="text",
            )
            text = result.strip() if isinstance(result, str) else result.text.strip()
            if text:
                logger.debug(f"Groq reconheceu: {text}")
                return text.lower()
            return None
        except Exception as e:
            logger.warning(f"Groq erro: {e}")
            return None

    async def _recognize_google(self, audio_bytes: bytes) -> Optional[str]:
        try:
            import speech_recognition as sr

            if self._sr_recognizer is None:
                self._sr_recognizer = sr.Recognizer()

            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    tmp_path = f.name
                    f.write(audio_bytes)

                with sr.AudioFile(tmp_path) as source:
                    audio = self._sr_recognizer.record(source)

                text = await asyncio.to_thread(
                    self._sr_recognizer.recognize_google,
                    audio,
                    language=self.language
                )
                logger.debug(f"Google reconheceu: {text}")
                return text.lower()

            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        except Exception as e:
            logger.debug(f"Google falhou: {e}")
            return None

    async def recognize_from_file(self, file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                audio_bytes = f.read()
            return await self.recognize(audio_bytes)
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return None
