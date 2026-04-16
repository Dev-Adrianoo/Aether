#!/usr/bin/env python3
"""
Script de teste para verificar instalação do Lumina
"""

import sys
import asyncio
from datetime import datetime

def test_imports():
    """Testa todas as importações essenciais"""
    print("🧪 TESTANDO INSTALAÇÃO DO LUMINA")
    print("=" * 50)

    tests = [
        ("OpenCV (visão)", "cv2"),
        ("MSS (screenshots)", "mss"),
        ("Pillow (imagens)", "PIL.Image"),
        ("SpeechRecognition (STT)", "speech_recognition"),
        ("pyttsx3 (TTS offline)", "pyttsx3"),
        ("edge-tts (TTS premium)", "edge_tts"),
        ("NumPy", "numpy"),
    ]

    all_passed = True

    for test_name, module_name in tests:
        try:
            if "." in module_name:
                # Para imports como PIL.Image
                parts = module_name.split(".")
                exec(f"import {parts[0]}")
                __import__(parts[0])
            else:
                __import__(module_name)

            print(f"✅ {test_name}: OK")

        except ImportError as e:
            print(f"❌ {test_name}: FALHA - {e}")
            all_passed = False
        except Exception as e:
            print(f"⚠️  {test_name}: AVISO - {e}")

    print("=" * 50)
    return all_passed

async def test_screenshot():
    """Testa captura de screenshot"""
    print("\n📸 TESTANDO CAPTURA DE SCREENSHOT")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager()
        print("✅ ScreenshotManager importado")

        # Testar captura
        print("Capturando screenshot...")
        result = await manager.capture_and_analyze(reason="test")

        if result.get("error"):
            print(f"❌ Erro na captura: {result['error']}")
            return False
        else:
            print(f"✅ Screenshot capturado: {result.get('summary', 'Sucesso')}")
            dimensions = result.get("dimensions", (0, 0))
            if dimensions != (0, 0):
                print(f"   Dimensões: {dimensions}")
            return True

    except Exception as e:
        print(f"❌ Erro no teste de screenshot: {e}")
        return False

async def test_tts():
    """Testa síntese de voz"""
    print("\n🗣️ TESTANDO SÍNTESE DE VOZ")
    print("=" * 50)

    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty('voices')

        print(f"✅ pyttsx3 inicializado")
        print(f"   Vozes disponíveis: {len(voices)}")

        # Testar voz rápida (sem falar)
        print("   Teste de voz (silencioso)...")

        return True

    except Exception as e:
        print(f"❌ Erro no TTS: {e}")
        return False

async def main():
    """Função principal de teste"""
    print(f"🧠 LUMINA - Teste de Instalação")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Testar imports
    if not test_imports():
        print("\n❌ ALGUMAS DEPENDÊNCIAS FALTANDO")
        print("Execute: pip install mss opencv-python Pillow SpeechRecognition pyttsx3 edge-tts")
        return

    print("\n✅ TODAS AS DEPENDÊNCIAS INSTALADAS")

    # Testar funcionalidades
    screenshot_ok = await test_screenshot()
    tts_ok = await test_tts()

    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES:")
    print(f"   Screenshots: {'✅' if screenshot_ok else '❌'}")
    print(f"   TTS: {'✅' if tts_ok else '❌'}")

    if screenshot_ok and tts_ok:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("A Lumina está pronta para uso.")
        print("\nPara iniciar: python main.py")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM")
        print("Verifique os erros acima.")

if __name__ == "__main__":
    asyncio.run(main())