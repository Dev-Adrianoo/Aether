"""
Ações de sistema — abrir apps, URLs e processos.
Adicione novas ações aqui e registre em registry.py.
"""

import webbrowser
import subprocess
import logging

logger = logging.getLogger(__name__)


def open_youtube():
    webbrowser.open("https://www.youtube.com")
    logger.info("YouTube aberto")
    return "Abrindo YouTube"


def open_spotify():
    try:
        subprocess.Popen("spotify")
        return "Abrindo Spotify"
    except FileNotFoundError:
        webbrowser.open("https://open.spotify.com")
        return "Abrindo Spotify no navegador"


def open_vscode():
    try:
        subprocess.Popen("code")
        return "Abrindo VS Code"
    except FileNotFoundError:
        logger.warning("VS Code não encontrado no PATH")
        return "VS Code não encontrado"


def open_unity():
    try:
        subprocess.Popen("Unity Hub")
        return "Abrindo Unity Hub"
    except FileNotFoundError:
        logger.warning("Unity Hub não encontrado no PATH")
        return "Unity Hub não encontrado"
