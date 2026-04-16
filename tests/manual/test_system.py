#!/usr/bin/env python3
"""
Script de teste rápido para o sistema Iris.
"""

import asyncio
import sys
from pathlib import Path

# Adicionar diretório atual ao path
sys.path.insert(0, str(Path(__file__).parent))

async def test_config():
    """Testa o sistema de configuração"""
    print("🧪 Testando sistema de configuração...")

    try:
        from config import config
        config.print_summary()

        if config.validate():
            print("✅ Configuração OK")
            return True
        else:
            print("❌ Configuração com problemas")
            return False

    except Exception as e:
        print(f"❌ Erro no teste de configuração: {e}")
        return False

async def test_voice_system():
    """Testa o sistema de voz"""
    print("\n🎤 Testando sistema de voz...")

    try:
        from src.voice.voice_listener import VoiceListener

        listener = VoiceListener(config={'print_feedback': True})

        print("Testando microfone por 5 segundos...")
        success = await listener.test_microphone()

        if success:
            print("✅ Sistema de voz OK")
            return True
        else:
            print("❌ Problemas no sistema de voz")
            return False

    except Exception as e:
        print(f"❌ Erro no teste de voz: {e}")
        return False

async def test_tts():
    """Testa o sistema de TTS"""
    print("\n🗣️  Testando sistema de TTS...")

    try:
        from src.voice.tts_engine import TTSEngine

        tts = TTSEngine(use_edge_tts=False)
        await tts.initialize()

        print("Falando teste...")
        await tts.speak("Sistema Iris funcionando")

        await tts.shutdown()
        print("✅ Sistema TTS OK")
        return True

    except Exception as e:
        print(f"❌ Erro no teste TTS: {e}")
        return False

async def main():
    """Executa todos os testes"""
    print("="*50)
    print("TESTE DO SISTEMA IRIS")
    print("="*50)

    tests_passed = 0
    total_tests = 3

    # Teste de configuração
    if await test_config():
        tests_passed += 1

    # Teste de voz
    if await test_voice_system():
        tests_passed += 1

    # Teste TTS
    if await test_tts():
        tests_passed += 1

    # Resultado
    print("\n" + "="*50)
    print(f"RESULTADO: {tests_passed}/{total_tests} testes passados")

    if tests_passed == total_tests:
        print("✅ SISTEMA PRONTO PARA USO")
        print("\nPara iniciar: python main.py")
        print("Comandos: 'Iris, captura tela'")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM")
        print("Verifique as mensagens acima.")

    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())