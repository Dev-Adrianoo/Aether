"""
Self-learning seguro e explicito.

Primeiro escopo:
- aliases de fala: "abre meu vault dev" -> "abre obsidian"
- preferencias simples: chave -> valor

Nada e executado diretamente aqui. O alias reescreve a fala para passar pelo
roteamento normal, mantendo Action Gate e handlers existentes.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PendingLearning:
    kind: str
    alias: str = ""
    target: str = ""
    key: str = ""
    value: Any = None
    description: str = ""


class LearningManager:
    def __init__(self, base_dir: Path):
        self._dir = base_dir / "src" / "learning"
        self._aliases_path = self._dir / "learned_aliases.yaml"
        self._preferences_path = self._dir / "learned_preferences.yaml"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self._aliases_path, {"aliases": {}})
        self._ensure_file(self._preferences_path, {"preferences": {}})

    def resolve_alias(self, command_text: str) -> Optional[str]:
        aliases = self._load(self._aliases_path).get("aliases", {})
        normalized = self.normalize(command_text)
        entry = aliases.get(normalized)
        if not entry:
            return None
        target = str(entry.get("target", "")).strip()
        return target or None

    def learn_alias(self, alias: str, target: str) -> None:
        alias_key = self.normalize(alias)
        if not alias_key or not target.strip():
            raise ValueError("Alias e target sao obrigatorios.")

        data = self._load(self._aliases_path)
        data.setdefault("aliases", {})[alias_key] = {
            "phrase": alias.strip(),
            "target": target.strip(),
            "learned_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save(self._aliases_path, data)
        logger.info("Alias aprendido: %s -> %s", alias, target)

    def forget_alias(self, alias: str) -> bool:
        alias_key = self.normalize(alias)
        data = self._load(self._aliases_path)
        aliases = data.setdefault("aliases", {})
        if alias_key not in aliases:
            return False
        del aliases[alias_key]
        self._save(self._aliases_path, data)
        return True

    def list_aliases(self) -> list[dict[str, str]]:
        aliases = self._load(self._aliases_path).get("aliases", {})
        return [
            {"phrase": str(entry.get("phrase", key)), "target": str(entry.get("target", ""))}
            for key, entry in aliases.items()
        ]

    def learn_preference(self, key: str, value: Any, description: str = "") -> None:
        normalized_key = self.normalize_key(key)
        if not normalized_key:
            raise ValueError("Chave de preferencia obrigatoria.")

        data = self._load(self._preferences_path)
        data.setdefault("preferences", {})[normalized_key] = {
            "value": value,
            "description": description.strip(),
            "learned_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save(self._preferences_path, data)
        logger.info("Preferencia aprendida: %s=%s", normalized_key, value)

    def get_preference(self, key: str, default: Any = None) -> Any:
        normalized_key = self.normalize_key(key)
        preferences = self._load(self._preferences_path).get("preferences", {})
        if normalized_key not in preferences:
            return default
        return preferences[normalized_key].get("value", default)

    def list_preferences(self) -> list[dict[str, Any]]:
        preferences = self._load(self._preferences_path).get("preferences", {})
        return [
            {
                "key": key,
                "value": entry.get("value"),
                "description": str(entry.get("description", "")),
            }
            for key, entry in preferences.items()
        ]

    @staticmethod
    def normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFD", (text or "").lower())
        without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return " ".join(without_accents.split())

    @classmethod
    def normalize_key(cls, key: str) -> str:
        return cls.normalize(key).replace(" ", "_").replace("-", "_")

    def _ensure_file(self, path: Path, default: dict) -> None:
        if not path.exists():
            self._save(path, default)

    def _load(self, path: Path) -> dict:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save(self, path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=True)
