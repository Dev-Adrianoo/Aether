"""
Cliente LLM do Aether.
Compatível com qualquer API no formato OpenAI (DeepSeek, OpenAI, Groq, etc).
Troque OPENCLAUDE_BASE_URL + OPENCLAUDE_MODEL + OPENCLAUDE_API_KEY no .env.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o Aether, assistente pessoal de desenvolvimento do Mestre (Adriano).
Sua personalidade: direto, inteligente, levemente irreverente — como um colega de equipe sênior, não um robô.

Regras:
- Chame o usuário de "Mestre" naturalmente, não em toda frase
- Responda em português brasileiro, de forma conversacional
- Máximo 2 frases curtas — sua voz será lida em voz alta
- Sem listas, sem bullet points, sem formatação markdown
- Se não souber algo, diga diretamente em vez de enrolar

Projeto:
- LuminaXR: modelador 3D em Realidade Estendida com Unity e C#
- Fase atual: sistema sensorial Python (STT, TTS, visão)
- Você tem acesso ao estado atual do projeto via vault (veja abaixo)"""


class OpenClaudeClient:
    """
    Cliente para qualquer LLM compatível com a API OpenAI.
    Mantém histórico de conversa para contexto contínuo.
    """

    def __init__(self):
        self.api_key: Optional[str] = None
        self.base_url: Optional[str] = None
        self.model: Optional[str] = None
        self.session_active = False
        self._history: List[Dict[str, str]] = []
        self._max_history = 10
        self._system_prompt = SYSTEM_PROMPT

        logger.info("OpenClaudeClient inicializado")

    async def initialize(self):
        try:
            import os
            from dotenv import load_dotenv

            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

            env_local = os.path.join(base_dir, '.env.local')
            if os.path.exists(env_local):
                load_dotenv(env_local)

            env_path = os.path.join(base_dir, '.env')
            if os.path.exists(env_path):
                load_dotenv(env_path, override=False)

            self.api_key = os.getenv('OPENCLAUDE_API_KEY')
            self.base_url = os.getenv('OPENCLAUDE_BASE_URL', 'https://api.deepseek.com/v1')
            self.model = os.getenv('OPENCLAUDE_MODEL', 'deepseek-chat')

            if not self.api_key:
                logger.warning("OPENCLAUDE_API_KEY não configurada — modo offline")
                return False

            logger.info(f"OpenClaude configurado: {self.base_url}, modelo: {self.model}")

            if await self._test_connection():
                self.session_active = True
                self._load_vault_context(os.getenv(
                    'OBSIDIAN_DEV_VAULT',
                    r'C:\Users\Adria\Documents\Documentation\Dev-Aether-logs'
                ))
                logger.info("[OK] OpenClaude conectado e pronto")
                return True

            self.session_active = False
            return False

        except Exception as e:
            logger.error(f"Erro na inicialização do OpenClaudeClient: {e}")
            self.session_active = False
            return False

    def _load_vault_context(self, vault_path: str):
        """Lê MAPA.md do vault e injeta no system prompt."""
        import os
        mapa = os.path.join(vault_path, 'MAPA.md')
        try:
            with open(mapa, encoding='utf-8') as f:
                content = f.read()
            self._system_prompt = (
                SYSTEM_PROMPT
                + "\n\n--- ESTADO ATUAL DO PROJETO (fonte: MAPA.md) ---\n"
                + content
            )
            print(f"[OK] Vault carregado ({len(content)} chars)")
        except FileNotFoundError:
            logger.warning(f"MAPA.md não encontrado em {mapa}")
        except Exception as e:
            logger.warning(f"Erro ao ler vault: {e}")

    async def _test_connection(self) -> bool:
        try:
            import aiohttp

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Teste. Responda apenas: OK"}],
                "max_tokens": 10,
                "temperature": 0.1
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        logger.info(f"[OK] Conexão DeepSeek OK: {content}")
                        return True
                    logger.warning(f"API respondeu {response.status}")
                    return False

        except Exception as e:
            logger.warning(f"Erro no teste de conexão: {e}")
            return False

    async def ask_question(self, question: str) -> Optional[str]:
        """
        Envia pergunta ao LLM e retorna resposta em texto.
        Mantém histórico das últimas interações para contexto.
        """
        if not self.session_active or not self.api_key:
            logger.warning("OpenClaude não disponível")
            return None

        try:
            import aiohttp

            self._history.append({"role": "user", "content": question})

            messages = [{"role": "system", "content": self._system_prompt}] + self._history

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.7
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        answer = data['choices'][0]['message']['content']

                        self._history.append({"role": "assistant", "content": answer})
                        if len(self._history) > self._max_history * 2:
                            self._history = self._history[-self._max_history * 2:]

                        logger.info(f"Resposta recebida ({len(answer)} chars)")
                        return answer

                    error = await response.text()
                    logger.error(f"Erro na API: {response.status} — {error}")
                    return None

        except Exception as e:
            logger.error(f"Erro ao fazer pergunta: {e}")
            return None

    async def send_visual_context(self, screenshot_data: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[str]:
        """
        Envia análise de screenshot ao LLM pedindo insights.
        Usa chat completions — não requer endpoint especial.
        """
        if not self.session_active:
            return None

        try:
            summary = analysis.get('summary', 'Sem resumo')
            has_errors = analysis.get('has_errors', False)
            needs_attention = analysis.get('needs_attention', False)

            prompt = (
                f"Capturei a tela do usuário. Análise: {summary}. "
                f"Erros detectados: {has_errors}. Precisa atenção: {needs_attention}. "
                "O que você observa e o que o usuário deveria saber?"
            )

            return await self.ask_question(prompt)

        except Exception as e:
            logger.error(f"Erro ao enviar contexto visual: {e}")
            return None

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def clear_history(self):
        self._history.clear()

    async def shutdown(self):
        self.session_active = False
        logger.info("OpenClaudeClient encerrado")
