"""
Tests for CodeAgentHandler.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.brain.handlers.code_agent_handler import CodeAgentHandler
from src.actions.action_loader import UnknownTarget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handler(
    openclaude=None,
    dispatch_fn=None,
    learn_fn=None,
    conversation_fallback_fn=None,
    base_dir=None,
    tmp_path=None,
):
    speak = AsyncMock()
    bd = base_dir or (tmp_path if tmp_path else Path("/tmp/lumina-test"))
    return (
        CodeAgentHandler(
            speak=speak,
            openclaude=openclaude,
            base_dir=bd,
            dispatch_fn=dispatch_fn,
            learn_fn=learn_fn,
            conversation_fallback_fn=conversation_fallback_fn,
        ),
        speak,
    )


# ---------------------------------------------------------------------------
# handle_code_agent — sem openclaude
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_code_agent_sem_openclaude_fala_indisponivel():
    handler, speak = _make_handler(openclaude=None)

    await handler.handle_code_agent("cria um arquivo teste.py")

    speak.assert_awaited_once_with("OpenClaude não está disponível.")


# ---------------------------------------------------------------------------
# handle_code_agent — working_dir baseado em keywords
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_code_agent_keyword_lumina_usa_base_dir(tmp_path):
    oc = MagicMock()
    handler, speak = _make_handler(openclaude=oc, tmp_path=tmp_path)

    await handler.handle_code_agent("muda o codigo do lumina para logar mais")

    call_kwargs = oc.run_visible.call_args
    assert call_kwargs.kwargs["working_dir"] == str(tmp_path)


@pytest.mark.asyncio
async def test_handle_code_agent_sem_keyword_lumina_usa_documents(tmp_path):
    oc = MagicMock()
    handler, speak = _make_handler(openclaude=oc, tmp_path=tmp_path)

    await handler.handle_code_agent("cria um script para organizar fotos")

    call_kwargs = oc.run_visible.call_args
    expected = str(Path.home() / "Documents")
    assert call_kwargs.kwargs["working_dir"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("keyword", [
    "lumina", "voce mesmo", "em voce", "no seu codigo",
    "obsidian", "vault", "nova acao", "actions.yaml", "action_loader",
])
async def test_handle_code_agent_cada_keyword_detecta_self(keyword, tmp_path):
    oc = MagicMock()
    handler, speak = _make_handler(openclaude=oc, tmp_path=tmp_path)

    await handler.handle_code_agent(f"faz algo {keyword} agora")

    call_kwargs = oc.run_visible.call_args
    assert call_kwargs.kwargs["working_dir"] == str(tmp_path)


# ---------------------------------------------------------------------------
# handle_action — dispatch retorna string
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_action_dispatch_retorna_string_fala_resultado():
    dispatch = MagicMock(return_value="Abrindo chrome")
    handler, speak = _make_handler(dispatch_fn=dispatch)

    await handler.handle_action("abre o chrome", confidence=0.9)

    speak.assert_awaited_once_with("Abrindo chrome")


# ---------------------------------------------------------------------------
# handle_action — dispatch retorna UnknownTarget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_action_unknown_target_seta_pending_e_fala_pergunta():
    dispatch = MagicMock(return_value=UnknownTarget(action_id="spotify"))
    handler, speak = _make_handler(dispatch_fn=dispatch)

    assert handler.has_pending_learn is False

    await handler.handle_action("abre o spotify", confidence=0.9)

    assert handler.has_pending_learn is True
    speak.assert_awaited_once()
    msg = speak.call_args.args[0]
    assert "spotify" in msg.lower()
    assert "procure" in msg.lower() or "procura" in msg.lower() or "sistema" in msg.lower()


# ---------------------------------------------------------------------------
# handle_action — dispatch retorna None/falsy -> conversation_fallback_fn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_action_dispatch_retorna_none_chama_fallback():
    dispatch = MagicMock(return_value=None)
    fallback = AsyncMock()
    handler, speak = _make_handler(dispatch_fn=dispatch, conversation_fallback_fn=fallback)

    await handler.handle_action("abre o blorg", confidence=0.7)

    fallback.assert_awaited_once_with("abre o blorg", 0.7)
    speak.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_action_dispatch_retorna_none_sem_fallback_nao_fala():
    dispatch = MagicMock(return_value=None)
    handler, speak = _make_handler(dispatch_fn=dispatch)

    await handler.handle_action("abre o blorg", confidence=0.7)

    speak.assert_not_awaited()


# ---------------------------------------------------------------------------
# has_pending_learn — True depois de unknown app, False antes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_pending_learn_false_antes_de_unknown():
    handler, _ = _make_handler()
    assert handler.has_pending_learn is False


@pytest.mark.asyncio
async def test_has_pending_learn_true_depois_de_unknown():
    dispatch = MagicMock(return_value=UnknownTarget(action_id="notion"))
    handler, _ = _make_handler(dispatch_fn=dispatch)

    await handler.handle_action("abre o notion", confidence=0.8)

    assert handler.has_pending_learn is True


# ---------------------------------------------------------------------------
# confirm_learn_app — negativa
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_learn_app_negativa_fala_tudo_bem():
    dispatch = MagicMock(return_value=UnknownTarget(action_id="figma"))
    handler, speak = _make_handler(dispatch_fn=dispatch)
    await handler.handle_action("abre figma", confidence=0.8)
    speak.reset_mock()

    await handler.confirm_learn_app("nao obrigado", confidence=0.9)

    speak.assert_awaited_once_with("Tudo bem, fica pra depois.")


# ---------------------------------------------------------------------------
# confirm_learn_app — sem openclaude
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_learn_app_sem_openclaude_fala_indisponivel():
    dispatch = MagicMock(return_value=UnknownTarget(action_id="figma"))
    handler, speak = _make_handler(dispatch_fn=dispatch, openclaude=None)
    await handler.handle_action("abre figma", confidence=0.8)
    speak.reset_mock()

    await handler.confirm_learn_app("sim, pode procurar", confidence=0.9)

    speak.assert_awaited_once_with("OpenClaude não está disponível.")


# ---------------------------------------------------------------------------
# _monitor_openclaude_sentinel — timeout: sem TTS, apenas log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_sentinel_timeout_sem_tts(tmp_path):
    handler, speak = _make_handler(tmp_path=tmp_path)
    handler._openclaude_run_id = 1

    sentinel_dir = tmp_path / "data" / "run"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    # sentinel nao existe — poll vai dar timeout

    import types
    fake_config = types.SimpleNamespace(sentinel_timeout=0.05)
    fake_config_mod = types.SimpleNamespace(config=fake_config)

    with patch.dict("sys.modules", {"config": fake_config_mod}):
        await handler._monitor_openclaude_sentinel(run_id=1)

    speak.assert_not_awaited()


# ---------------------------------------------------------------------------
# _monitor_openclaude_sentinel — run_id antigo: ignora
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_sentinel_run_id_antigo_ignora(tmp_path):
    handler, speak = _make_handler(tmp_path=tmp_path)
    handler._openclaude_run_id = 5  # run atual eh 5

    sentinel_dir = tmp_path / "data" / "run"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinel_dir / "done.sentinel"

    import types
    fake_config = types.SimpleNamespace(sentinel_timeout=5.0)
    fake_config_mod = types.SimpleNamespace(config=fake_config)

    async def _create_sentinel_soon():
        await asyncio.sleep(0.05)
        sentinel.write_text("done")

    asyncio.create_task(_create_sentinel_soon())

    with patch.dict("sys.modules", {"config": fake_config_mod}):
        await handler._monitor_openclaude_sentinel(run_id=1)  # run antigo = 1

    speak.assert_not_awaited()
    # sentinel deve ter sido deixado intacto (sem unlink, pois run_id nao bate)
    assert sentinel.exists()


# ---------------------------------------------------------------------------
# _monitor_openclaude_sentinel — sentinel presente e run_id atual: fala terminou
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_monitor_sentinel_run_id_atual_fala_terminou(tmp_path):
    handler, speak = _make_handler(tmp_path=tmp_path)
    handler._openclaude_run_id = 3

    sentinel_dir = tmp_path / "data" / "run"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    sentinel = sentinel_dir / "done.sentinel"

    import types
    fake_config = types.SimpleNamespace(sentinel_timeout=5.0)
    fake_config_mod = types.SimpleNamespace(config=fake_config)

    async def _create_sentinel_soon():
        await asyncio.sleep(0.05)
        sentinel.write_text("done")

    asyncio.create_task(_create_sentinel_soon())

    with patch.dict("sys.modules", {"config": fake_config_mod}):
        await handler._monitor_openclaude_sentinel(run_id=3)

    speak.assert_awaited_once_with("OpenClaude terminou. Confere o resultado no terminal.")
    assert not sentinel.exists()
