import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from src.learning.learning_manager import LearningManager


@pytest.fixture
def workspace_tmp():
    path = Path.cwd() / "data" / "test_tmp" / f"learning_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_learn_and_resolve_alias(workspace_tmp: Path):
    manager = LearningManager(workspace_tmp)

    manager.learn_alias("abre meu vault dev", "abre obsidian")

    assert manager.resolve_alias("abre meu vault dev") == "abre obsidian"
    assert manager.resolve_alias("ÁBRE   meu   váult dev") == "abre obsidian"


def test_forget_alias(workspace_tmp: Path):
    manager = LearningManager(workspace_tmp)
    manager.learn_alias("testar lumina", "anota testar lumina")

    assert manager.forget_alias("testar lumina") is True
    assert manager.resolve_alias("testar lumina") is None
    assert manager.forget_alias("testar lumina") is False


def test_list_aliases(workspace_tmp: Path):
    manager = LearningManager(workspace_tmp)
    manager.learn_alias("abre docs", "abre obsidian")

    aliases = manager.list_aliases()

    assert aliases == [{"phrase": "abre docs", "target": "abre obsidian"}]


def test_learn_and_read_preference(workspace_tmp: Path):
    manager = LearningManager(workspace_tmp)

    manager.learn_preference(
        "screenshot right auto analyze",
        True,
        "Ao pedir print da tela direita, analisar junto.",
    )

    assert manager.get_preference("screenshot-right-auto-analyze") is True
    assert manager.get_preference("missing", default=False) is False
    assert manager.list_preferences()[0]["key"] == "screenshot_right_auto_analyze"
