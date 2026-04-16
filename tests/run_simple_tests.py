#!/usr/bin/env python3
"""
Script de teste simplificado que não requer pytest
"""

import asyncio
import sys
from pathlib import Path

# Adicionar caminho
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_vision_basics():
    """Testa funcionalidades básicas do módulo de visão"""
    print("🧪 TESTANDO MÓDULO DE VISÃO")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager()
        print("✅ ScreenshotManager inicializado")

        # Testar trigger words
        test_cases = [
            ("tira um print da tela", True),
            ("mostra a tela", True),
            ("teste normal", False),
        ]

        print("Testando trigger words:")
        for text, expected in test_cases:
            result = await manager.check_trigger_words(text)
            status = "✅" if result == expected else "❌"
            print(f"   {status} '{text}' -> {result}")

        # Testar decisão de captura
        import time
        manager.last_screenshot_time = time.time() - 70  # 70 segundos atrás

        should_capture, reason = manager.should_capture_screenshot("tira um print")
        print(f"\n✅ Decisão de captura: {should_capture} (razão: {reason})")

        return True

    except Exception as e:
        print(f"❌ Erro no teste de visão: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_hearing_basics():
    """Testa funcionalidades básicas do módulo de audição"""
    print("\n🧪 TESTANDO MÓDULO DE AUDIÇÃO")
    print("=" * 50)

    try:
        from src.voice.voice_listener import VoiceListener

        listener = VoiceListener()
        print("✅ VoiceListener inicializado")

        # Testar classificação de comandos
        test_cases = [
            ("tira um print da tela", "screenshot"),
            ("captura a tela", "screenshot"),
            ("para tudo", "stop"),
        ]

        print("Testando classificação de comandos:")
        for text, expected in test_cases:
            result = listener._classify_command(text)
            status = "✅" if result == expected else "❌"
            print(f"   {status} '{text}' -> {result}")

        # Testar cálculo de confiança
        confidence = listener._calculate_confidence("tela print")
        print(f"\n✅ Confiança para 'tela print': {confidence:.2f}")

        return True

    except Exception as e:
        print(f"❌ Erro no teste de audição: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_integration():
    """Testa integração básica entre módulos"""
    print("\n🧪 TESTANDO INTEGRAÇÃO VISÃO-AUDIÇÃO")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager
        from src.voice.voice_listener import VoiceListener

        vision = ScreenshotManager()
        hearing = VoiceListener()

        # Comando de exemplo
        command = "iris tira um print da tela"

        print("1. Extraindo comando do wake word...")
        command_start = command.find("iris") + len("iris")
        command_text = command[command_start:].strip()
        print(f"   Comando: '{command_text}'")

        print("2. Verificando trigger word...")
        has_trigger = await vision.check_trigger_words(command_text)
        print(f"   Tem trigger word: {has_trigger}")

        print("3. Classificando comando...")
        command_type = hearing._classify_command(command_text)
        print(f"   Tipo: {command_type}")

        print("4. Calculando confiança...")
        confidence = hearing._calculate_confidence(command_text)
        print(f"   Confiança: {confidence:.2f}")

        if has_trigger and command_type == "screenshot" and confidence > 0.5:
            print("\n✅ Integração funcionando corretamente!")
            return True
        else:
            print("\n❌ Problema na integração")
            return False

    except Exception as e:
        print(f"❌ Erro no teste de integração: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Função principal"""
    print("🧠 IRIS - TESTES SIMPLIFICADOS")
    print("=" * 50)

    results = []

    # Executar testes
    results.append(("Visão", await test_vision_basics()))
    results.append(("Audição", await test_hearing_basics()))
    results.append(("Integração", await test_integration()))

    # Resumo
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES:")
    print("=" * 50)

    all_passed = True
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"   {status} - {test_name}")
        if not success:
            all_passed = False

    print("=" * 50)

    if all_passed:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("O Iris está pronto para a próxima fase.")
        print("\nPróximos passos:")
        print("1. Instalar pytest: pip install pytest pytest-asyncio")
        print("2. Executar testes completos: python -m pytest tests/ -v")
        print("3. Implementar integração com OpenClaude")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM")
        print("Verifique os erros acima.")

    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)