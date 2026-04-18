"""
Integracao com OpenClaude via subprocess + flag -p.
Usa --output-format stream-json para streaming em tempo real.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional

from config import config

logger = logging.getLogger(__name__)


class OpenClaudeSubprocess:
    """
    Chama o OpenClaude em modo nao interativo (-p) e pode abrir janela visivel.
    O binario vem do config por instancia, nao de constante global hardcoded.
    """

    def __init__(self):
        self._terminal_proc: Optional[subprocess.Popen] = None
        self._bin_path = config.openclaude.bin_path

    def is_available(self) -> bool:
        return self._bin_path.exists()

    async def ask(
        self,
        prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        working_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Envia prompt ao OpenClaude e retorna resposta completa."""
        if not self.is_available():
            logger.error("OpenClaude nao encontrado em: %s", self._bin_path)
            return None

        cmd = [
            "node",
            str(self._bin_path),
            "-p",
            prompt,
            "--output-format",
            "stream-json",
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
                logger.error("OpenClaude saiu com codigo %s: %s", proc.returncode, err.decode()[:200])

            return full_text.strip() or None

        except Exception as e:
            logger.error("Erro ao chamar OpenClaude: %s", e)
            return None

    def _extract_text(self, line: str) -> str:
        """Extrai texto de uma linha stream-json do Claude Code/OpenClaude."""
        try:
            data = json.loads(line)

            if data.get("type") == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    return delta.get("text", "")

            if "text" in data:
                return data["text"]

            if data.get("type") == "result" and "result" in data:
                return data["result"]

        except (json.JSONDecodeError, KeyError):
            if not line.startswith("{"):
                return line

        return ""

    def run_visible(self, prompt: str, working_dir: Optional[str] = None) -> Optional[subprocess.Popen]:
        """
        Singleton: fecha terminal anterior e abre um novo com o prompt.
        Escreve sentinel quando o node termina.
        """
        cwd = working_dir or str(Path.home() / "Documents")
        cwd_path = Path(cwd)
        if not cwd_path.exists() or not cwd_path.is_dir():
            cwd = str(Path.home() / "Documents")

        run_dir = Path(__file__).parent.parent.parent / "data" / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = run_dir / "prompt.txt"
        script_file = run_dir / "run_openclaude.ps1"
        sentinel_file = run_dir / "done.sentinel"

        sentinel_file.unlink(missing_ok=True)
        prompt_file.write_text(prompt, encoding="utf-8")
        script_file.write_text(
            f"Set-Location '{cwd}'\n"
            f"$prompt = Get-Content -Raw '{prompt_file}'\n"
            f"node '{self._bin_path}' --dangerously-skip-permissions --no-session-persistence -p $prompt\n"
            f"'done' | Out-File -FilePath '{sentinel_file}' -Encoding utf8\n"
            f"Write-Host ''\n"
            f"Write-Host 'OpenClaude terminou. Pressione qualquer tecla para fechar.'\n"
            f"$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')\n",
            encoding="utf-8",
        )

        if self._terminal_proc and self._terminal_proc.poll() is None:
            self._terminal_proc.terminate()
            try:
                self._terminal_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._terminal_proc.kill()
            self._terminal_proc = None

        self._terminal_proc = subprocess.Popen(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_file)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        logger.info("OpenClaude visivel em: %s", cwd)
        return self._terminal_proc

    def show_terminal(self, shell: str = "powershell"):
        """Abre terminal interativo do OpenClaude. Fecha o anterior se existir."""
        if self._terminal_proc and self._terminal_proc.poll() is None:
            self._terminal_proc.terminate()
            try:
                self._terminal_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._terminal_proc.kill()
            self._terminal_proc = None

        run_dir = Path(__file__).parent.parent.parent / "data" / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        if shell == "cmd":
            script_file = run_dir / "openclaude_terminal.bat"
            script_file.write_text(
                f"@echo off\nnode \"{self._bin_path}\" --dangerously-skip-permissions\n",
                encoding="utf-8",
            )
            args = ["cmd", "/k", str(script_file)]
        else:
            script_file = run_dir / "openclaude_terminal.ps1"
            script_file.write_text(
                f"node '{self._bin_path}' --dangerously-skip-permissions\n",
                encoding="utf-8",
            )
            args = ["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(script_file)]

        self._terminal_proc = subprocess.Popen(
            args,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        logger.info("Terminal OpenClaude aberto (%s)", shell)

    def hide_terminal(self) -> bool:
        """Fecha a janela do terminal visivel. Retorna True se havia algo aberto."""
        if self._terminal_proc and self._terminal_proc.poll() is None:
            self._terminal_proc.terminate()
            try:
                self._terminal_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._terminal_proc.kill()
            self._terminal_proc = None
            logger.info("Terminal fechado")
            return True
        logger.info("Nenhum terminal aberto para fechar")
        return False

    async def shutdown(self):
        self.hide_terminal()
