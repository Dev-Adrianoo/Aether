"""
Testes para LearningHandler.
"""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.brain.handlers.learning_handler import LearningHandler
from src.learning.learning_manager import LearningManager


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace_tmp():
    path = Path.cwd() / "data" / "test_tmp" / f"learning_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def handler(workspace_tmp):
    speak = AsyncMock()
    lm = LearningManager(workspace_tmp)
    h = LearningHandler(speak=speak, learning_manager=lm)
    return h, speak, lm


# ---------------------------------------------------------------------------
# handle_learn_alias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_learn_alias_sem_alias_fala_instrucao(handler):
    h, speak, _ = handler
    await h.handle_learn_alias("", "obsidian")
    speak.assert_awaited_once_with(
        "Não entendi o alias. Fala no formato: aprende que X significa Y."
    )


@pytest.mark.asyncio
async def test_learn_alias_sem_target_fala_instrucao(handler):
    h, speak, _ = handler
    await h.handle_learn_alias("abre meu vault", "")
    speak.assert_awaited_once_with(
        "Não entendi o alias. Fala no formato: aprende que X significa Y."
    )


@pytest.mark.asyncio
async def test_learn_alias_valido_seta_pending_e_pede_confirmacao(handler):
    h, speak, _ = handler
    await h.handle_learn_alias("abre vault", "abre obsidian")
    assert h.has_pending is True
    spoken = speak.await_args.args[0]
    assert "Quer que eu aprenda" in spoken
    assert "abre vault" in spoken
    assert "abre obsidian" in spoken


# ---------------------------------------------------------------------------
# handle_learn_preference
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_learn_preference_sem_key_fala_erro(handler):
    h, speak, _ = handler
    await h.handle_learn_preference("", True, "descricao")
    speak.assert_awaited_once_with("Não entendi qual preferência devo aprender.")


@pytest.mark.asyncio
async def test_learn_preference_valida_seta_pending_e_pede_confirmacao(handler):
    h, speak, _ = handler
    await h.handle_learn_preference("idioma", "pt-BR", "idioma preferido")
    assert h.has_pending is True
    spoken = speak.await_args.args[0]
    assert "preferência" in spoken
    assert "idioma" in spoken


# ---------------------------------------------------------------------------
# handle_forget_alias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forget_alias_sem_alias_fala_pedido(handler):
    h, speak, _ = handler
    await h.handle_forget_alias("")
    speak.assert_awaited_once_with("Qual alias devo esquecer?")


@pytest.mark.asyncio
async def test_forget_alias_encontrado_fala_esqueci(handler):
    h, speak, lm = handler
    lm.learn_alias("abre vault", "abre obsidian")
    await h.handle_forget_alias("abre vault")
    speak.assert_awaited_once_with("Esqueci esse alias.")


@pytest.mark.asyncio
async def test_forget_alias_nao_encontrado_fala_nao_encontrei(handler):
    h, speak, _ = handler
    await h.handle_forget_alias("alias inexistente")
    speak.assert_awaited_once_with("Não encontrei esse alias.")


# ---------------------------------------------------------------------------
# handle_list_learning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_learning_sem_nada_fala_vazio(handler):
    h, speak, _ = handler
    await h.handle_list_learning()
    speak.assert_awaited_once_with("Ainda não tenho aprendizados salvos.")


@pytest.mark.asyncio
async def test_list_learning_com_aliases_lista_ate_tres(handler):
    h, speak, lm = handler
    lm.learn_alias("alias um", "target um")
    lm.learn_alias("alias dois", "target dois")
    await h.handle_list_learning()
    spoken = speak.await_args.args[0]
    assert "Aliases:" in spoken
    assert "alias um" in spoken.lower() or "target um" in spoken.lower()


@pytest.mark.asyncio
async def test_list_learning_com_preferencia_lista(handler):
    h, speak, lm = handler
    lm.learn_preference("idioma", "pt-BR", "")
    await h.handle_list_learning()
    spoken = speak.await_args.args[0]
    assert "Preferências:" in spoken


# ---------------------------------------------------------------------------
# confirm_learning — sem pendente (guard)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_sem_pending_fala_nada_pendente(handler):
    h, speak, _ = handler
    await h.confirm_learning("sim")
    speak.assert_awaited_once_with("Não há nada pendente para confirmar.")


# ---------------------------------------------------------------------------
# confirm_learning — alias
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("resposta", ["sim", "pode", "claro", "confirma", "confirmo", "ok", "isso"])
async def test_confirm_alias_com_confirmacao_salva(resposta, handler):
    h, speak, lm = handler
    await h.handle_learn_alias("abre vault", "abre obsidian")
    speak.reset_mock()
    await h.confirm_learning(resposta)

    assert lm.resolve_alias("abre vault") == "abre obsidian"
    spoken = speak.await_args.args[0]
    assert "Aprendi" in spoken


@pytest.mark.asyncio
async def test_confirm_alias_com_negativa_nao_salva(handler):
    h, speak, lm = handler
    await h.handle_learn_alias("abre vault", "abre obsidian")
    speak.reset_mock()
    await h.confirm_learning("nao")

    assert lm.resolve_alias("abre vault") is None
    speak.assert_awaited_once_with("Tudo bem, não vou salvar esse aprendizado.")


# ---------------------------------------------------------------------------
# confirm_learning — preference
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_preference_com_confirmacao_salva(handler):
    h, speak, lm = handler
    await h.handle_learn_preference("idioma", "pt-BR", "idioma preferido")
    speak.reset_mock()
    await h.confirm_learning("sim")

    assert lm.get_preference("idioma") == "pt-BR"
    speak.assert_awaited_once_with("Preferência salva.")


@pytest.mark.asyncio
async def test_confirm_preference_com_negativa_nao_salva(handler):
    h, speak, lm = handler
    await h.handle_learn_preference("idioma", "pt-BR", "")
    speak.reset_mock()
    await h.confirm_learning("nao quero")

    assert lm.get_preference("idioma") is None
    speak.assert_awaited_once_with("Tudo bem, não vou salvar esse aprendizado.")


# ---------------------------------------------------------------------------
# has_pending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_pending_true_depois_de_learn_alias(handler):
    h, _, _ = handler
    assert h.has_pending is False
    await h.handle_learn_alias("x", "y")
    assert h.has_pending is True


@pytest.mark.asyncio
async def test_has_pending_false_depois_de_confirm(handler):
    h, _, _ = handler
    await h.handle_learn_alias("x", "y")
    await h.confirm_learning("sim")
    assert h.has_pending is False


@pytest.mark.asyncio
async def test_has_pending_false_depois_de_rejeitar(handler):
    h, _, _ = handler
    await h.handle_learn_alias("x", "y")
    await h.confirm_learning("nao")
    assert h.has_pending is False
