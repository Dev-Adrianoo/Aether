#!/usr/bin/env python3
"""
Lumina — ponto de entrada principal.
Orquestra visão, voz e integração com LLM.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

# Arquivo: tudo em DEBUG para diagnóstico
_file_handler = logging.FileHandler('lumina.log')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))

# Console: só erros reais — o output visual vem dos print() nos módulos
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(logging.Formatter('WARN  %(message)s'))

logging.basicConfig(level=logging.DEBUG, handlers=[_file_handler, _console_handler])
logger = logging.getLogger(__name__)


class LuminaSensorySystem:

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.running = False
        self.modules = {}
        self._last_recognized = ""
        self._last_code_action = ""  # última tarefa enviada ao OpenClaude — contexto de sessão
        from src.voice.stt_corrector import STTCorrector
        self.stt_corrector = STTCorrector()

    async def initialize(self):
        try:
            from src.vision.screenshot_manager import ScreenshotManager
            from src.voice.voice_listener import VoiceListener
            from src.voice.tts_engine import TTSEngine
            from src.integrations.openclaude_client import OpenClaudeClient
            from src.brain.obsidian_manager import ObsidianManager
            from config import config

            print("Lumina iniciando...")

            from src.integrations.openclaude_subprocess import OpenClaudeSubprocess
            oc = OpenClaudeSubprocess()
            if oc.is_available():
                self.modules['openclaude'] = oc
                print("[OK] OpenClaude subprocess disponível")
            else:
                print("[WARN] OpenClaude não encontrado — modo voz desativado")

            self.modules['vision'] = ScreenshotManager()
            self.modules['hearing'] = VoiceListener(config={
                'print_feedback': True,
                'device_index': config.audio.device_index,
                'sample_rate': config.audio.sample_rate,
            })
            self.modules['speech'] = TTSEngine(use_edge_tts=config.tts.engine == 'edge-tts')
            self.modules['integration'] = OpenClaudeClient()
            self.modules['brain'] = ObsidianManager(
                vault_path=str(config.obsidian.vault_path),
                log_folder=config.obsidian.log_folder
            )

            await self.modules['speech'].initialize()

            openclaude_ok = await self.modules['integration'].initialize()
            if openclaude_ok:
                print("[OK] LLM conectado (DeepSeek)")
            else:
                print("[WARN] LLM offline — conversa livre indisponível")
                await self._speak(
                    "Atenção: sem conexão com o LLM. Conversa livre indisponível."
                )

            self._setup_callbacks()
            return True

        except ImportError as e:
            print(f"[ERRO] Módulo não encontrado: {e}")
            return False
        except Exception as e:
            print(f"[ERRO] Falha na inicialização: {e}")
            return False

    async def _speak(self, text: str):
        """Fala e muta o microfone durante a reprodução para evitar loopback."""
        hearing = self.modules.get('hearing')
        if hearing:
            hearing.is_speaking = True
        try:
            await self.modules['speech'].speak(text)
            await asyncio.sleep(2.0)  # buffer para eco do speaker dissipar
        finally:
            if hearing:
                hearing.is_speaking = False

    def _setup_callbacks(self):
        vision = self.modules['vision']
        hearing = self.modules['hearing']

        vision.on_important_screenshot = self._handle_screenshot

        hearing.register_command_handler("screenshot", self._handle_screenshot_command)
        hearing.register_command_handler("stop", self._handle_stop_command)
        hearing.register_command_handler("help", self._handle_help_command)
        hearing.register_command_handler("status", self._handle_status_command)
        hearing.register_command_handler("action", self._handle_action)
        hearing.register_command_handler("task", self._handle_task_command)
        hearing.register_command_handler("llm_route", self._handle_llm_route)
        hearing.register_command_handler("openclaude", self._handle_openclaude_terminal)
        hearing.register_command_handler("unknown", self._handle_llm_route)

    def _parse_monitor(self, command_text: str) -> int:
        text = command_text.lower()
        if any(w in text for w in ["direita", "segunda", "monitor 2", "tela 2", "dois"]):
            return 2
        if any(w in text for w in ["esquerda", "primeira", "monitor 1", "tela 1", "um"]):
            return 1
        return 1

    async def _handle_screenshot_command(self, command_text: str, confidence: float):
        monitor = self._parse_monitor(command_text)
        label = f"monitor {monitor}"
        analysis = await self.modules['vision'].capture_and_analyze(
            reason='voice_command', monitor_index=monitor
        )
        if analysis and analysis.get('filepath'):
            w, h = analysis.get('dimensions', (0, 0))
            await self._speak(
                f"Print do {label} capturado. {w}x{h} pixels, salvo em screenshots."
            )
        else:
            await self._speak("Erro ao capturar tela.")

    async def _handle_task_command(self, command_text: str, confidence: float):
        from src.actions.system_actions import write_claude_task
        keywords = ["anota", "anote", "tarefa", "lembra", "lembre", "adiciona", "adicione", "registra", "registre"]
        task_text = command_text.lower()
        for kw in keywords:
            if kw in task_text:
                idx = task_text.find(kw) + len(kw)
                task_text = command_text[idx:].strip(" :,-")
                break
        if task_text:
            write_claude_task(task_text)
            response = await self.modules['integration'].ask_question(
                f"Acabei de anotar a tarefa: '{task_text}'. Confirme de forma natural e breve."
            )
            await self._speak(response or "Anotado.")
        else:
            await self._speak("Qual é a tarefa que devo anotar?")

    async def _handle_llm_route(self, command_text: str, confidence: float):
        """
        Classificador LLM: uma chamada DeepSeek entende a intenção e roteia.
        Sem keywords. Qualquer fala natural funciona.
        """
        import json as _json

        # Aplica correções conhecidas antes de processar
        corrected = self.stt_corrector.apply(command_text)
        if corrected != command_text:
            print(f"[STT corrigido] '{command_text}' → '{corrected}'")
        command_text = corrected

        last = self._last_recognized
        self._last_recognized = command_text

        llm = self.modules['integration']
        speech = self.modules['speech']

        classification_prompt = f"""Você recebe texto de comando de voz (pode estar garrafado pelo STT).
Analise e retorne APENAS JSON válido com a intenção. Nenhum texto adicional.

Tipos disponíveis:
- screenshot: capturar tela → {{"type":"screenshot","monitor":1}}  (monitor: 1=esquerda/padrão, 2=direita/segundo)
- action: abrir aplicativo → {{"type":"action","app":"youtube"}}  (apps válidos: youtube, spotify, vscode, unity, obsidian)
- terminal: abrir ou fechar terminal → {{"type":"terminal","action":"open","shell":"powershell"}}  (action: open|close, shell: powershell|cmd)
- task: anotar tarefa → {{"type":"task","text":"texto da tarefa"}}
- code_agent: criar/editar arquivos, executar scripts, rodar código, navegar pastas → {{"type":"code_agent","prompt":"prompt técnico claro"}}
- correction: microfone transcreveu errado e usuário corrige O QUE ELE DISSE → {{"type":"correction","wrong":"texto errado","right":"texto correto"}}
- conversation: conversa geral → {{"type":"conversation","response":"resposta em 1-2 frases coloquiais"}}

Regras:
- screenshot: qualquer pedido de capturar/fotografar/printar/foto da tela
- action: abrir apps por nome (youtube, spotify, vscode, unity, obsidian)
- terminal: abrir/fechar cmd, powershell, opencloud, terminal — NÃO use code_agent para isso
- code_agent: tarefas no sistema de arquivos ou execução de código — NÃO use para abrir terminal simples
- correction: SOMENTE quando o usuário diz que o MICROFONE errou ("não, eu disse X", "você entendeu errado, falei X"). NÃO use quando reclama do comportamento da Lumina. Use a fala anterior como "wrong": "{last}"
- conversation: perguntas, reclamações de comportamento, comentários, qualquer coisa que não se encaixe acima

Texto recebido: "{command_text}"

Retorne APENAS o JSON."""

        raw = await llm.classify(classification_prompt)
        if not raw:
            await self._speak("Não entendi. Pode repetir?")
            return

        # Extrai JSON da resposta (LLM às vezes adiciona markdown)
        try:
            raw_clean = raw.strip().strip("```json").strip("```").strip()
            intent = _json.loads(raw_clean)
        except Exception:
            # JSON inválido ou truncado — trata como conversa normal
            await self._handle_conversation(command_text, confidence)
            return

        intent_type = intent.get("type", "conversation")

        if intent_type == "screenshot":
            monitor = intent.get("monitor", 1)
            fake_text = "direita" if monitor == 2 else "esquerda"
            await self._handle_screenshot_command(fake_text, confidence)

        elif intent_type == "action":
            app = intent.get("app", "")
            await self._handle_action(app, confidence)

        elif intent_type == "terminal":
            action = intent.get("action", "open")
            shell = intent.get("shell", "powershell")
            await self._handle_openclaude_terminal(
                f"{'feche' if action == 'close' else 'abre'} {shell}", confidence
            )

        elif intent_type == "task":
            text = intent.get("text", "")
            await self._handle_task_command(text, confidence)

        elif intent_type == "code_agent":
            prompt = intent.get("prompt", command_text)
            await self._handle_code_agent(prompt, confidence)

        elif intent_type == "correction":
            wrong = intent.get("wrong", "").strip()
            right = intent.get("right", "").strip()
            if wrong and right:
                self.stt_corrector.add(wrong, right)
                await self._save_correction_to_vault(wrong, right)
                await self._speak(f"Entendido. Vou lembrar que '{wrong}' é '{right}'.")
            else:
                await self._speak("Não entendi a correção. Pode repetir?")

        elif intent_type == "conversation":
            response = intent.get("response", "")
            if response:
                await self._speak(response)
            else:
                await self._handle_conversation(command_text, confidence)

        else:
            await self._handle_conversation(command_text, confidence)

    async def _handle_code_agent(self, command_text: str, confidence: float):
        """Recebe prompt ja limpo do LLM router e envia pro OpenClaude."""
        oc = self.modules.get('openclaude')
        if not oc:
            await self._speak("OpenClaude nao esta disponivel.")
            return

        lumina_dir = str(Path(__file__).parent)
        lumina_keywords = ["lumina", "voce mesmo", "em voce", "no seu codigo", "obsidian", "vault", "nova acao", "system_actions", "registry"]
        is_self = any(kw in command_text.lower() for kw in lumina_keywords)
        working_dir = lumina_dir if is_self else str(Path.home() / "Documents")

        # Instrui OpenClaude a executar diretamente sem pedir confirmação
        prompt = (
            "Execute a tarefa diretamente sem pedir confirmação nem fazer perguntas. "
            "Não mostre design nem planejamento — só execute:\n\n"
            + command_text
        )

        await self._speak("Entendido. Abrindo o terminal.")
        oc.run_visible(prompt=prompt, working_dir=working_dir)
        self._last_code_action = command_text
        await self._speak("OpenClaude ta trabalhando. Acompanha no terminal.")

        asyncio.create_task(self._monitor_openclaude_sentinel())

    async def _monitor_openclaude_sentinel(self):
        """Aguarda sentinel file do script e fala quando OpenClaude terminar."""
        sentinel = Path(__file__).parent / "data" / "run" / "done.sentinel"
        for _ in range(300):  # timeout: 5 min
            await asyncio.sleep(1)
            if sentinel.exists():
                try:
                    sentinel.unlink()
                except OSError:
                    pass
                await self._speak("OpenClaude terminou. Confere o resultado no terminal.")
                return
        await self._speak("OpenClaude ainda ta rodando. Me chama quando terminar.")

    async def _handle_openclaude_terminal(self, command_text: str, confidence: float):
        oc = self.modules.get('openclaude')
        if not oc:
            await self._speak("OpenClaude não está disponível.")
            return
        text = command_text.lower()
        fechar = any(w in text for w in ["esconde", "fecha", "feche", "oculta", "esconder"])
        if fechar:
            closed = oc.hide_terminal()
            if closed:
                await self._speak("Terminal fechado.")
            else:
                await self._speak("Não tenho nenhum terminal aberto. Só consigo fechar terminais que eu mesma abri.")
            return

        # Detecta qual shell o usuário quer
        if "cmd" in text:
            shell = "cmd"
        elif any(w in text for w in ["powershell", "power shell", "posh"]):
            shell = "powershell"
        else:
            shell = "powershell"

        already_open = oc._terminal_proc and oc._terminal_proc.poll() is None
        oc.show_terminal(shell=shell)
        if already_open:
            await self._speak("Terminal já está aberto.")
        else:
            await self._speak(f"Terminal aberto em {shell}.")

    async def _handle_action(self, command_text: str, confidence: float):
        from src.actions.registry import dispatch
        feedback = dispatch(command_text)
        if feedback:
            await self._speak(feedback)
        else:
            await self._handle_conversation(command_text, confidence)

    async def _handle_stop_command(self, command_text: str, confidence: float):
        await self._speak("Encerrando")
        self.running = False

    async def _handle_status_command(self, command_text: str, confidence: float):
        await self._speak(
            "Online e funcionando. LLM conectado, voz ativa."
        )

    async def _handle_help_command(self, command_text: str, confidence: float):
        await self._speak(
            "Diga Lumina seguido do seu comando. "
            "Posso capturar a tela, responder perguntas ou verificar meu status."
        )

    async def _handle_conversation(self, command_text: str, confidence: float):
        logger.debug(f"Conversa: {command_text}")
        question = command_text
        if self._last_code_action:
            question = (
                f"[Contexto: acabei de enviar ao OpenClaude a tarefa: '{self._last_code_action}'. "
                f"O terminal está aberto e pode ainda estar executando.]\n\n{command_text}"
            )
        response = await self.modules['integration'].ask_question(question)
        if not response:
            await self._speak("Não consegui responder agora. Pode repetir?")
            return

        # LLM decidiu que é tarefa de execução — rota pro code_agent
        if response.strip().startswith("CÓDIGO:"):
            task = response.strip()[len("CÓDIGO:"):].strip()
            await self._handle_code_agent(task, confidence)
            return

        await self._speak(response)
        await self._log_to_obsidian({
            'type': 'conversation',
            'question': command_text,
            'answer': response,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })

    async def _handle_screenshot(self, screenshot_data, analysis):
        logger.debug(f"Screenshot: {analysis.get('summary', '')}")
        if analysis.get('has_errors') or analysis.get('needs_attention'):
            await self.modules['integration'].send_visual_context(screenshot_data, analysis)

    async def _save_correction_to_vault(self, wrong: str, right: str):
        """Registra correção de STT no vault Obsidian."""
        vault = Path(r"C:\Users\Adria\Documents\Documentation\Dev-lumina-agent")
        corrections_note = vault / "04_APRENDIZADOS" / "LEARN_STT_corrections.md"
        from datetime import datetime
        entry = f"- `{wrong}` → `{right}`  <!-- {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n"
        if not corrections_note.exists():
            corrections_note.write_text("# Correções STT\n\nMapeamentos aprendidos automaticamente.\n\n", encoding="utf-8")
        with open(corrections_note, "a", encoding="utf-8") as f:
            f.write(entry)

    async def _log_to_obsidian(self, data):
        await self.modules['brain'].save_interaction(data)

    async def run(self):
        if not await self.initialize():
            print("[ERRO] Falha na inicialização. Encerrando.")
            return

        self.running = True
        print("Pronto. Diga 'Lumina' para ativar.\n")

        try:
            await asyncio.gather(
                self.modules['hearing'].start(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        self.running = False
        await self._save_session_summary()
        for module in self.modules.values():
            if hasattr(module, 'stop'):
                await module.stop()
            elif hasattr(module, 'shutdown'):
                await module.shutdown()
        print("\nLumina encerrada.")

    async def _save_session_summary(self):
        try:
            integration = self.modules.get('integration')
            brain = self.modules.get('brain')
            if not integration or not brain:
                return
            summary = await integration.summarize_session()
            if summary:
                integration._append_session_to_recentes(summary)
                await brain.save_interaction({
                    'type': 'session_summary',
                    'summary': summary,
                    'timestamp': datetime.now().isoformat()
                })
                print("Sessão resumida e salva no vault.")
        except Exception as e:
            logger.warning(f"Erro ao salvar resumo da sessão: {e}")


async def main():
    lumina = LuminaSensorySystem()
    await lumina.run()


if __name__ == "__main__":
    asyncio.run(main())
