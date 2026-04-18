import shutil
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.brain.intent_router import IntentRouter


@pytest.fixture
def workspace_tmp():
    path = Path.cwd() / "data" / "test_tmp" / f"router_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_router(base_path: Path, classify_response: str = '{"type":"conversation"}'):
    speak = AsyncMock()
    integration = Mock()
    integration.classify = AsyncMock(return_value=classify_response)
    integration.ask_question = AsyncMock(return_value="ok")
    stt_corrector = Mock()
    stt_corrector.apply.side_effect = lambda text: text

    router = IntentRouter(
        speak=speak,
        modules={"integration": integration},
        stt_corrector=stt_corrector,
        base_dir=base_path,
        screenshot_handler=AsyncMock(),
        save_correction_fn=AsyncMock(),
        log_fn=AsyncMock(),
    )
    return router, speak, integration


@pytest.mark.asyncio
async def test_pending_screenshot_confirmation_routes_without_llm(workspace_tmp: Path):
    router, speak, integration = make_router(workspace_tmp)
    router._handle_screenshot_command = AsyncMock()

    await router._speak("Não consigo ver a tela. Quer que eu tire um print?")
    await router.route("yes, i accept", 0.8)

    router._handle_screenshot_command.assert_awaited_once()
    integration.classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_long_sentence_does_not_count_as_pending_confirmation(workspace_tmp: Path):
    router, _, integration = make_router(workspace_tmp)
    router._handle_screenshot_command = AsyncMock()

    await router._speak("Não consigo ver a tela. Quer que eu tire um print?")
    await router.route("sim mas antes me explica o que aconteceu", 0.8)

    router._handle_screenshot_command.assert_not_awaited()
    integration.classify.assert_awaited_once()


@pytest.mark.asyncio
async def test_screenshot_request_with_stt_first_person_misread_routes_directly(workspace_tmp: Path):
    router, _, integration = make_router(workspace_tmp, '{"type":"conversation"}')
    router._handle_screenshot_command = AsyncMock()

    await router.route("vou tirar um print na minha tela direita agora e me falar o que tem nela", 0.8)

    router._handle_screenshot_command.assert_awaited_once_with("direita", 0.8)
    integration.classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_learn_alias_requires_confirmation(workspace_tmp: Path):
    router, speak, _ = make_router(
        workspace_tmp,
        '{"type":"learn_alias","alias":"abre meu vault dev","target":"abre obsidian"}',
    )

    await router.route("aprende que abre meu vault dev significa abre obsidian", 0.8)

    assert router._learning_handler.has_pending
    assert "Quer que eu aprenda" in speak.await_args.args[0]


@pytest.mark.asyncio
async def test_confirm_learning_saves_alias(workspace_tmp: Path):
    router, _, _ = make_router(
        workspace_tmp,
        '{"type":"learn_alias","alias":"abre meu vault dev","target":"abre obsidian"}',
    )

    await router.route("aprende que abre meu vault dev significa abre obsidian", 0.8)
    await router.route("sim", 0.8)

    assert router._learning.resolve_alias("abre meu vault dev") == "abre obsidian"


@pytest.mark.asyncio
async def test_alias_is_applied_before_classification(workspace_tmp: Path):
    router, _, integration = make_router(workspace_tmp, '{"type":"conversation"}')
    router._learning.learn_alias("abre meu vault dev", "abre obsidian")

    await router.route("abre meu vault dev", 0.8)

    prompt = integration.classify.await_args.args[0]
    assert 'Texto recebido: "abre obsidian"' in prompt


@pytest.mark.asyncio
async def test_reject_learning_does_not_save_alias(workspace_tmp: Path):
    router, _, _ = make_router(
        workspace_tmp,
        '{"type":"learn_alias","alias":"abre meu vault dev","target":"abre obsidian"}',
    )

    await router.route("aprende que abre meu vault dev significa abre obsidian", 0.8)
    await router.route("nao", 0.8)

    assert router._learning.resolve_alias("abre meu vault dev") is None
