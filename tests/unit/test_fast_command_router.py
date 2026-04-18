"""
Tests for deterministic fast command routing.
"""

from src.brain.fast_command_router import FastCommand, FastCommandRouter


def test_routes_screenshot_right_without_llm():
    router = FastCommandRouter()

    assert router.route("tira print da tela direita e me fala o que tem") == FastCommand(
        type="screenshot",
        monitor=2,
    )


def test_routes_stt_first_person_misread_as_screenshot_when_user_asks_answer():
    router = FastCommandRouter()

    assert router.route("vou tirar um print na minha tela direita agora e me falar o que tem nela") == FastCommand(
        type="screenshot",
        monitor=2,
    )


def test_does_not_route_plain_first_person_narrative():
    router = FastCommandRouter()

    assert router.route("vou tirar um print daqui a pouco") is None


def test_routes_left_or_default_screenshot():
    router = FastCommandRouter()

    assert router.route("olha minha tela") == FastCommand(type="screenshot", monitor=1)


def test_ignores_non_fast_command():
    router = FastCommandRouter()

    assert router.route("abre o terminal") is None
