"""
Testes unitários do módulo de visão (screenshots)
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from pathlib import Path

# Importar módulo a testar
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vision.screenshot_manager import ScreenshotManager


class TestScreenshotManager:
    """Testes para ScreenshotManager"""

    @pytest.fixture
    def manager(self):
        """Fixture para criar manager limpo"""
        return ScreenshotManager()

    @pytest.mark.asyncio
    async def test_initialization(self, manager):
        """Testa inicialização do manager"""
        assert manager.trigger_words == ["tela", "print", "screenshot", "foto", "mostra", "olha", "captura"]
        assert manager.screenshot_interval == 60
        assert manager.last_screenshot_time == 0
        assert manager.on_important_screenshot is None

    @pytest.mark.asyncio
    async def test_check_trigger_words_positive(self, manager):
        """Testa detecção de trigger words (casos positivos)"""
        test_cases = [
            ("tira um print da tela", True),
            ("mostra a tela pra mim", True),
            ("captura isso aqui", True),
            ("olha como está", True),
            ("tira uma foto disso", True),
            ("faz um screenshot agora", True),
            ("captura a tela por favor", True),
        ]

        for text, expected in test_cases:
            result = await manager.check_trigger_words(text)
            assert result == expected, f"Falha em: '{text}'"

    @pytest.mark.asyncio
    async def test_check_trigger_words_negative(self, manager):
        """Testa detecção de trigger words (casos negativos)"""
        test_cases = [
            ("teste normal", False),
            ("outra coisa qualquer", False),
            ("vamos lá", False),
            ("isso é um teste", False),
            ("", False),
            (None, False),
        ]

        for text, expected in test_cases:
            result = await manager.check_trigger_words(text)
            assert result == expected, f"Falha em: '{text}'"

    def test_should_capture_screenshot_trigger(self, manager):
        """Testa decisão de captura por trigger word"""
        # Configurar tempo atual
        import time
        manager.last_screenshot_time = time.time() - 30  # 30 segundos atrás

        # Deve capturar por trigger word
        should_capture, reason = manager.should_capture_screenshot("tira um print da tela")
        assert should_capture is True
        assert reason == "trigger_word"

    def test_should_capture_screenshot_interval(self, manager):
        """Testa decisão de captura por intervalo"""
        import time
        # Configurar para capturar (passou intervalo)
        manager.last_screenshot_time = time.time() - 70  # 70 segundos atrás (intervalo é 60)

        should_capture, reason = manager.should_capture_screenshot()
        assert should_capture is True
        assert reason == "interval"

    def test_should_capture_screenshot_no_capture(self, manager):
        """Testa decisão de NÃO capturar"""
        import time
        # Configurar para NÃO capturar (não passou intervalo)
        manager.last_screenshot_time = time.time() - 30  # 30 segundos atrás (intervalo é 60)

        should_capture, reason = manager.should_capture_screenshot()
        assert should_capture is False
        assert reason is None

    @pytest.mark.asyncio
    @patch('src.vision.screenshot_manager.mss.mss')
    async def test_capture_screen_success(self, mock_mss, manager):
        """Testa captura de screenshot bem-sucedida"""
        # Mock do mss
        mock_sct = Mock()
        mock_monitor = {'left': 0, 'top': 0, 'width': 1920, 'height': 1080}
        mock_sct.monitors = [None, mock_monitor]

        mock_screenshot = Mock()
        mock_screenshot.width = 1920
        mock_screenshot.height = 1080
        mock_screenshot.size = (1920, 1080)
        mock_screenshot.bgra = b'\x00' * (1920 * 1080 * 4)  # Dummy data

        mock_sct.grab.return_value = mock_screenshot
        mock_mss.return_value.__enter__.return_value = mock_sct

        # Mock do PIL
        with patch('src.vision.screenshot_manager.Image') as mock_image:
            mock_img = Mock()
            mock_image.frombytes.return_value = mock_img

            # Executar captura
            result = await manager._capture_screen()

            # Verificar resultado
            assert result["dimensions"] == (1920, 1080)
            assert "timestamp" in result
            assert result["pil_image"] == mock_img
            assert "filepath" in result

    @pytest.mark.asyncio
    async def test_capture_screen_mss_not_installed(self, manager):
        """Testa captura quando mss não está instalado"""
        # Simular ImportError
        with patch('src.vision.screenshot_manager.mss', None):
            result = await manager._capture_screen()

            assert result["error"] == "mss não instalado"
            assert result["dimensions"] == (0, 0)

    @pytest.mark.asyncio
    async def test_analyze_screenshot_basic(self, manager):
        """Testa análise básica de screenshot"""
        screenshot_data = {
            "timestamp": datetime.now().isoformat(),
            "dimensions": (1920, 1080)
        }

        analysis = await manager._analyze_screenshot(screenshot_data)

        assert analysis["timestamp"] == screenshot_data["timestamp"]
        assert analysis["summary"] == "Tela capturada"
        assert analysis["has_errors"] is False
        assert analysis["needs_attention"] is False
        assert "detected_elements" in analysis
        assert "change_significance" in analysis

    @pytest.mark.asyncio
    async def test_save_screenshot(self, manager, tmp_path):
        """Testa salvamento de screenshot"""
        # Mock do caminho
        with patch('src.vision.screenshot_manager.Path') as mock_path:
            mock_save_dir = Mock()
            mock_save_dir.mkdir.return_value = None
            mock_save_dir.__truediv__.return_value = tmp_path / "test_screenshot.png"

            mock_path.return_value.parent = mock_save_dir
            mock_path.return_value.__str__.return_value = str(tmp_path / "test_screenshot.png")

            screenshot_data = {"timestamp": "test"}
            analysis = {"summary": "test"}

            # Não deve lançar exceção
            await manager._save_screenshot(screenshot_data, analysis, "test")


if __name__ == "__main__":
    # Execução manual dos testes (para debugging)
    import asyncio

    async def run_tests():
        manager = ScreenshotManager()

        print("🧪 Testando inicialização...")
        assert manager.trigger_words, "Trigger words não configuradas"
        print("✅ OK")

        print("🧪 Testando trigger words...")
        result = await manager.check_trigger_words("tira um print")
        assert result is True, "Trigger word não detectada"
        print("✅ OK")

        print("🧪 Testando should_capture_screenshot...")
        import time
        manager.last_screenshot_time = time.time() - 70
        should_capture, reason = manager.should_capture_screenshot()
        assert should_capture is True, "Deveria capturar por intervalo"
        assert reason == "interval", "Razão incorreta"
        print("✅ OK")

        print("\n🎉 Todos os testes básicos passaram!")

    asyncio.run(run_tests())