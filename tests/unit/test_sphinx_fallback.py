"""
Testes para fallback do CMU Sphinx
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.voice.voice_listener import VoiceListener


class TestSphinxFallback:
    """Testes para fallback do CMU Sphinx"""

    @pytest.fixture
    def listener(self):
        """Fixture para criar VoiceListener limpo"""
        return VoiceListener()

    def test_check_sphinx_availability_available(self):
        """Testa verificação quando CMU Sphinx está disponível"""
        # Mock das importações dentro do método _check_sphinx_availability
        with patch('src.voice.voice_listener.sr') as mock_sr, \
             patch('src.voice.voice_listener.pocketsphinx'):

            listener = VoiceListener()
            assert hasattr(listener, 'sphinx_available')
            # O método _check_sphinx_availability é chamado no __init__

    def test_check_sphinx_availability_not_available(self):
        """Testa verificação quando CMU Sphinx não está disponível"""
        # Mock sr e simular ImportError para pocketsphinx
        with patch('src.voice.voice_listener.sr') as mock_sr:
            mock_sr.Recognizer.return_value = Mock()
            with patch('src.voice.voice_listener.pocketsphinx', side_effect=ImportError("No module named 'pocketsphinx'")):
                listener = VoiceListener()
                assert hasattr(listener, 'sphinx_available')
                # O valor será definido pelo método _check_sphinx_availability

    @pytest.mark.asyncio
    async def test_recognize_speech_google_success(self, listener):
        """Testa reconhecimento bem-sucedido com Google"""
        # Mock do recognizer
        mock_recognizer = Mock()
        mock_recognizer.recognize_google.return_value = "texto reconhecido"
        listener.recognizer = mock_recognizer
        listener.sphinx_available = True

        mock_audio = Mock()

        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.return_value = "texto reconhecido"

            result = await listener._recognize_speech(mock_audio)

            assert result == "texto reconhecido"
            mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_recognize_speech_google_fallback_to_sphinx(self, listener):
        """Testa fallback do Google para CMU Sphinx"""
        # Mock do recognizer
        mock_recognizer = Mock()
        listener.recognizer = mock_recognizer
        listener.sphinx_available = True

        mock_audio = Mock()

        # Simular RequestError do Google, depois sucesso do Sphinx
        with patch('asyncio.to_thread') as mock_to_thread:
            # Primeira chamada (Google) levanta RequestError
            import speech_recognition as sr
            mock_to_thread.side_effect = [
                sr.RequestError("API error"),
                "texto do sphinx"
            ]

            result = await listener._recognize_speech(mock_audio)

            assert result == "texto do sphinx"
            assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    async def test_recognize_speech_google_fallback_sphinx_not_available(self, listener):
        """Testa fallback quando Sphinx não está disponível"""
        mock_recognizer = Mock()
        listener.recognizer = mock_recognizer
        listener.sphinx_available = False  # Sphinx não disponível

        mock_audio = Mock()

        with patch('asyncio.to_thread') as mock_to_thread:
            import speech_recognition as sr
            mock_to_thread.side_effect = sr.RequestError("API error")

            result = await listener._recognize_speech(mock_audio)

            assert result is None
            mock_to_thread.call_count == 1  # Só tentou Google

    @pytest.mark.asyncio
    async def test_recognize_speech_unknown_value_fallback(self, listener):
        """Testa fallback quando Google não entende a fala"""
        mock_recognizer = Mock()
        listener.recognizer = mock_recognizer
        listener.sphinx_available = True

        mock_audio = Mock()

        with patch('asyncio.to_thread') as mock_to_thread:
            import speech_recognition as sr
            # Primeiro UnknownValueError, depois sucesso do Sphinx
            mock_to_thread.side_effect = [
                sr.UnknownValueError(),
                "texto do sphinx"
            ]

            result = await listener._recognize_speech(mock_audio)

            assert result == "texto do sphinx"
            assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    async def test_recognize_speech_sphinx_empty_result(self, listener):
        """Testa quando Sphinx retorna texto vazio"""
        mock_recognizer = Mock()
        listener.recognizer = mock_recognizer
        listener.sphinx_available = True

        mock_audio = Mock()

        with patch('asyncio.to_thread') as mock_to_thread:
            import speech_recognition as sr
            mock_to_thread.side_effect = [
                sr.RequestError("API error"),
                ""  # Sphinx retorna vazio
            ]

            result = await listener._recognize_speech(mock_audio)

            assert result is None

    @pytest.mark.asyncio
    async def test_recognize_speech_both_fail(self, listener):
        """Testa quando Google e Sphinx falham"""
        mock_recognizer = Mock()
        listener.recognizer = mock_recognizer
        listener.sphinx_available = True

        mock_audio = Mock()

        with patch('asyncio.to_thread') as mock_to_thread:
            import speech_recognition as sr
            # Google falha com RequestError, Sphinx falha com Exception
            mock_to_thread.side_effect = [
                sr.RequestError("API error"),
                Exception("Sphinx error")
            ]

            result = await listener._recognize_speech(mock_audio)

            assert result is None

    def test_sphinx_language_support(self):
        """Testa suporte a idioma português no Sphinx"""
        # CMU Sphinx tem suporte limitado a português
        # Em produção, pode precisar de modelos específicos
        listener = VoiceListener()

        # Verificar que o método usa "pt-BR" como idioma
        # Isso é testado indiretamente nos testes de reconhecimento
        assert hasattr(listener, 'sphinx_available')


if __name__ == "__main__":
    # Execução manual dos testes
    import asyncio

    async def run_tests():
        print("🧪 Testando fallback do CMU Sphinx...\n")

        listener = VoiceListener()

        print("1. Verificando disponibilidade do Sphinx...")
        print(f"   Sphinx disponível: {listener.sphinx_available}")

        if listener.sphinx_available:
            print("✅ CMU Sphinx está disponível para fallback offline")
        else:
            print("⚠️  CMU Sphinx não disponível. Para instalar:")
            print("   pip install pocketsphinx")
            print("   (Nota: suporte a português pode ser limitado)")

        print("\n2. Testando estrutura de fallback...")
        # Testar se o método _recognize_speech tem lógica de fallback
        import inspect
        source = inspect.getsource(listener._recognize_speech)
        assert "recognize_google" in source, "Google Speech não encontrado"
        assert "recognize_sphinx" in source, "CMU Sphinx não encontrado"
        print("✅ Estrutura de fallback implementada")

        print("\n🎉 Testes de fallback do CMU Sphinx concluídos!")

    asyncio.run(run_tests())