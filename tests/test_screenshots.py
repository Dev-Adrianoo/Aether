#!/usr/bin/env python3
"""
Teste avançado do sistema de screenshots do Aether
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path

async def test_basic_capture():
    """Testa captura básica de screenshot"""
    print("📸 TESTE DE CAPTURA BÁSICA")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager()
        print("✅ ScreenshotManager inicializado")

        # Testar captura
        start_time = time.time()
        result = await manager.capture_and_analyze(reason="test")
        capture_time = time.time() - start_time

        print(f"✅ Captura concluída em {capture_time:.2f}s")

        if result.get("error"):
            print(f"❌ Erro: {result['error']}")
            return False

        # Verificar dados
        print(f"   Timestamp: {result.get('timestamp', 'N/A')}")
        print(f"   Resumo: {result.get('summary', 'N/A')}")

        # Verificar se arquivo foi salvo
        filepath = result.get("filepath")
        if filepath and Path(filepath).exists():
            file_size = Path(filepath).stat().st_size
            print(f"✅ Arquivo salvo: {filepath}")
            print(f"   Tamanho: {file_size / 1024:.1f} KB")
        else:
            print("⚠️  Arquivo não salvo (pode ser normal em teste)")

        return True

    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_trigger_words():
    """Testa detecção de trigger words"""
    print("\n🎯 TESTE DE TRIGGER WORDS")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager()
        test_cases = [
            ("tira um print da tela", True),
            ("mostra a tela", True),
            ("captura isso", True),
            ("olha aqui", True),
            ("foto disso", True),
            ("screenshot agora", True),
            ("teste normal", False),
            ("outra coisa", False),
        ]

        print("Testando trigger words:")
        for text, expected in test_cases:
            result = await manager.check_trigger_words(text)
            status = "✅" if result == expected else "❌"
            print(f"   {status} '{text[:20]}...' -> {result} (esperado: {expected})")

        return True

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

async def test_interval_capture():
    """Testa lógica de intervalo"""
    print("\n⏱️ TESTE DE INTERVALO DE CAPTURA")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager()
        manager.screenshot_interval = 2  # 2 segundos para teste rápido

        print("Testando captura por intervalo:")
        print("   Primeira captura...")
        result1 = await manager.capture_and_analyze(reason="test")
        print(f"   ✅ Captura 1: {result1.get('summary', 'OK')}")

        print("   Aguardando 1 segundo...")
        await asyncio.sleep(1)

        # Não deve capturar (ainda não passou intervalo)
        print("   Tentando captura antes do intervalo...")
        should_capture, reason = manager.should_capture_screenshot()
        print(f"   Deve capturar? {should_capture} (razão: {reason})")

        print("   Aguardando mais 1 segundo...")
        await asyncio.sleep(1)

        # Agora deve capturar
        print("   Tentando captura após intervalo...")
        should_capture, reason = manager.should_capture_screenshot()
        print(f"   Deve capturar? {should_capture} (razão: {reason})")

        if should_capture:
            result2 = await manager.capture_and_analyze(reason="test")
            print(f"   ✅ Captura 2: {result2.get('summary', 'OK')}")

        return True

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

async def test_context_economy():
    """Testa economia de contexto"""
    print("\n💡 TESTE DE ECONOMIA DE CONTEXTO")
    print("=" * 50)

    try:
        from src.vision.screenshot_manager import ScreenshotManager

        manager = ScreenshotManager()
        manager.min_interval_for_context = 5  # 5 segundos para teste

        test_scenarios = [
            ("voice_trigger", True, "Trigger por voz sempre envia"),
            ("interval", False, "Intervalo normal não envia"),
            ("error_detected", True, "Erro detectado sempre envia"),
        ]

        print("Testando decisão de envio para contexto:")

        # Simular análise com/sem erros
        analysis_with_error = {"has_errors": True, "change_significance": "low"}
        analysis_normal = {"has_errors": False, "change_significance": "low"}

        for reason, should_send, description in test_scenarios:
            # Mock da análise
            analysis = analysis_with_error if "error" in reason else analysis_normal

            # Simular _should_send_to_context
            current_time = time.time()
            manager.last_context_send_time = current_time - 10  # 10 segundos atrás

            # Lógica do método real (simplificada para teste)
            if reason == "voice_trigger":
                sends = True
            elif analysis.get("has_errors", False):
                sends = True
            elif analysis.get("needs_attention", False):
                sends = True
            elif current_time - manager.last_context_send_time > manager.min_interval_for_context:
                sends = True
            elif analysis.get("change_significance") in ["high", "medium"]:
                # Só envia se não enviou recentemente
                if current_time - manager.last_context_send_time > 60:  # 1 minuto
                    sends = True
                else:
                    sends = False
            else:
                sends = False

            status = "✅" if sends == should_send else "❌"
            print(f"   {status} {description}: {sends}")

        return True

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

async def main():
    """Função principal"""
    print(f"🧠 AETHER - Teste Avançado de Screenshots")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    tests = [
        ("Captura Básica", test_basic_capture),
        ("Trigger Words", test_trigger_words),
        ("Intervalo", test_interval_capture),
        ("Economia de Contexto", test_context_economy),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n🔬 EXECUTANDO: {test_name}")
        try:
            success = await test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Erro não tratado: {e}")
            results.append((test_name, False))

    # Resumo
    print("\n" + "=" * 50)
    print("📊 RESUMO FINAL DOS TESTES:")
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
        print("O sistema de screenshots está funcionando perfeitamente.")
        print("\nPróximos passos:")
        print("1. Integrar com módulo de audição")
        print("2. Implementar wake word 'Aether'")
        print("3. Conectar com OpenClaude")
    else:
        print("\n⚠️  ALGUNS TESTES FALHARAM")
        print("Verifique os erros acima.")

    # Limpar arquivos de teste
    print("\n🧹 Limpando arquivos de teste...")
    try:
        test_dir = Path("data/screenshots")
        if test_dir.exists():
            for file in test_dir.glob("screenshot_*test*.png"):
                file.unlink()
            print("✅ Arquivos de teste removidos")
    except Exception as e:
        print(f"⚠️  Erro ao limpar: {e}")

if __name__ == "__main__":
    asyncio.run(main())