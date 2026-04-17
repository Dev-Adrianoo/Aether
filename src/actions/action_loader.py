"""
Loader de ações dinâmicas via actions.yaml.
Adicionar ou editar ações não requer tocar em Python — só o YAML.
"""

import logging
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_YAML_PATH = Path(__file__).parent / "actions.yaml"
_actions_cache: Optional[dict] = None


def _load() -> dict:
    global _actions_cache
    if _actions_cache is None:
        with open(_YAML_PATH, encoding="utf-8") as f:
            _actions_cache = yaml.safe_load(f).get("actions", {})
    return _actions_cache


def reload():
    """Força releitura do YAML — útil após self-learning escrever nova entrada."""
    global _actions_cache
    _actions_cache = None


def dispatch(command_text: str) -> Optional[str]:
    """
    Recebe texto do comando e executa a ação correspondente.
    Retorna feedback para TTS, ou None se nenhuma ação foi encontrada.
    """
    text_lower = command_text.lower()
    actions = _load()

    for action_id, action in actions.items():
        keywords = action.get("keywords", [])
        if any(kw in text_lower for kw in keywords):
            return _execute(action_id, action)

    return None


def _execute(action_id: str, action: dict) -> str:
    action_type = action.get("type")
    target = action.get("target")

    if action_type == "url":
        webbrowser.open(target)
        logger.info(f"URL aberta: {target}")
        return f"Abrindo {action_id}"

    if action_type == "exe":
        if not target:
            logger.warning(f"Ação '{action_id}' sem target configurado")
            return f"{action_id} não está configurado ainda"
        try:
            subprocess.Popen(target)
            logger.info(f"App aberto: {target}")
            return f"Abrindo {action_id}"
        except FileNotFoundError:
            fallback = action.get("fallback_url")
            if fallback:
                webbrowser.open(fallback)
                return f"Abrindo {action_id} no navegador"
            return f"{action_id} não encontrado"

    if action_type == "exe_vault":
        from config import config
        vault_path = str(config.obsidian.dev_vault_path)
        candidates = [Path(c) for c in action.get("candidates", [])]
        for exe in candidates:
            if exe.exists():
                subprocess.Popen([str(exe), vault_path])
                logger.info(f"Obsidian aberto com vault: {vault_path}")
                return f"Abrindo {action_id}"
        logger.warning(f"Nenhum executável encontrado para '{action_id}'")
        return f"{action_id} não encontrado"

    logger.warning(f"Tipo desconhecido '{action_type}' para ação '{action_id}'")
    return f"Tipo de ação desconhecido: {action_type}"
