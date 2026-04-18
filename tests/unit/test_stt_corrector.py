"""
Testes do corretor local de transcricao STT.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.voice.stt_corrector import STTCorrector


def test_corrects_brazilian_screenshot_command_misread():
    corrector = STTCorrector()

    result = corrector.apply(
        "vou tirar um print na minha tela direita agora e me falar o que tem nela"
    )

    assert result == "tira print na minha tela direita agora e me fala o que tem nela"


def test_does_not_rewrite_first_person_without_request_for_answer():
    corrector = STTCorrector()

    result = corrector.apply("vou tirar um print daqui a pouco")

    assert result == "vou tirar um print daqui a pouco"


def test_normalizes_colloquial_screen_phrases():
    corrector = STTCorrector()

    result = corrector.apply("dá uma olhada na tela da direita e me fala o que aparece")

    assert result == "olha na tela direita e me fala o que aparece"
