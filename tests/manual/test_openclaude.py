#!/usr/bin/env python3
"""
Teste de conexão com OpenClaude API.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_openclaude():
    """Testa conexão e conversação com OpenClaude"""
    print("🤖 Testando conexão OpenClaude...")

    try:
        from src.integrations.openclaude_client import OpenClaudeClient

        client = OpenClaudeClient()

        print("1. Inicializando cliente...")
        success = await client.initialize()

        if not success:
            print("❌ Falha na inicialização do OpenClaude")
            return False

        print("✅ OpenClaude inicializado")

        # Teste de pergunta simples
        print("\n2. Testando pergunta simples...")
        question = "Qual é a capital do Brasil?"
        print(f"   Pergunta: '{question}'")

        response = await client.ask_question(question)

        if response:
            print(f"✅ Resposta: {response[:100]}...")

            # Teste de conversação contextual
            print("\n3. Testando conversação contextual...")
            follow_up = "E qual é a população aproximada?"
            print(f"   Segunda pergunta: '{follow_up}'")

            # Usar contexto da conversa anterior
            context = {
                "conversation_history": [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": response[:200]}
                ]
            }

            response2 = await client.ask_question(follow_up, context)

            if response2:
                print(f"✅ Resposta contextual: {response2[:100]}...")
                print("\n🎉 OpenClaude funcionando perfeitamente!")
                return True
            else:
                print("❌ Sem resposta contextual")
                return False
        else:
            print("❌ Sem resposta à pergunta simples")
            return False

    except Exception as e:
        print(f"❌ Erro no teste OpenClaude: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Executa teste principal"""
    print("="*50)
    print("TESTE OPENCLAUDE API")
    print("="*50)

    success = await test_openclaude()

    print("\n" + "="*50)
    if success:
        print("✅ OPENCLAUDE PRONTO PARA CONVERSA")
        print("\nPara usar no sistema:")
        print("1. Execute: python main.py")
        print("2. Diga: 'Lumina, qual é a capital da França?'")
        print("3. Sistema responderá por voz")
    else:
        print("❌ PROBLEMAS COM OPENCLAUDE")
        print("\nVerifique:")
        print("1. API key no .env está correta")
        print("2. Conexão com internet")
        print("3. Créditos na conta OpenClaude")

    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())