"""
Tests for executable-intent safety policy.
"""

from src.brain.action_gate import ActionGate


def test_non_executable_intent_is_never_blocked():
    gate = ActionGate()

    assert gate.should_block("conversation", "abre o terminal") is False
    assert gate.should_block("screenshot", "vou tirar print e me fala") is False


def test_blocks_narrative_first_person_execution():
    gate = ActionGate()

    assert gate.should_block("terminal", "vou abrir o terminal agora") is True
    assert gate.should_block("code_agent", "estou pensando em criar um arquivo") is True


def test_allows_imperative_execution():
    gate = ActionGate()

    assert gate.should_block("terminal", "abre o terminal") is False
    assert gate.should_block("ui_action", "clique no botao yes i accept") is False


def test_allows_explicit_polite_execution_request():
    gate = ActionGate()

    assert gate.should_block("code_agent", "preciso que você crie um teste") is False
    assert gate.should_block("task", "quero que voce anote isso") is False


def test_normalizes_accents_for_policy():
    gate = ActionGate()

    assert gate.is_explicit_execution_request("faça isso") is True
    assert gate.should_block("terminal", "não precisa abrir terminal") is True
