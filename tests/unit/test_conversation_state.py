"""
Tests for bounded short-term conversation state.
"""

from src.brain.conversation_state import ConversationState


def test_records_assistant_question_as_pending_screenshot():
    state = ConversationState()

    state.record_assistant("Não consigo ver a tela. Quer que eu tire um print?")

    assert state.pending_context == {"type": "screenshot"}


def test_consumes_affirmative_pending_screenshot():
    state = ConversationState()
    state.record_assistant("Quer que eu tire um print?")

    assert state.consume_pending_context("yes, i accept") == {"type": "screenshot"}
    assert state.pending_context is None


def test_long_affirmative_sentence_does_not_consume_pending_screenshot():
    state = ConversationState()
    state.record_assistant("Quer que eu tire um print?")

    assert state.consume_pending_context("sim mas antes me explica o que aconteceu") is None
    assert state.pending_context == {"type": "screenshot"}


def test_negative_reply_consumes_pending_context():
    state = ConversationState()
    state.record_assistant("Quer que eu tire um print?")

    assert state.consume_pending_context("nao agora") == {"type": "negative"}
    assert state.pending_context is None


def test_recent_turns_are_bounded():
    state = ConversationState(max_turns=2)

    state.remember_turn("u1", "a1")
    state.remember_turn("u2", "a2")
    state.remember_turn("u3", "a3")

    assert state.recent_turns == [
        {"user": "u2", "assistant": "a2"},
        {"user": "u3", "assistant": "a3"},
    ]
