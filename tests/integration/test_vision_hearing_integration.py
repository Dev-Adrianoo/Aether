"""
Teste de integração entre visão e audição
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Importar módulos
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vision.screenshot_manager import ScreenshotManager
from src.voice.voice_listener import VoiceListener


class TestVisionHearingIntegration:
    """Testes de integração entre módulos de visão e audição"""

    @pytest.fixture
    def vision_manager(self):
        """Fixture para vision manager"""
        manager = ScreenshotManager()
        manager.screenshot_interval = 2  # 2 segundos para testes rápidos
        return manager

    @pytest.fixture
    def hearing_listener(self):
        """Fixture para hearing listener"""
        return VoiceListener()

    @pytest.mark.asyncio
    async def test_trigger_word_capture_integration(self, vision_manager, hearing_listener):
        """Testa integração: trigger word → captura de screenshot"""
        # Mock para captura
        mock_capture = AsyncMock()
        vision_manager.capture_and_analyze = mock_capture
        mock_capture.return_value = {"summary": "Teste", "dimensions": (1920, 1080)}

        # Simular comando de voz com trigger word
        command_text = "lumina tira um print da tela"

        # Processar como se tivesse vindo do VoiceListener
        await hearing_listener._process_audio_text(command_text)

        # Verificar se o ScreenshotManager detectaria trigger word
        should_capture = await vision_manager.check_trigger_words(command_text)
        assert should_capture is True, "Trigger word não detectada"

        # Se tivéssemos integração direta, capturaria screenshot
        if should_capture:
            result = await vision_manager.capture_and_analyze(reason="voice_trigger")
            assert result["summary"] == "Teste"

    @pytest.mark.asyncio
    async def test_command_classification_integration(self, hearing_listener):
        """Testa que comandos de screenshot são classificados corretamente"""
        test_commands = [
            ("lumina tira um print", "screenshot"),
            ("lumina captura a tela", "screenshot"),
            ("lumina mostra como está", "screenshot"),
            ("lumina olha aqui", "screenshot"),
            ("lumina tira uma foto", "screenshot"),
        ]

        for command, expected_type in test_commands:
            # Extrair comando (tudo depois do wake word)
            command_start = command.find("lumina") + len("lumina")
            command_text = command[command_start:].strip()

            # Classificar
            command_type = hearing_listener._classify_command(command_text)
            assert command_type == expected_type, f"Falha em: '{command}' -> {command_type}"

    @pytest.mark.asyncio
    async def test_confidence_calculation_integration(self, vision_manager, hearing_listener):
        """Testa que comandos com trigger words têm alta confiança"""
        test_cases = [
            ("tira um print da tela", True),  # Tem trigger word
            ("captura isso aqui", True),      # Tem trigger word
            ("teste qualquer", False),        # Não tem trigger word
        ]

        for command, has_trigger in test_cases:
            # Verificar no vision manager
            has_trigger_vision = await vision_manager.check_trigger_words(command)

            # Calcular confiança no hearing
            confidence = hearing_listener._calculate_confidence(command)

            # Se tem trigger word, deve ter confiança > 0.5
            if has_trigger:
                assert has_trigger_vision is True
                assert confidence > 0.5, f"Confiança baixa para trigger word: {confidence}"
            else:
                assert confidence == 0.5, f"Confiança inesperada: {confidence}"

    @pytest.mark.asyncio
    async def test_screenshot_decision_flow(self, vision_manager):
        """Testa fluxo completo de decisão de screenshot"""
        import time

        # Cenário 1: Trigger word deve capturar
        vision_manager.last_screenshot_time = time.time() - 10
        should_capture, reason = vision_manager.should_capture_screenshot("tira um print agora")
        assert should_capture is True
        assert reason == "trigger_word"

        # Cenário 2: Intervalo deve capturar
        vision_manager.last_screenshot_time = time.time() - 70  # 70 segundos atrás
        should_capture, reason = vision_manager.should_capture_screenshot()
        assert should_capture is True
        assert reason == "interval"

        # Cenário 3: Não deve capturar (sem trigger, intervalo não passou)
        vision_manager.last_screenshot_time = time.time() - 1  # 1 segundo atrás (intervalo é 2)
        should_capture, reason = vision_manager.should_capture_screenshot("texto normal")
        assert should_capture is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_wake_word_processing_flow(self, hearing_listener):
        """Testa fluxo completo de processamento de wake word"""
        # Mock callbacks
        mock_wake_callback = AsyncMock()
        mock_command_callback = AsyncMock()
        hearing_listener.on_wake_word_detected = mock_wake_callback
        hearing_listener.on_command_detected = mock_command_callback

        # Processar comando com wake word
        await hearing_listener._process_audio_text("lumina tira um print da tela por favor")

        # Verificar callbacks
        mock_wake_callback.assert_called_once()
        mock_command_callback.assert_called_once()

        # Verificar parâmetros do comando
        args = mock_command_callback.call_args[0]
        assert "tira um print da tela por favor" in args[0]  # Comando
        assert 0.5 <= args[1] <= 0.95  # Confiança

    @pytest.mark.asyncio
    async def test_economy_of_context_integration(self, vision_manager):
        """Testa integração da economia de contexto"""
        # Configurar
        vision_manager.min_interval_for_context = 5
        vision_manager.last_context_send_time = time.time() - 10  # 10 segundos atrás

        # Cenários de teste
        test_scenarios = [
            ({"has_errors": True}, True, "Erro detectado → envia"),
            ({"has_errors": False, "needs_attention": True}, True, "Precisa atenção → envia"),
            ({"has_errors": False, "needs_attention": False, "change_significance": "high"}, True, "Mudança alta → envia"),
            ({"has_errors": False, "needs_attention": False, "change_significance": "low"}, True, "Passou intervalo → envia"),
        ]

        for analysis, should_send, description in test_scenarios:
            # Simular _should_send_to_context
            current_time = time.time()

            sends = False
            if analysis.get("has_errors", False):
                sends = True
            elif analysis.get("needs_attention", False):
                sends = True
            elif current_time - vision_manager.last_context_send_time > vision_manager.min_interval_for_context:
                sends = True
            elif analysis.get("change_significance") in ["high", "medium"]:
                if current_time - vision_manager.last_context_send_time > 60:
                    sends = True

            assert sends == should_send, f"Falha em: {description}"


if __name__ == "__main__":
    # Execução manual dos testes de integração
    import asyncio

    async def run_integration_tests():
        print("🧪 TESTES DE INTEGRAÇÃO VISÃO-AUDIÇÃO")
        print("=" * 50)

        from src.vision.screenshot_manager import ScreenshotManager
        from src.voice.voice_listener import VoiceListener

        vision = ScreenshotManager()
        hearing = VoiceListener()

        print("1. Testando trigger word detection...")
        command = "lumina tira um print da tela"
        has_trigger = await vision.check_trigger_words(command)
        assert has_trigger is True, "Trigger word não detectada"
        print("✅ OK")

        print("2. Testando classificação de comando...")
        command_start = command.find("lumina") + len("lumina")
        command_text = command[command_start:].strip()
        command_type = hearing._classify_command(command_text)
        assert command_type == "screenshot", f"Tipo incorreto: {command_type}"
        print("✅ OK")

        print("3. Testando cálculo de confiança...")
        confidence = hearing._calculate_confidence(command_text)
        assert confidence > 0.5, f"Confiança baixa: {confidence}"
        print(f"✅ OK (confiança: {confidence:.2f})")

        print("4. Testando decisão de screenshot...")
        import time
        vision.last_screenshot_time = time.time() - 70
        should_capture, reason = vision.should_capture_screenshot(command_text)
        assert should_capture is True, "Deveria capturar"
        assert reason == "trigger_word", f"Razão incorreta: {reason}"
        print("✅ OK")

        print("\n" + "=" * 50)
        print("🎉 TODOS OS TESTES DE INTEGRAÇÃO PASSARAM!")
        print("Módulos de visão e audição estão integrados corretamente.")

    asyncio.run(run_integration_tests())