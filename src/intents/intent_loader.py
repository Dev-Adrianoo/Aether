"""
Loader do prompt de classificação de intenções via intents.yaml.
"""

from pathlib import Path
from typing import Optional

import yaml

_YAML_PATH = Path(__file__).parent / "intents.yaml"
_template: Optional[str] = None


def _load() -> str:
    global _template
    if _template is None:
        with open(_YAML_PATH, encoding="utf-8") as f:
            _template = yaml.safe_load(f)["classification_prompt"]
    return _template


def build_prompt(command_text: str, last_recognized: str = "") -> str:
    """Retorna o prompt de classificação com os placeholders preenchidos."""
    return _load().format(
        command_text=command_text,
        last_recognized=last_recognized,
    )
