"""
Sistema de configuração do Lumina
Usa variáveis de ambiente com fallback para valores padrão
"""

import os
from pathlib import Path
from typing import List, Optional
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
    bin_path: Path  # path do executável openclaude CLI

@dataclass
class GroqConfig:
    """Configurações da API Groq (STT Whisper)"""
    api_key: str

@dataclass
class ObsidianConfig:
    """Configurações do Obsidian"""
    vault_path: Path       # vault geral (ObsidianManager / logs)
    dev_vault_path: Path   # vault de desenvolvimento (MAPA.md, contexto LLM)
    log_folder: str
    obsidian_exe_candidates: List[Path]

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
    tesseract_cmd: str

@dataclass
class LoggingConfig:
    """Configurações de logging"""
    level: str
    log_file: Path
    to_console: bool

class LuminaConfig:
    """Configuração principal do Lumina"""

    def __init__(self, env_file: Optional[str] = None):
        """Inicializa configuração, carregando de .env se disponível"""
        if env_file:
            self._load_env_file(env_file)
        else:
            self._load_env_file('.env')

        self.audio = self._load_audio_config()
        self.openclaude = self._load_openclaude_config()
        self.groq = self._load_groq_config()
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
                print(f"[OK] Config carregado de {env_file}")
            except ImportError:
                print("[WARN] python-dotenv nao instalado. Use: pip install python-dotenv")
        else:
            print(f"[WARN] Arquivo {env_file} nao encontrado. Usando valores padrao.")

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

    def _get_env_paths(self, key: str, default: list[Path]) -> list[Path]:
        value = os.getenv(key, '').strip()
        if not value:
            return default
        return [Path(part.strip()) for part in value.split(';') if part.strip()]

    @property
    def user_name(self) -> str:
        return self._get_env('LUMINA_USER_NAME', 'Mestre')

    @property
    def sentinel_timeout(self) -> float:
        return float(self._get_env('OPENCLAUDE_SENTINEL_TIMEOUT', '300'))

    def _load_audio_config(self) -> AudioConfig:
        device_raw = os.getenv('AUDIO_DEVICE_INDEX')
        return AudioConfig(
            wake_word=self._get_env('LUMINA_WAKE_WORD', 'lumina'),
            sample_rate=self._get_env_int('AUDIO_SAMPLE_RATE', 16000),
            channels=self._get_env_int('LUMINA_AUDIO_CHANNELS', 1),
            phrase_time_limit=self._get_env_int('LUMINA_PHRASE_TIME_LIMIT', 15),
            energy_threshold=self._get_env_int('LUMINA_ENERGY_THRESHOLD', 4000),
            pause_threshold=0.8,
            device_index=int(device_raw) if device_raw is not None else None
        )

    def _load_openclaude_config(self) -> OpenClaudeConfig:
        default_bin = Path(os.getenv('APPDATA', '')) / 'npm' / 'node_modules' / '@gitlawb' / 'openclaude' / 'dist' / 'cli.mjs'
        return OpenClaudeConfig(
            api_key=self._get_env('OPENCLAUDE_API_KEY', ''),
            base_url=self._get_env('OPENCLAUDE_BASE_URL', 'https://api.deepseek.com/v1'),
            model=self._get_env('OPENCLAUDE_MODEL', 'deepseek-chat'),
            bin_path=Path(self._get_env('OPENCLAUDE_BIN', str(default_bin)))
        )

    def _load_groq_config(self) -> GroqConfig:
        return GroqConfig(
            api_key=self._get_env('GROQ_API_KEY', '')
        )

    def _load_obsidian_config(self) -> ObsidianConfig:
        vault_path = Path(self._get_env('OBSIDIAN_VAULT_PATH', str(Path.home() / 'Documents' / 'Obsidian Vault')))
        dev_vault_path = Path(self._get_env('OBSIDIAN_DEV_VAULT', str(vault_path)))
        local_app_data = Path(os.getenv('LOCALAPPDATA', ''))
        program_files = Path(os.getenv('ProgramFiles', 'C:/Program Files'))
        obsidian_candidates = self._get_env_paths('OBSIDIAN_EXE_CANDIDATES', [
            local_app_data / 'Programs' / 'Obsidian' / 'Obsidian.exe',
            local_app_data / 'Obsidian' / 'Obsidian.exe',
            program_files / 'Obsidian' / 'Obsidian.exe',
        ])
        return ObsidianConfig(
            vault_path=vault_path,
            dev_vault_path=dev_vault_path,
            log_folder=self._get_env('OBSIDIAN_LOG_FOLDER', 'Lumina_Logs'),
            obsidian_exe_candidates=obsidian_candidates
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
            save_path=save_path,
            tesseract_cmd=self._get_env('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe'),
        )

    def _load_logging_config(self) -> LoggingConfig:
        log_file = Path(self._get_env('LOG_FILE', 'lumina.log'))
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
            print("[ERRO] Erros de configuracao:")
            for error in errors:
                print(f"   - {error}")
            return False

        print("[OK] Configuracoes validadas com sucesso")
        return True

    def print_summary(self):
        """Exibe resumo das configurações"""
        print("\n" + "="*50)
        print("CONFIGURACAO LUMINA - RESUMO")
        print("="*50)

        print(f"\nAudio:")
        print(f"   Wake Word: {self.audio.wake_word}")
        print(f"   Sample Rate: {self.audio.sample_rate}Hz")
        print(f"   Canais: {self.audio.channels}")

        print(f"\nOpenClaude:")
        print(f"   API Key: {'ok' if self.openclaude.api_key else 'AUSENTE'}")
        print(f"   Model: {self.openclaude.model}")

        print(f"\nObsidian:")
        print(f"   Vault: {self.obsidian.vault_path}")
        print(f"   Existe: {'ok' if self.obsidian.vault_path.exists() else 'NAO ENCONTRADO'}")

        print(f"\nTTS:")
        print(f"   Engine: {self.tts.engine}")
        print(f"   Voz: {self.tts.voice}")

        print(f"\nVisao:")
        print(f"   Qualidade: {self.vision.quality}%")
        print(f"   Formato: {self.vision.format}")

        print(f"\nLogging:")
        print(f"   Nivel: {self.logging.level}")
        print(f"   Arquivo: {self.logging.log_file}")
        print("="*50 + "\n")

config = LuminaConfig()
