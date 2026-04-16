"""
Registry de ações de voz.
Para adicionar uma nova ação:
  1. Implemente a função em system_actions.py (ou crie um novo módulo)
  2. Adicione uma entrada em ACTIONS com as palavras-chave que ativam a ação
"""

from typing import Callable, Dict, List, Optional, Tuple
from src.actions.system_actions import (
    open_youtube,
    open_spotify,
    open_vscode,
    open_unity,
    open_obsidian,
)

# Mapa: lista de palavras-chave → função que executa a ação
# A função deve retornar uma string com o feedback para o TTS
ACTIONS: Dict[str, Tuple[List[str], Callable[[], str]]] = {
    "youtube":  (["youtube"],              open_youtube),
    "spotify":  (["spotify", "música"],    open_spotify),
    "vscode":   (["vscode", "vs code", "código"],  open_vscode),
    "unity":    (["unity"],                open_unity),
    "obsidian": (["obsidian"],             open_obsidian),
}


def dispatch(command_text: str) -> Optional[str]:
    """
    Recebe texto do comando de voz e executa a ação correspondente.
    Retorna o feedback para TTS, ou None se nenhuma ação foi encontrada.
    """
    text_lower = command_text.lower()

    for _action_id, (keywords, handler) in ACTIONS.items():
        if any(kw in text_lower for kw in keywords):
            return handler()

    return None
