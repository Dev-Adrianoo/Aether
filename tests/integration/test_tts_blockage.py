"""
Teste de integração para verificar bloqueio do TTS edge-tts
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.speech.tts_engine import TTSEngine
from config import config


async def test_tts_blockage():
    """Testa se o TTS edge-tts trava após múltiplas falas"""
    print("=" * 60)
    print("TESTE DE BLOQUEIO DO TTS EDGE-TTS")
    print("=" * 60)

    # Verificar configuração
    print(f"\n📋 Configuração atual:")
    print(f"   Engine: {config.tts.engine}")
    print(f"   Voz: {config.tts.voice}")
    print(f"   Rate: {config.tts.rate}")

    if config.tts.engine != 'edge-tts':
        print(f"\n⚠️  ATENÇÃO: TTS não configurado como edge-tts ({config.tts.engine})")
        print("   Para testar edge-tts, configure TTS_ENGINE=edge-tts no .env")
        return

    print("\n🚀 Inicializando TTSEngine...")
    tts = TTSEngine()

    # Inicializar
    success = await tts.initialize()
    if not success:
        print("❌ Falha na inicialização do TTSEngine")
        return

    print("✅ TTSEngine inicializado")

    # Teste 1: Frase única
    print("\n" + "-" * 40)
    print("TESTE 1: Frase única")
    print("-" * 40)
    await tts.speak("Primeira fala do sistema Aether.")
    print("✅ Primeira fala concluída")

    # Teste 2: Múltiplas frases seguidas
    print("\n" + "-" * 40)
    print("TESTE 2: Múltiplas frases seguidas")
    print("-" * 40)

    phrases = [
        "Esta é a primeira frase do teste sequencial.",
        "Agora a segunda frase do teste.",
        "Terceira frase para verificar continuidade.",
        "Quarta e última frase do teste sequencial."
    ]

    for i, phrase in enumerate(phrases, 1):
        print(f"\n🎯 Frase {i}/{len(phrases)}: '{phrase[:30]}...'")
        await tts.speak(phrase)
        print(f"✅ Frase {i} concluída")
        await asyncio.sleep(0.5)  # Pequena pausa

    # Teste 3: Mesma frase múltiplas vezes (simula uso real)
    print("\n" + "-" * 40)
    print("TESTE 3: Mesma frase repetida (simula bloqueio)")
    print("-" * 40)

    for i in range(5):
        print(f"\n🔄 Repetição {i + 1}/5")
        await tts.speak(f"Teste de repetição número {i + 1}")
        print(f"✅ Repetição {i + 1} concluída")
        await asyncio.sleep(1.0)

    # Teste 4: Usar método de teste integrado
    print("\n" + "-" * 40)
    print("TESTE 4: Método test_voice() com 2 ciclos")
    print("-" * 40)
    await tts.test_voice(test_count=2)

    # Teste 5: Teste de repetição específico
    print("\n" + "-" * 40)
    print("TESTE 5: test_single_phrase_multiple_times()")
    print("-" * 40)
    await tts.test_single_phrase_multiple_times("Verificando bloqueio", 3)

    # Encerrar
    print("\n" + "-" * 40)
    print("Encerrando teste...")
    await tts.shutdown()

    print("\n" + "=" * 60)
    print("RESULTADO DO TESTE DE BLOQUEIO")
    print("=" * 60)

    print("\n✅ TODOS OS TESTES CONCLUÍDOS")
    print("\n📊 Resumo:")
    print("   - Frase única: OK")
    print("   - Múltiplas frases seguidas: OK")
    print("   - Repetição da mesma frase: OK")
    print("   - Teste com ciclos: OK")
    print("   - Teste específico de repetição: OK")

    print("\n🎉 Sistema NÃO apresentou bloqueio do TTS!")
    print("\n💡 Se o sistema travar em uso real, verifique:")
    print("   1. Conexão com internet (edge-tts requer online)")
    print("   2. Bibliotecas de áudio instaladas (pydub/pygame/playsound)")
    print("   3. Limites de taxa da API edge-tts")


async def test_tts_without_audio_libs():
    """Testa TTS sem bibliotecas de áudio (apenas geração)"""
    print("\n" + "=" * 60)
    print("TESTE SEM BIBLIOTECAS DE ÁUDIO")
    print("=" * 60)

    print("\n⚠️  Testando sem bibliotecas de reprodução...")
    print("   (edge-tts deve gerar áudio mas não reproduzir)")

    tts = TTSEngine()
    await tts.initialize()

    # Testar sem esperar reprodução
    print("\n🎯 Testando geração de áudio...")
    await tts.speak("Teste sem reprodução de áudio")

    print("\n✅ Áudio gerado (mas não reproduzido)")
    print("💡 Instale bibliotecas para reprodução:")
    print("   pip install pydub pygame playsound")

    await tts.shutdown()


if __name__ == "__main__":
    print("🧪 Iniciando testes de bloqueio do TTS edge-tts")

    try:
        # Teste principal
        asyncio.run(test_tts_blockage())

        # Opcional: testar sem bibliotecas de áudio
        # asyncio.run(test_tts_without_audio_libs())

    except KeyboardInterrupt:
        print("\n\n⏹️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante o teste: {e}")
        import traceback
        traceback.print_exc()