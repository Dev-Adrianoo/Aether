"""
Tests for TerminalHandler.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.brain.handlers.terminal_handler import TerminalHandler


# ---------------------------------------------------------------------------
# Sem openclaude
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_openclaude_fala_indisponivel():
    speak = AsyncMock()
    handler = TerminalHandler(speak=speak, openclaude=None)

    await handler.handle("abre o terminal")

    speak.assert_awaited_once_with("OpenClaude não está disponível.")


# ---------------------------------------------------------------------------
# Fechar / ocultar terminal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["fecha o terminal", "feche", "esconde", "oculta", "esconder"])
async def test_fechar_terminal_sucesso(text):
    speak = AsyncMock()
    oc = MagicMock()
    oc.hide_terminal.return_value = True
    handler = TerminalHandler(speak=speak, openclaude=oc)

    await handler.handle(text)

    oc.hide_terminal.assert_called_once()
    speak.assert_awaited_once_with("Terminal fechado.")


@pytest.mark.asyncio
async def test_fechar_terminal_sem_terminal_aberto():
    speak = AsyncMock()
    oc = MagicMock()
    oc.hide_terminal.return_value = False
    handler = TerminalHandler(speak=speak, openclaude=oc)

    await handler.handle("fecha o terminal")

    speak.assert_awaited_once_with("Não tenho nenhum terminal aberto.")


# ---------------------------------------------------------------------------
# Abrir terminal — escolha de shell
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_abre_powershell_por_padrao():
    speak = AsyncMock()
    oc = MagicMock()
    oc.is_terminal_open.return_value = False
    handler = TerminalHandler(speak=speak, openclaude=oc)

    await handler.handle("abre o terminal")

    oc.show_terminal.assert_called_once_with(shell="powershell")
    speak.assert_awaited_once_with("Terminal aberto em powershell.")


@pytest.mark.asyncio
async def test_abre_cmd_quando_solicitado():
    speak = AsyncMock()
    oc = MagicMock()
    oc.is_terminal_open.return_value = False
    handler = TerminalHandler(speak=speak, openclaude=oc)

    await handler.handle("abre o cmd")

    oc.show_terminal.assert_called_once_with(shell="cmd")
    speak.assert_awaited_once_with("Terminal aberto em cmd.")


# ---------------------------------------------------------------------------
# Terminal ja aberto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_terminal_ja_aberto_fala_mensagem_correta():
    speak = AsyncMock()
    oc = MagicMock()
    oc.is_terminal_open.return_value = True
    handler = TerminalHandler(speak=speak, openclaude=oc)

    await handler.handle("abre o terminal")

    oc.show_terminal.assert_called_once_with(shell="powershell")
    speak.assert_awaited_once_with("Terminal já está aberto.")


@pytest.mark.asyncio
async def test_terminal_proc_encerrado_nao_considera_aberto():
    speak = AsyncMock()
    oc = MagicMock()
    oc.is_terminal_open.return_value = False
    handler = TerminalHandler(speak=speak, openclaude=oc)

    await handler.handle("abre o terminal")

    speak.assert_awaited_once_with("Terminal aberto em powershell.")
