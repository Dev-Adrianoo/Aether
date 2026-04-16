"""
Integração com OpenClaude via subprocess + flag -p.
Usa --output-format stream-json para streaming em tempo real.
Não requer gRPC nem bun — funciona com o install npm global.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

OPENCLAUDE_BIN = Path(
    r"C:\Users\Adria\AppData\Roaming\npm\node_modules"
    r"\@gitlawb\openclaude\dist\cli.mjs"
)


class OpenClaudeSubprocess:
    """
    Chama o OpenClaude em modo não-interativo (-p) e faz streaming da resposta.
    Por padrão roda oculto. Pode abrir janela visível sob demanda.
    """

    def __init__(self):
        self._terminal_proc: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        return OPENCLAUDE_BIN.exists()

    async def ask(
        self,
        prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        working_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        Envia prompt ao OpenClaude e retorna resposta completa.
        Se on_chunk for fornecido, chama a cada fragmento de texto recebido (streaming).
        """
        if not self.is_available():
            logger.error(f"OpenClaude não encontrado em: {OPENCLAUDE_BIN}")
            return None

        cmd = [
            "node",
            str(OPENCLAUDE_BIN),
            "-p", prompt,
            "--output-format", "stream-json",
            "--dangerously-skip-permissions",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir or str(Path.cwd()),
            )

            full_text = ""

            async for line in proc.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                chunk = self._extract_text(decoded)
                if chunk:
                    full_text += chunk
                    if on_chunk:
                        on_chunk(chunk)

            await proc.wait()

            if proc.returncode != 0:
                err = await proc.stderr.read()
                logger.error(f"OpenClaude saiu com código {proc.returncode}: {err.decode()[:200]}")

            return full_text.strip() or None

        except Exception as e:
            logger.error(f"Erro ao chamar OpenClaude: {e}")
            return None

    def _extract_text(self, line: str) -> str:
        """
        Extrai texto de uma linha do stream-json do OpenClaude.
        Formato Claude Code: {"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}
        Também tenta formato simples {"text": "..."} como fallback.
        """
        try:
            data = json.loads(line)

            # Formato Claude Code stream-json
            if data.get("type") == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    return delta.get("text", "")

            # Formato alternativo
            if "text" in data:
                return data["text"]

            # result final
            if data.get("type") == "result" and "result" in data:
                return data["result"]

        except (json.JSONDecodeError, KeyError):
            # Linha não é JSON — pode ser texto puro
            if not line.startswith("{"):
                return line

        return ""

    def run_visible(self, prompt: str, working_dir: Optional[str] = None):
        """
        Singleton: reutiliza terminal aberto ou abre um novo.
        Escreve o prompt num arquivo temporário e passa via stdin — evita erro de parsing.
        """
        cwd = working_dir or str(Path.home() / "Documents")

        cwd_path = Path(cwd)
        if not cwd_path.exists() or not cwd_path.is_dir():
            cwd = str(Path.home() / "Documents")

        # Arquivos fixos — sobrescreve sempre, sem acumular lixo
        run_dir = Path(__file__).parent.parent.parent / "data" / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = run_dir / "prompt.txt"
        script_file = run_dir / "run_openclaude.ps1"

        prompt_file.write_text(prompt, encoding="utf-8")
        script_file.write_text(
            f"Set-Location '{cwd}'\n"
            f"$prompt = Get-Content -Raw '{prompt_file}'\n"
            f"node '{OPENCLAUDE_BIN}' --dangerously-skip-permissions -p $prompt\n",
            encoding="utf-8"
        )

        # Singleton: fecha terminal anterior se ainda aberto
        if self._terminal_proc and self._terminal_proc.poll() is None:
            self._terminal_proc.terminate()
            self._terminal_proc = None

        cmd = f'start powershell -NoExit -File "{script_file}"'
        self._terminal_proc = subprocess.Popen(cmd, shell=True)
        logger.info(f"OpenClaude visível (singleton) em: {cwd}")

    def show_terminal(self, shell: str = "powershell"):
        """
        Abre o OpenClaude em uma janela de terminal visível.
        shell: 'powershell' (padrão) ou 'cmd'
        """
        if self._terminal_proc and self._terminal_proc.poll() is None:
            logger.info("Terminal OpenClaude já está aberto")
            return

        if shell == "cmd":
            cmd = f'start cmd /k "node {OPENCLAUDE_BIN}"'
        else:
            cmd = f'start powershell -NoExit -Command "node \'{OPENCLAUDE_BIN}\'"'

        self._terminal_proc = subprocess.Popen(cmd, shell=True)
        logger.info(f"Terminal OpenClaude aberto ({shell})")

    def hide_terminal(self):
        """Fecha a janela do terminal visível, se aberta."""
        if self._terminal_proc and self._terminal_proc.poll() is None:
            self._terminal_proc.terminate()
            self._terminal_proc = None
            logger.info("Terminal OpenClaude fechado")
        else:
            logger.info("Terminal OpenClaude não estava aberto")

    async def shutdown(self):
        self.hide_terminal()
