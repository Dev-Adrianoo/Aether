# Missão para Opus — Lumina Bug Sprint

## Contexto do Projeto

**Lumina** é um assistente de desenvolvimento por voz para Windows, escrito em Python.
- Diretório: `C:\Users\Adria\Documents\lumina-agent`
- Vault Obsidian (documentação): `C:\Users\Adria\Documents\Documentation\Dev-lumina-agent`
- Stack: Python 3.14, asyncio, SpeechRecognition, edge-tts, DeepSeek LLM (via openclaude_client.py), OpenClaude CLI (node.js)
- Entrypoint: `main.py` → `LuminaSensorySystem`
- Configuração central: `config.py` → `LuminaConfig`

## Arquitetura Resumida

```
main.py (LuminaSensorySystem)
├── src/voice/voice_listener.py       → captura áudio + wake word "lumina"
├── src/voice/command_processor.py    → classifica comando (só "stop" local; resto → llm_route)
├── main.py:_handle_llm_route()       → DeepSeek classifica intenção → roteia handler
├── src/integrations/openclaude_client.py  → DeepSeek API (classificação + conversa)
└── src/integrations/openclaude_subprocess.py → OpenClaude CLI (agente de código)
```

## Fluxo de um Comando de Voz

1. Usuário fala → STT reconhece → `command_processor.py` detecta wake word "lumina"
2. Texto do comando vai para `_handle_llm_route()` em `main.py`
3. DeepSeek classifica a intenção: screenshot / action / terminal / task / code_agent / correction / conversation
4. Handler correspondente executa

## Bugs Conhecidos — Corrigir UM POR UM

### BUG 1: `show_terminal(shell="cmd")` quebra o quoting do node

**Arquivo**: `src/integrations/openclaude_subprocess.py`, método `show_terminal`

**Sintoma**:
```
Error: Cannot find module 'C:\Users\Adria\Documents\lumina-agent\"C:\Users\Adria\AppData\Roaming\npm\node_modules\@gitlawb\openclaude\dist\cli.mjs"'
```

**Causa**: O código atual usa:
```python
args = ["cmd", "/k", f"node \"{OPENCLAUDE_BIN}\""]
```
Quando Python converte essa lista para a command line do Windows (`list2cmdline`), as aspas internas ficam escapadas de um jeito que o cmd repassa ao node COM aspas no path, causando o erro de módulo.

**Fix**: Usar a mesma abordagem de `run_visible` — escrever um script file (`.ps1` para PowerShell, `.bat` para cmd) e executar o script, evitando quoting manual. Para cmd, usar `.bat`:

```python
def show_terminal(self, shell: str = "powershell"):
    # Fechar terminal existente antes de abrir novo
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
            f"@echo off\n"
            f"node \"{OPENCLAUDE_BIN}\" --dangerously-skip-permissions\n",
            encoding="utf-8"
        )
        args = ["cmd", "/k", str(script_file)]
    else:
        script_file = run_dir / "openclaude_terminal.ps1"
        script_file.write_text(
            f"node '{OPENCLAUDE_BIN}' --dangerously-skip-permissions\n",
            encoding="utf-8"
        )
        args = ["powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", str(script_file)]

    self._terminal_proc = subprocess.Popen(
        args,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    logger.info(f"Terminal OpenClaude aberto ({shell})")
```

**Verificar após fix**: Abrir terminal cmd via Lumina não deve mais mostrar o erro de módulo node.

---

### BUG 2: `show_terminal` bloqueava quando terminal já estava aberto

**Status**: Parcialmente corrigido no BUG 1 (remover o early return e sempre fechar + reabrir).

Confirmar que o comportamento correto é: se já existe um terminal aberto, fecha e abre um novo. Isso está implementado no fix do BUG 1 acima.

---

### BUG 3: STT Corrections aprende entradas erradas

**Arquivo**: `data/stt_corrections.json`

**Sintoma**: O usuário disse "eu pedi pra você fechar, não abrir" → o LLM classificou como `correction` com `wrong="abrir"` e `right="fechar"` → o sistema aprendeu que "abrir" deve ser corrigido para "fechar" em todas as transcrições futuras. Isso vai quebrar todos os comandos que contenham a palavra "abrir".

**Fix**:
1. Abrir `data/stt_corrections.json` e remover entradas claramente erradas como `"abrir": "fechar"`
2. Verificar se há outras entradas suspeitas (pares muito curtos ou palavras comuns)
3. Adicionar validação em `stt_corrector.py` — método `add()` — para rejeitar correções de palavras com menos de 4 caracteres OU palavras que são verbos de ação comuns (lista curta: "abrir", "fechar", "criar", "fazer", "ir", "ver", "usar")

---

### BUG 4: Monitor sentinel dispara imediatamente após `run_visible`

**Arquivo**: `main.py`, método `_monitor_openclaude_sentinel`

**Sintoma**: Logo após o terminal abrir, a Lumina fala "OpenClaude terminou. Confere o resultado." — antes do OpenClaude ter feito qualquer coisa.

**Causa Provável**: O sentinel do run anterior (`data/run/done.sentinel`) ainda existe quando o novo `run_visible` é chamado. Apesar de `run_visible` chamar `sentinel_file.unlink(missing_ok=True)`, existe uma race condition: se o monitor de um run anterior ainda estava em `asyncio.sleep(1)` quando o novo `run_visible` foi chamado, ele pode ter acordado DEPOIS do novo sentinel ter sido escrito pelo script novo.

**Fix**: No início de `_monitor_openclaude_sentinel`, registrar o timestamp de início e só considerar sentinels escritos DEPOIS desse timestamp:

```python
async def _monitor_openclaude_sentinel(self):
    sentinel = Path(__file__).parent / "data" / "run" / "done.sentinel"
    start_time = time.time()
    for _ in range(300):
        await asyncio.sleep(1)
        if sentinel.exists():
            # Ignora sentinels de runs anteriores (escritos antes de começarmos a monitorar)
            try:
                mtime = sentinel.stat().st_mtime
                if mtime < start_time:
                    sentinel.unlink(missing_ok=True)
                    continue
            except OSError:
                continue
            try:
                sentinel.unlink()
            except OSError:
                pass
            await self._speak("OpenClaude terminou. Confere o resultado no terminal.")
            return
    await self._speak("OpenClaude ainda ta rodando. Me chama quando terminar.")
```

Adicionar `import time` no topo de `main.py` se não existir.

---

### BUG 5: Handler `_handle_openclaude_terminal` detecta "feche" mas ignora contexto

**Arquivo**: `main.py`, método `_handle_openclaude_terminal`

**Situação atual**: O handler recebe texto já classificado pelo DeepSeek como `terminal`. O DeepSeek retorna `{"type":"terminal","action":"open","shell":"cmd"}` ou `{"type":"terminal","action":"close"}`. O handler de `terminal` no LLM route em `_handle_llm_route` faz:

```python
elif intent_type == "terminal":
    action = intent.get("action", "open")
    shell = intent.get("shell", "powershell")
    await self._handle_openclaude_terminal(
        f"{'feche' if action == 'close' else 'abre'} {shell}", confidence
    )
```

Isso é convoluto — cria um texto fake só para repassar pro handler que vai fazer keyword matching de novo. Simplificar:

```python
elif intent_type == "terminal":
    action = intent.get("action", "open")
    shell = intent.get("shell", "powershell")
    oc = self.modules.get('openclaude')
    if not oc:
        await self._speak("OpenClaude não está disponível.")
    elif action == "close":
        closed = oc.hide_terminal()
        await self._speak("Terminal fechado." if closed else "Não tenho nenhum terminal aberto que eu possa fechar.")
    else:
        already_open = oc._terminal_proc and oc._terminal_proc.poll() is None
        oc.show_terminal(shell=shell)
        await self._speak(f"Terminal aberto em {shell}." if not already_open else f"Troquei para terminal {shell}.")
```

---

### BUG 6: `_handle_openclaude_terminal` ainda existe com keyword matching obsoleto

Com o BUG 5 corrigido (terminal sendo roteado diretamente via LLM intent), o método `_handle_openclaude_terminal` só é chamado do `_handle_llm_route` via o bloco `terminal`. O método pode ser simplificado ou removido — mover a lógica inline para o bloco `terminal` em `_handle_llm_route`.

Verificar se `_handle_openclaude_terminal` ainda é registrado como handler em `_setup_callbacks`:
```python
hearing.register_command_handler("openclaude", self._handle_openclaude_terminal)
```
**Este registro pode ser removido** — agora tudo passa pelo `llm_route`. Se removido, o handler "openclaude" nunca será chamado diretamente pelo command_processor (que já não classifica mais como "openclaude").

---

## Após Todos os Bugs Corrigidos

### 1. Limpar `data/stt_corrections.json`

Abrir o arquivo, mostrar o conteúdo, remover entradas inválidas.

### 2. Testar mentalmente o fluxo

Para cada bug, raciocinar: "Se o usuário falar X, o que acontece agora?" Confirmar que o comportamento está correto.

### 3. Atualizar Vault Obsidian

**Arquivo**: `C:\Users\Adria\Documents\Documentation\Dev-lumina-agent\MAPA.md`

Atualizar as seções:
- Estado atual dos módulos (openclaude_subprocess, command_processor, main.py)
- Bugs resolvidos nesta sessão
- Decisões técnicas tomadas (por que removemos keyword matching de terminal; por que usamos sentinel com timestamp; etc.)

**Arquivo**: `C:\Users\Adria\Documents\Documentation\Dev-lumina-agent\02_ATIVO\PENDENCIAS.md`

Remover os bugs corrigidos. Adicionar se houver pendências novas identificadas.

### 4. Atualizar memória Claude

Escrever/atualizar os arquivos em `C:\Users\Adria\.claude\projects\C--Users-Adria-Documents-lumina-agent\memory\`:

- `project_lumina_state.md` — estado atual do projeto pós-fix
- `feedback_architecture.md` — aprendizado: keyword matching para roteamento é frágil; usar LLM para classificação é mais robusto
- Atualizar `MEMORY.md` com ponteiros corretos

---

## Instruções de Execução

1. Leia este documento inteiro antes de começar
2. Corrija os bugs NA ORDEM LISTADA (1, 2, 3, 4, 5, 6)
3. Após cada bug: leia o arquivo afetado, faça o edit, confirme que não quebrou nada óbvio
4. Não refatore código fora do escopo de cada bug
5. Não crie arquivos de documentação extras além dos listados acima
6. Se encontrar um bug não listado durante o trabalho, anote mas não corrija — foque nos listados
7. Ao final, atualize vault e memória conforme seção "Após Todos os Bugs Corrigidos"

## Arquivos Chave para Ler Antes de Começar

- `main.py` (completo)
- `src/integrations/openclaude_subprocess.py` (completo)
- `src/voice/command_processor.py` (completo)
- `src/voice/stt_corrector.py` (completo)
- `data/stt_corrections.json` (se existir)
- `C:\Users\Adria\Documents\Documentation\Dev-lumina-agent\MAPA.md`
