"""
Persistencia simples de tarefas ditadas por voz.
Mantem anotacoes fora do registry de acoes executaveis.
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TASKS_FILE = Path("tasks.md")


def write_task(task_text: str) -> str:
    """Grava uma tarefa em tasks.md para leitura posterior."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [ ] {task_text}  <!-- {timestamp} -->\n"

    if not TASKS_FILE.exists():
        TASKS_FILE.write_text("# Tarefas da Lumina\n\n", encoding="utf-8")

    with open(TASKS_FILE, "a", encoding="utf-8") as f:
        f.write(entry)

    logger.info("Tarefa gravada: %s", task_text)
    return f"Tarefa anotada: {task_text}"
