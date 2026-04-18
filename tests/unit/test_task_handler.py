"""
Tests for TaskHandler.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.brain.handlers.task_handler import TaskHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handler(llm_response=None, write_task_fn=None):
    speak = AsyncMock()
    integration = AsyncMock()
    integration.ask_question = AsyncMock(return_value=llm_response)
    write_fn = write_task_fn or MagicMock()
    handler = TaskHandler(speak=speak, integration=integration, write_task_fn=write_fn)
    return handler, speak, integration, write_fn


# ---------------------------------------------------------------------------
# Keyword presente — extrai tarefa após keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("text,expected_task", [
    ("anota comprar leite", "comprar leite"),
    ("registre enviar relatório", "enviar relatório"),
    ("lembra ligar pro cliente", "ligar pro cliente"),
])
async def test_keyword_extrai_tarefa_e_chama_write(text, expected_task):
    handler, speak, integration, write_fn = _make_handler(llm_response="Anotei!")

    await handler.handle(text)

    write_fn.assert_called_once_with(expected_task)
    speak.assert_awaited_once_with("Anotei!")


# ---------------------------------------------------------------------------
# Sem keyword — trata command_text inteiro como tarefa
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_keyword_trata_texto_inteiro_como_tarefa():
    handler, speak, integration, write_fn = _make_handler(llm_response="Registrado.")

    await handler.handle("revisar o código amanhã")

    # task_text = command_text.lower() = "revisar o código amanhã" (não vazio)
    write_fn.assert_called_once_with("revisar o código amanhã")
    speak.assert_awaited_once_with("Registrado.")


# ---------------------------------------------------------------------------
# LLM retorna None — fala fallback "Anotado."
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_retorna_none_fala_anotado():
    handler, speak, integration, write_fn = _make_handler(llm_response=None)

    await handler.handle("anota estudar asyncio")

    write_fn.assert_called_once()
    speak.assert_awaited_once_with("Anotado.")


# ---------------------------------------------------------------------------
# Só keyword, sem conteúdo — fala pedido de esclarecimento
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["anota", "anota ", "registre", "lembra"])
async def test_so_keyword_sem_conteudo_pede_esclarecimento(text):
    handler, speak, integration, write_fn = _make_handler()

    await handler.handle(text)

    write_fn.assert_not_called()
    speak.assert_awaited_once_with("Qual é a tarefa que devo anotar?")


# ---------------------------------------------------------------------------
# write_task é chamado antes do ask_question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_task_chamado_antes_do_llm():
    call_order = []

    async def _speak(text):
        pass

    def _write(text):
        call_order.append("write")

    integration = AsyncMock()

    async def _ask(prompt, **kwargs):
        call_order.append("llm")
        return "Ok."

    integration.ask_question = _ask

    handler = TaskHandler(speak=_speak, integration=integration, write_task_fn=_write)
    await handler.handle("anota fazer deploy")

    assert call_order == ["write", "llm"]
