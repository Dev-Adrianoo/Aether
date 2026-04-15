"""
Cliente OpenClaude para integração com o Aether
Envia contexto visual e recebe insights
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class OpenClaudeClient:
    """Cliente para comunicação com OpenClaude"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.api_key = None
        self.base_url = None
        self.model = None
        self.session_active = False

        logger.info("OpenClaudeClient inicializado")

    async def initialize(self):
        """Inicializa o cliente com configurações do .env"""
        try:
            # Carregar configurações do .env
            import os
            from dotenv import load_dotenv

            # Tentar carregar .env.local primeiro (prioridade), depois .env
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

            # 1. .env.local (prioridade máxima - não commitado)
            env_local_path = os.path.join(base_dir, '.env.local')
            if os.path.exists(env_local_path):
                load_dotenv(env_local_path)
                logger.info(f"Configurações carregadas de {env_local_path}")
            else:
                logger.debug(".env.local não encontrado")

            # 2. .env (fallback - pode ser commitado sem chaves)
            env_path = os.path.join(base_dir, '.env')
            if os.path.exists(env_path):
                load_dotenv(env_path, override=False)  # Não sobrescreve .env.local
                logger.info(f"Configurações de fallback carregadas de {env_path}")
            else:
                logger.warning("Arquivo .env não encontrado")

            # Obter configurações do ambiente
            self.api_key = os.getenv('OPENCLAUDE_API_KEY')
            self.base_url = os.getenv('OPENCLAUDE_BASE_URL', 'https://api.openclaude.ai/v1')
            self.model = os.getenv('OPENCLAUDE_MODEL', 'deepseek-chat')

            if not self.api_key:
                logger.warning("OPENCLAUDE_API_KEY não configurada")
                logger.info("OpenClaude funcionará em modo offline")
                self.session_active = False
                return False

            logger.info(f"OpenClaude configurado: {self.base_url}, modelo: {self.model}")

            # Testar conexão básica
            connection_ok = await self._test_connection()

            if connection_ok:
                self.session_active = True
                logger.info("[OK] OpenClaude conectado e pronto")
                return True
            else:
                logger.warning("OpenClaude não disponível - modo offline")
                self.session_active = False
                return False

        except Exception as e:
            logger.error(f"Erro na inicialização do OpenClaudeClient: {e}")
            self.session_active = False
            return False

    async def _test_connection(self):
        """Testa conexão com DeepSeek API (OpenAI-compatible)"""
        try:
            import aiohttp

            # DeepSeek usa formato OpenAI-compatible
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # Payload de teste simples (OpenAI format)
            test_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": "Teste de conexão. Responda apenas com 'OK'."}],
                "max_tokens": 10,
                "temperature": 0.1
            }

            logger.debug(f"Testando conexão com {self.base_url}/chat/completions")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=test_payload,
                    headers=headers,
                    timeout=10
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        # OpenAI-compatible format
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', 'OK')
                        logger.info(f"[OK] Conexão DeepSeek OK: {content}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.warning(f"DeepSeek respondeu com status {response.status}: {error_text}")
                        return False

        except aiohttp.ClientError as e:
            logger.warning(f"Erro de conexão com DeepSeek: {e}")
            return False
        except Exception as e:
            logger.warning(f"Erro no teste de conexão: {e}")
            return False

    async def send_visual_context(self, screenshot_data: Dict[str, Any], analysis: Dict[str, Any]):
        """Envia contexto visual para análise do OpenClaude"""
        if not self.session_active:
            logger.warning("OpenClaude não disponível - ignorando envio de contexto")
            return None

        try:
            # Preparar payload
            payload = {
                "type": "visual_context",
                "timestamp": datetime.now().isoformat(),
                "screenshot": {
                    "dimensions": screenshot_data.get("dimensions", (0, 0)),
                    "timestamp": screenshot_data.get("timestamp"),
                },
                "analysis": analysis,
                "request": {
                    "action": "analyze_screenshot",
                    "priority": "high" if analysis.get("has_errors") else "normal"
                }
            }

            logger.info(f"Enviando contexto visual para OpenClaude: {analysis.get('summary', 'Sem resumo')}")

            # Enviar para OpenClaude
            response = await self._send_to_openclaude(payload)

            if response:
                logger.info(f"Resposta do OpenClaude: {response.get('summary', 'Sem resumo')}")
                return response
            else:
                logger.warning("Nenhuma resposta do OpenClaude")
                return None

        except Exception as e:
            logger.error(f"Erro ao enviar contexto visual: {e}")
            return None

    async def _send_to_openclaude(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Envia payload para API do OpenClaude"""
        try:
            import aiohttp

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else ""
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/analyze",
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:

                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Erro na API OpenClaude: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Erro na comunicação com OpenClaude: {e}")
            return None

    async def ask_question(self, question: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Faz uma pergunta ao OpenClaude usando a API de chat"""
        if not self.session_active or not self.api_key:
            logger.warning("OpenClaude não disponível - usando resposta simulada")
            return "OpenClaude não está disponível no momento."

        try:
            import aiohttp

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # Construir mensagens com contexto
            messages = []

            # Adicionar contexto se fornecido
            if context:
                context_text = f"Contexto: {json.dumps(context, ensure_ascii=False)}"
                messages.append({"role": "system", "content": context_text})

            # Adicionar pergunta do usuário
            messages.append({"role": "user", "content": question})

            # Payload para API de chat
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7
            }

            logger.info(f"Enviando pergunta para OpenClaude: '{question[:50]}...'")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        answer = data.get('choices', [{}])[0].get('message', {}).get('content', 'Sem resposta')

                        logger.info(f"Resposta OpenClaude recebida ({len(answer)} chars)")
                        return answer

                    else:
                        error_text = await response.text()
                        logger.error(f"Erro na API OpenClaude: {response.status} - {error_text}")
                        return f"Erro na API OpenClaude: {response.status}"

        except aiohttp.ClientError as e:
            logger.error(f"Erro de conexão ao fazer pergunta: {e}")
            return f"Erro de conexão: {str(e)}"
        except Exception as e:
            logger.error(f"Erro ao fazer pergunta: {e}")
            return f"Erro: {str(e)}"

    async def log_interaction(self, interaction_type: str, data: Dict[str, Any]):
        """Registra interação no OpenClaude"""
        try:
            payload = {
                "type": "interaction_log",
                "interaction_type": interaction_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }

            # Enviar de forma assíncrona (não bloqueante)
            asyncio.create_task(self._send_to_openclaude(payload))
            logger.debug(f"Interação registrada: {interaction_type}")

        except Exception as e:
            logger.error(f"Erro ao registrar interação: {e}")

    async def shutdown(self):
        """Encerra o cliente"""
        self.session_active = False
        logger.info("OpenClaudeClient encerrado")