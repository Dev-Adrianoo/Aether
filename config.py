"""
Sistema de configuração do Aether Sensory System
Usa variáveis de ambiente com fallback para valores padrão
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

@dataclass
class AudioConfig:
    """Configurações de áudio"""
    wake_word: str
    sample_rate: int
    channels: int
    phrase_time_limit: int
    energy_threshold: int
    pause_threshold: float
    device_index: Optional[int]  # None = usar padrão do SO

@dataclass
class OpenClaudeConfig:
    """Configurações da API OpenClaude"""
    api_key: str
    base_url: str
    model: str

@dataclass
class ObsidianConfig:
    """Configurações do Obsidian"""
    vault_path: Path
    log_folder: str

@dataclass
class TTSConfig:
    """Configurações de Text-to-Speech"""
    engine: str
    voice: str
    rate: int

@dataclass
class VisionConfig:
    """Configurações de visão/screenshots"""
    quality: int
    format: str
    save_path: Path

@dataclass
class LoggingConfig:
    """Configurações de logging"""
    level: str
    log_file: Path
    to_console: bool

class AetherConfig:
    """Configuração principal do sistema Aether"""

    def __init__(self, env_file: Optional[str] = None):
        """Inicializa configuração, carregando de .env se disponível"""
        if env_file:
            self._load_env_file(env_file)
        else:
            self._load_env_file('.env')

        self.audio = self._load_audio_config()
        self.openclaude = self._load_openclaude_config()
        self.obsidian = self._load_obsidian_config()
        self.tts = self._load_tts_config()
        self.vision = self._load_vision_config()
        self.logging = self._load_logging_config()

    def _load_env_file(self, env_file: str):
        """Carrega variáveis de ambiente de um arquivo .env"""
        env_path = Path(env_file)
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                print(f"✅ Configurações carregadas de {env_file}")
            except ImportError:
                print("⚠️  python-dotenv não instalado. Use: pip install python-dotenv")
        else:
            print(f"⚠️  Arquivo {env_file} não encontrado. Usando valores padrão.")

    def _get_env(self, key: str, default: str) -> str:
        return os.getenv(key, default)

    def _get_env_int(self, key: str, default: int) -> int:
        value = os.getenv(key)
        return int(value) if value else default

    def _get_env_bool(self, key: str, default: bool) -> bool:
        value = os.getenv(key, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        return default

    def _load_audio_config(self) -> AudioConfig:
        device_raw = os.getenv('AUDIO_DEVICE_INDEX')
        return AudioConfig(
            wake_word=self._get_env('AETHER_WAKE_WORD', 'aether'),
            sample_rate=self._get_env_int('AUDIO_SAMPLE_RATE', 16000),
            channels=self._get_env_int('AETHER_AUDIO_CHANNELS', 1),
            phrase_time_limit=self._get_env_int('AETHER_PHRASE_TIME_LIMIT', 5),
            energy_threshold=self._get_env_int('AETHER_ENERGY_THRESHOLD', 4000),
            pause_threshold=0.8,
            device_index=int(device_raw) if device_raw is not None else 13
        )

    def _load_openclaude_config(self) -> OpenClaudeConfig:
        return OpenClaudeConfig(
            api_key=self._get_env('OPENCLAUDE_API_KEY', ''),
            base_url=self._get_env('OPENCLAUDE_BASE_URL', 'https://api.openclaude.ai/v1'),
            model=self._get_env('OPENCLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
        )

    def _load_obsidian_config(self) -> ObsidianConfig:
        vault_path = Path(self._get_env('OBSIDIAN_VAULT_PATH', 'C:/Users/Adria/Documents/Obsidian Vault'))
        return ObsidianConfig(
            vault_path=vault_path,
            log_folder=self._get_env('OBSIDIAN_LOG_FOLDER', 'Aether_Logs')
        )

    def _load_tts_config(self) -> TTSConfig:
        return TTSConfig(
            engine=self._get_env('TTS_ENGINE', 'pyttsx3'),
            voice=self._get_env('TTS_VOICE', 'pt-br'),
            rate=self._get_env_int('TTS_RATE', 150)
        )

    def _load_vision_config(self) -> VisionConfig:
        save_path = Path(self._get_env('SCREENSHOT_SAVE_PATH', './data/screenshots'))
        save_path.mkdir(parents=True, exist_ok=True)

        return VisionConfig(
            quality=self._get_env_int('SCREENSHOT_QUALITY', 85),
            format=self._get_env('SCREENSHOT_FORMAT', 'png'),
            save_path=save_path
        )

    def _load_logging_config(self) -> LoggingConfig:
        log_file = Path(self._get_env('LOG_FILE', 'aether.log'))
        return LoggingConfig(
            level=self._get_env('LOG_LEVEL', 'INFO'),
            log_file=log_file,
            to_console=self._get_env_bool('LOG_TO_CONSOLE', True)
        )

    def validate(self) -> bool:
        """Valida configurações críticas"""
        errors = []

        if not self.openclaude.api_key:
            errors.append("OPENCLAUDE_API_KEY não configurada")

        if not self.obsidian.vault_path.exists():
            errors.append(f"Obsidian vault não encontrado: {self.obsidian.vault_path}")

        if errors:
            print("❌ Erros de configuração:")
            for error in errors:
                print(f"   - {error}")
            return False

        print("✅ Configurações validadas com sucesso")
        return True

    def print_summary(self):
        """Exibe resumo das configurações"""
        print("\n" + "="*50)
        print("CONFIGURAÇÃO AETHER - RESUMO")
        print("="*50)

        print(f"\n🎤 Áudio:")
        print(f"   Wake Word: {self.audio.wake_word}")
        print(f"   Sample Rate: {self.audio.sample_rate}Hz")
        print(f"   Canais: {self.audio.channels}")

        print(f"\n🤖 OpenClaude:")
        print(f"   API Key: {'✅ Configurada' if self.openclaude.api_key else '❌ Não configurada'}")
        print(f"   Model: {self.openclaude.model}")

        print(f"\n📓 Obsidian:")
        print(f"   Vault: {self.obsidian.vault_path}")
        print(f"   Existe: {'✅' if self.obsidian.vault_path.exists() else '❌'}")

        print(f"\n🗣️  TTS:")
        print(f"   Engine: {self.tts.engine}")
        print(f"   Voz: {self.tts.voice}")

        print(f"\n👁️  Visão:")
        print(f"   Qualidade: {self.vision.quality}%")
        print(f"   Formato: {self.vision.format}")

        print(f"\n📊 Logging:")
        print(f"   Nível: {self.logging.level}")
        print(f"   Arquivo: {self.logging.log_file}")
        print("="*50 + "\n")

config = AetherConfig()