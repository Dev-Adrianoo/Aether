"""
Cliente LLM do Lumina.
Compatível com qualquer API no formato OpenAI (DeepSeek, OpenAI, Groq, etc).
Troque OPENCLAUDE_BASE_URL + OPENCLAUDE_MODEL + OPENCLAUDE_API_KEY no .env.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """Você é o Lumina — parceiro de dev do {user_name}, não um assistente.

Personalidade:
- Curioso e direto. Quando algo te interessa, comenta. Quando algo parece errado, fala.
- Humor seco, sem exagero. Não tente ser engraçado o tempo todo.
- Chame de "Mestre" com naturalidade — não em toda frase, só quando fizer sentido.
- Português coloquial brasileiro. Sem formalidade, sem "claro!", sem "com certeza!".
- Você tem opinião. Se discordar, diz. Se achar que tem jeito melhor, sugere.

Como responder em voz:
- Sem markdown, sem listas, sem asteriscos — você está falando, não escrevendo.
- 1 a 3 frases no máximo. Mais que isso fica pesado pra ouvir.
- Se precisar de mais contexto pra responder bem, PERGUNTA antes de chutar.
- Não repita o que o Mestre disse. Responda ou reaja, não ecoe.
- Se a fala chegou cortada ou sem sentido, diz que não entendeu e pede pra repetir.

LIMITAÇÕES FÍSICAS — nunca minta sobre o que você vê ou faz:
- Você NÃO vê a tela a não ser que um screenshot tenha sido capturado NESTA sessão.
- Você NÃO sabe o que está acontecendo no terminal do OpenClaude em tempo real.
- Se o Mestre perguntar "você vê X?", "o que está acontecendo no terminal?", etc — seja honesto: "Não consigo ver o terminal. Quer que eu tire um print?"
- Nunca invente que está vendo algo que não viu. Isso quebra a confiança.

Quando engajar proativamente:
- Se o Mestre parecer travado num problema, pergunta o que está acontecendo.
- Se fez algo e não teve retorno, pode perguntar se funcionou.
- Não fique em silêncio quando tem algo óbvio pra dizer.

O que você PODE fazer (diga ao Mestre quando fizer sentido):
- Abrir terminal com OpenClaude para executar código → "abre o terminal" ou "terminal"
- Enviar tarefas de código ao OpenClaude → "código: [tarefa]" ou "programa: [tarefa]"
- Capturar tela → "captura tela" ou "tira print"
- Abrir apps → "abre o YouTube / Spotify / VSCode / Unity / Obsidian"
- Anotar tarefas → "anota: [tarefa]"

REGRA CRÍTICA — quando o Mestre pedir pra criar, editar, gerar arquivo, rodar comando, navegar pasta, abrir arquivo no navegador, ou qualquer tarefa de execução no sistema (EXCETO screenshot/print/foto da tela — esses são comandos nativos, não use CÓDIGO: pra isso):
NÃO diga "Vou fazer" nem explique. Responda APENAS: CÓDIGO: [descrição clara e técnica da tarefa]
O sistema vai capturar isso e mandar pro OpenClaude executar automaticamente.

Exemplos:
- "cria um html com hello world" → CÓDIGO: Crie o arquivo index.html em Documents com <h1>Hello World</h1> e abra no navegador
- "qual pasta estou" → CÓDIGO: Mostre o diretório atual e liste os arquivos
- "cria uma pasta teste" → CÓDIGO: Crie a pasta 'teste' em Documents

Projeto:
- LuminaXR: modelador 3D em XR/VR com Unity e C#
- Fase atual: sistema sensorial Python (STT, TTS, visão)
- Estado detalhado abaixo (fonte: vault Obsidian)

ACESSO AO VAULT:
- O conteúdo do vault Obsidian do Mestre foi carregado no seu contexto (veja abaixo).
- Quando perguntado sobre o projeto, documentação ou notas do Obsidian, USE esse conteúdo.
- NUNCA diga "não tenho acesso ao Obsidian" — você tem, está no contexto."""


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
        self._system_prompt = _SYSTEM_PROMPT_TEMPLATE  # formatado em initialize()

        logger.info("OpenClaudeClient inicializado")

    async def initialize(self):
        try:
            from config import config

            self.api_key = config.openclaude.api_key
            self.base_url = config.openclaude.base_url
            self.model = config.openclaude.model

            if not self.api_key:
                logger.warning("OPENCLAUDE_API_KEY não configurada — modo offline")
                return False

            logger.info(f"OpenClaude configurado: {self.base_url}, modelo: {self.model}")

            self._system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(user_name=config.user_name)

            if await self._test_connection():
                self.session_active = True
                self._load_vault_context(str(config.obsidian.dev_vault_path))
                logger.info("[OK] OpenClaude conectado e pronto")
                return True

            self.session_active = False
            return False

        except Exception as e:
            logger.error(f"Erro na inicialização do OpenClaudeClient: {e}")
            self.session_active = False
            return False

    def _load_vault_context(self, vault_path: str):
        """
        Injeta MAPA.md + últimas 5 sessões no system prompt.
        Teto fixo de tokens independente do tamanho do histórico.
        """
        import os

        sections = []

        mapa = os.path.join(vault_path, 'MAPA.md')
        try:
            with open(mapa, encoding='utf-8') as f:
                sections.append("--- ESTADO DO PROJETO (MAPA.md) ---\n" + f.read())
        except FileNotFoundError:
            logger.warning(f"MAPA.md não encontrado em {mapa}")

        recentes = os.path.join(vault_path, 'SESSOES_RECENTES.md')
        try:
            with open(recentes, encoding='utf-8') as f:
                sections.append("--- SESSÕES RECENTES ---\n" + f.read())
        except FileNotFoundError:
            pass  # ainda não existe, normal na primeira sessão

        if sections:
            context = "\n\n".join(sections)
            self._system_prompt = SYSTEM_PROMPT + "\n\n" + context
            self._vault_path = vault_path
            total = sum(len(s) for s in sections)
            print(f"[OK] Vault carregado ({total} chars)")
        else:
            self._vault_path = vault_path

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

    async def classify(self, prompt: str) -> Optional[str]:
        """
        Chamada stateless para classificação — sem histórico, sem system prompt longo.
        Mais rápida que ask_question. Usada pelo LLM router.
        """
        if not self.session_active or not self.api_key:
            return None
        try:
            import aiohttp
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
                "temperature": 0.1
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    return None
        except Exception as e:
            logger.error(f"Erro na classificação: {e}")
            return None

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
                    timeout=aiohttp.ClientTimeout(total=60)
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

    def _append_session_to_recentes(self, summary: str, max_sessions: int = 5):
        """Salva resumo no arquivo rolling SESSOES_RECENTES.md, mantendo só os últimos N."""
        import os
        vault = getattr(self, '_vault_path', None)
        if not vault or not summary:
            return
        path = os.path.join(vault, 'SESSOES_RECENTES.md')
        from datetime import datetime
        entry = f"### {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{summary}\n"
        try:
            existing = []
            if os.path.exists(path):
                with open(path, encoding='utf-8') as f:
                    raw = f.read()
                existing = [s for s in raw.split('### ') if s.strip()]
            existing.append(entry.lstrip('### '))
            kept = existing[-max_sessions:]
            with open(path, 'w', encoding='utf-8') as f:
                f.write(''.join(f'### {s}' for s in kept))
        except Exception as e:
            logger.warning(f"Erro ao salvar SESSOES_RECENTES: {e}")

    async def summarize_session(self) -> str:
        """Pede ao LLM um resumo da sessão para salvar no vault."""
        if not self.session_active or not self._history:
            return ""
        try:
            import aiohttp
            messages = [
                {"role": "system", "content": "Resuma em 3-5 frases o que foi discutido e decidido nesta sessão. Formato: texto simples, sem markdown."},
            ] + self._history[-10:]

            payload = {"model": self.model, "messages": messages, "max_tokens": 200, "temperature": 0.3}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload, headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
        except Exception as e:
            logger.warning(f"Erro ao gerar resumo: {e}")
        return ""

    def clear_history(self):
        self._history.clear()

    async def shutdown(self):
        self.session_active = False
        logger.info("OpenClaudeClient encerrado")
