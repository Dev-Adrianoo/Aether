"""
Utilitários de sistema que não são ações de voz despachadas pelo action_loader.
"""

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
