"""
Ações de sistema — abrir apps, URLs e processos.
Adicione novas ações aqui e registre em registry.py.
"""

import webbrowser
import subprocess
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TASKS_FILE = Path("tasks.md")


def write_claude_task(task_text: str) -> str:
    """Grava uma tarefa em tasks.md para o Claude Code ler."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [ ] {task_text}  <!-- {timestamp} -->\n"

    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("# Tarefas para Claude Code\n\n", encoding="utf-8")

    with open(TASKS_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    logger.info(f"Tarefa gravada: {task_text}")
    return f"Tarefa anotada: {task_text}"


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


def open_obsidian():
    vault_path = r"C:\Users\Adria\Documents\Documentation\Dev-lumina-agent"
    candidates = [
        Path(r"C:\Users\Adria\AppData\Local\Programs\Obsidian\Obsidian.exe"),
        Path(r"C:\Users\Adria\AppData\Local\Obsidian\Obsidian.exe"),
        Path(r"C:\Program Files\Obsidian\Obsidian.exe"),
    ]
    for obsidian_path in candidates:
        if obsidian_path.exists():
            subprocess.Popen([str(obsidian_path), vault_path])
            logger.info(f"Obsidian aberto com vault: {vault_path}")
            return "Abrindo Obsidian"
    logger.warning("Obsidian não encontrado em nenhum caminho conhecido")
    return "Obsidian não encontrado"
