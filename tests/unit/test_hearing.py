"""
Testes unitários do módulo de audição (VoiceListener)
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
import time

# Importar módulo a testar
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.hearing.voice_listener import VoiceListener


class TestVoiceListener:
    """Testes para VoiceListener"""

    @pytest.fixture
    def listener(self):
        """Fixture para criar listener limpo"""
        return VoiceListener()

    def test_initialization(self, listener):
        """Testa inicialização do listener"""
        assert listener.wake_word == "aether"
        assert listener.listening_active is False
        assert listener.energy_threshold == 4000
        assert listener.pause_threshold == 0.8
        assert listener.phrase_time_limit == 5
        assert listener.on_command_detected is None
        assert listener.on_wake_word_detected is None
        assert listener.last_wake_word_time == 0
        assert listener.wake_word_cooldown == 2

    def test_calculate_confidence(self, listener):
        """Testa cálculo de confiança"""
        # Comandos curtos têm confiança baixa
        assert listener._calculate_confidence("oi") == 0.5

        # Comandos com palavras-chave aumentam confiança
        confidence = listener._calculate_confidence("tira um print da tela")
        assert 0.6 <= confidence <= 0.95  # Deve ter pelo menos +0.1 por "tela"

        # Máximo 0.95
        confidence = listener._calculate_confidence("tela print captura mostra olha foto")
        assert confidence == 0.95  # Máximo

    def test_classify_command(self, listener):
        """Testa classificação de comandos"""
        test_cases = [
            ("tira um print da tela", "screenshot"),
            ("captura a tela agora", "screenshot"),
            ("tira uma foto disso", "screenshot"),
            ("mostra como está", "screenshot"),
            ("olha aqui", "screenshot"),
            ("para tudo", "stop"),
            ("pare agora", "stop"),
            ("encerra o sistema", "stop"),
            ("me ajuda", "help"),
            ("quais comandos", "help"),
            ("qual o status", "status"),
            ("como tá", "status"),
            ("comando desconhecido", "unknown"),
            ("outra coisa qualquer", "unknown"),
        ]

        for text, expected in test_cases:
            result = listener._classify_command(text)
            assert result == expected, f"Falha em: '{text}' -> {result} (esperado: {expected})"

    @pytest.mark.asyncio
    async def test_process_audio_text_wake_word(self, listener):
        """Testa processamento de texto com wake word"""
        # Mock callbacks
        mock_wake_callback = AsyncMock()
        mock_command_callback = AsyncMock()
        listener.on_wake_word_detected = mock_wake_callback
        listener.on_command_detected = mock_command_callback

        # Primeira ativação
        await listener._process_audio_text("aether tira um print")

        # Deve chamar callbacks
        mock_wake_callback.assert_called_once()
        mock_command_callback.assert_called_once_with("tira um print", pytest.approx(0.5, 0.1))

    @pytest.mark.asyncio
    async def test_process_audio_text_wake_word_cooldown(self, listener):
        """Testa cooldown do wake word"""
        listener.last_wake_word_time = time.time() - 1  # 1 segundo atrás (cooldown é 2)

        # Mock callback
        mock_callback = AsyncMock()
        listener.on_wake_word_detected = mock_callback

        # Não deve ativar (ainda em cooldown)
        await listener._process_audio_text("aether teste")

        mock_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_audio_text_no_wake_word(self, listener):
        """Testa texto sem wake word"""
        # Mock callback
        mock_callback = AsyncMock()
        listener.on_command_detected = mock_callback

        # Texto sem wake word
        await listener._process_audio_text("texto normal sem wake word")

        # Não deve chamar callback (sem estado "acordado" ainda)
        mock_callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_command(self, listener):
        """Testa processamento de comando"""
        # Mock callback
        mock_callback = AsyncMock()
        listener.on_command_detected = mock_callback

        await listener._process_command("tira um print da tela")

        mock_callback.assert_called_once()
        args = mock_callback.call_args[0]
        assert args[0] == "tira um print da tela"
        assert 0.5 <= args[1] <= 0.95  # Confiança dentro do esperado

    @pytest.mark.asyncio
    @patch('src.hearing.voice_listener.sr.Recognizer')
    @patch('src.hearing.voice_listener.sr.Microphone')
    async def test_start_listening_basic(self, mock_mic, mock_recognizer, listener):
        """Testa início básico da escuta"""
        # Mocks
        mock_source = Mock()
        mock_mic.return_value.__enter__.return_value = mock_source

        mock_rec = Mock()
        mock_rec.energy_threshold = 4000
        mock_rec.pause_threshold = 0.8
        mock_rec.dynamic_energy_threshold = True
        mock_recognizer.return_value = mock_rec

        # Configurar para parar rápido
        listener.listening_active = True

        # Mock do listen para retornar rápido
        mock_audio = Mock()
        mock_rec.listen.return_value = mock_audio
        mock_rec.recognize_google.return_value = "aether teste"

        # Executar em background e parar rápido
        task = asyncio.create_task(listener.start_listening())
        await asyncio.sleep(0.1)
        listener.listening_active = False
        await task

        # Verificar chamadas básicas
        mock_rec.adjust_for_ambient_noise.assert_called_once_with(mock_source, duration=1)

    @pytest.mark.asyncio
    @patch('src.hearing.voice_listener.sr.Recognizer')
    async def test_recognize_speech_success(self, mock_recognizer, listener):
        """Testa reconhecimento de fala bem-sucedido"""
        # Setup
        listener.recognizer = Mock()
        listener.recognizer.recognize_google.return_value = "texto reconhecido"

        mock_audio = Mock()

        result = await listener._recognize_speech(mock_audio)

        assert result == "texto reconhecido"
        listener.recognizer.recognize_google.assert_called_once_with(mock_audio, language="pt-BR")

    @pytest.mark.asyncio
    @patch('src.hearing.voice_listener.sr')
    async def test_recognize_speech_unknown_value(self, mock_sr, listener):
        """Testa reconhecimento quando fala não é entendida"""
        listener.recognizer = Mock()
        listener.recognizer.recognize_google.side_effect = mock_sr.UnknownValueError

        mock_audio = Mock()

        result = await listener._recognize_speech(mock_audio)

        assert result is None

    @pytest.mark.asyncio
    @patch('src.hearing.voice_listener.Path')
    @patch('src.hearing.voice_listener.json')
    async def test_log_command(self, mock_json, mock_path, listener):
        """Testa registro de comando no log"""
        # Mock do Path
        mock_log_dir = Mock()
        mock_log_dir.mkdir.return_value = None
        mock_log_file = Mock()
        mock_log_dir.__truediv__.return_value = mock_log_file

        mock_path.return_value.parent = mock_log_dir
        mock_path.return_value.__str__.return_value = "/fake/path/commands.jsonl"

        # Mock do open
        mock_file = Mock()
        mock_file.__enter__.return_value = mock_file

        with patch('builtins.open', return_value=mock_file):
            await listener._log_command("teste", 0.8, "screenshot")

            # Verificar que escreveu JSON
            mock_file.write.assert_called_once()
            call_args = mock_file.write.call_args[0][0]
            assert '"command": "teste"' in call_args
            assert '"confidence": 0.8' in call_args
            assert '"type": "screenshot"' in call_args

    @pytest.mark.asyncio
    async def test_shutdown(self, listener):
        """Testa encerramento do listener"""
        listener.listening_active = True
        await listener.shutdown()
        assert listener.listening_active is False


if __name__ == "__main__":
    # Execução manual dos testes (para debugging)
    import asyncio

    async def run_tests():
        listener = VoiceListener()

        print("🧪 Testando inicialização...")
        assert listener.wake_word == "aether", "Wake word incorreta"
        print("✅ OK")

        print("🧪 Testando classificação de comandos...")
        result = listener._classify_command("tira um print da tela")
        assert result == "screenshot", f"Classificação incorreta: {result}"
        print("✅ OK")

        print("🧪 Testando cálculo de confiança...")
        confidence = listener._calculate_confidence("tela print")
        assert 0.6 <= confidence <= 0.95, f"Confiança fora do esperado: {confidence}"
        print("✅ OK")

        print("\n🎉 Todos os testes básicos passaram!")

    asyncio.run(run_tests())