"""
Loader do prompt de classificação de intenções via intents.yaml.
"""

from pathlib import Path
from typing import Optional

import yaml

_YAML_PATH = Path(__file__).parent / "intents.yaml"
_data: Optional[dict] = None


def _load() -> dict:
    global _data
    if _data is None:
        with open(_YAML_PATH, encoding="utf-8") as f:
            _data = yaml.safe_load(f)
    return _data


def build_prompt(command_text: str, last_recognized: str = "") -> str:
    """Retorna o prompt de classificação com os placeholders preenchidos."""
    return _load()["classification_prompt"].format(
        command_text=command_text,
        last_recognized=last_recognized,
    )


def classify_model() -> str:
    """Modelo a usar para a chamada de classificação (sempre leve)."""
    return _load().get("classify_model", "deepseek-chat")


def model_for_intent(intent_type: str, default: str = "deepseek-chat") -> str:
    """Retorna o modelo configurado para um tipo de intenção, ou o default."""
    routing = _load().get("model_routing", {})
    return routing.get(intent_type, default)
