# Lumina Agent

Lumina is a voice-first development assistant that listens, speaks, reads the screen, routes intent, and can delegate heavier system/code tasks to OpenClaude. The current goal is not to be a generic chatbot, but a local "Jarvis-style" development companion that can stay in conversation mode while avoiding accidental command execution.

## Current Status

Lumina is in an active prototype stage. The core architecture has been refactored into separate modules for configuration, voice, vision, intent routing, actions, integrations, and safe learning.

Stable today:

- Voice loop with wake word support.
- Local speech-to-text through `faster-whisper` when available, with Groq Whisper and Google Speech fallback.
- Text-to-speech responses.
- Screenshot capture and basic screen context handling.
- DeepSeek/OpenAI-compatible LLM integration.
- OpenClaude subprocess integration for heavier code/system work.
- Centralized configuration through `config.py` and `.env`.
- Dynamic intent loading through `src/intents/intents.yaml`.
- Dynamic action registry through `src/actions/actions.yaml`.
- Action Gate to reduce accidental execution while keeping conversation mode active.
- Safe self-learning for aliases and preferences, with explicit confirmation.
- Short conversational context and pending-confirmation handling for follow-up replies such as "yes, I accept".
- Dynamic audio device fallback for switching between Meta Quest and desk microphones.

Experimental or future:

- UI control through PyAutoGUI is present but should remain guarded.
- `learned_locations.yaml` and `learned_commands.yaml` are placeholders only; the runtime does not use them yet.
- Vision-language model routing is still a design topic, not a finished feature.
- Local STT needs real voice benchmarking across `turbo`, `large-v3`, and compute modes.
- LuminaXR/Quest integration is a future server/client phase.

## Architecture

```text
lumina-agent/
|-- config.py                  # Centralized environment/config loader
|-- main.py                    # Runtime entry point
|-- src/
|   |-- actions/               # Dynamic actions and task storage
|   |-- brain/
|   |   |-- intent_router.py   # Orchestrator: classifies intent, delegates to handlers
|   |   |-- action_gate.py     # Blocks execution when speech sounds like narrative/question
|   |   |-- conversation_state.py  # Short-term turn memory and pending confirmations
|   |   |-- fast_command_router.py # Deterministic screenshot bypass (no LLM)
|   |   |-- handlers/          # Domain handlers, one per responsibility
|   |   |   |-- ui_action_handler.py
|   |   |   |-- terminal_handler.py
|   |   |   |-- learning_handler.py
|   |   |   |-- task_handler.py
|   |   |   `-- code_agent_handler.py
|   |   `-- obsidian_manager.py
|   |-- integrations/          # DeepSeek/OpenClaude clients
|   |-- intents/               # Intent definitions loaded from YAML
|   |-- learning/              # Safe alias/preference learning
|   |-- vision/                # Screenshot capture
|   `-- voice/                 # STT, TTS, wake word, command processing
|-- tests/
|   |-- integration/
|   `-- unit/
|-- scripts/                   # Utility scripts
|-- data/                      # Generated local runtime data
`-- docs/                      # Project documentation
```

## Core Concepts

### Conversation Mode

Lumina is intentionally allowed to listen beyond strict command phrases. This keeps the assistant useful as a conversational companion, but it creates a risk: noise, fragments, or casual speech can be misclassified as commands.

The current mitigation is the Action Gate inside the intent routing layer. It blocks sensitive actions such as terminal execution, code-agent delegation, UI actions, and system actions unless the user phrase is direct enough.

The router also keeps a small recent-turn context and explicit pending confirmations. This lets short replies such as "sim", "yes, I accept", or "pode" answer Lumina's previous question without relying on a full LLM reclassification.

### Speech Recognition

The preferred STT path is local `faster-whisper`:

- `LUMINA_STT_BACKEND=auto` tries local Whisper first, then Groq, then Google Speech.
- `LUMINA_LOCAL_WHISPER_MODEL=turbo` is the current default for RTX-class GPUs.
- `LUMINA_LOCAL_WHISPER_DEVICE=cuda` uses NVIDIA acceleration.
- `LUMINA_LOCAL_WHISPER_COMPUTE_TYPE=float16` is the default CUDA precision.
- `LUMINA_LOCAL_WHISPER_CACHE_DIR=./data/models/huggingface` keeps downloaded model files inside the local workspace.

Groq remains useful as a fallback when local model initialization fails. Google Speech is the last fallback.

`src/voice/stt_corrector.py` contains local correction rules for common Brazilian Portuguese command-transcription mistakes, plus user-learned corrections in `data/stt_corrections.json`.

### Intent Routing

`src/brain/intent_router.py` is a pure orchestrator. It classifies intent via LLM and delegates execution to a focused handler. It owns no domain logic itself.

The routing pipeline:

1. `FastCommandRouter` intercepts deterministic commands (e.g. screenshot phrases in Brazilian Portuguese) before the LLM is called.
2. The LLM classifies remaining input into a typed intent using `src/intents/intents.yaml`.
3. `ActionGate` blocks executable intents when the speech sounds like narrative, question, or brainstorming.
4. `IntentRouter` dispatches to the correct handler:
   - `UIActionHandler` — click a named screen element
   - `TerminalHandler` — open or close a terminal
   - `LearningHandler` — learn/forget aliases and preferences
   - `TaskHandler` — write a task note
   - `CodeAgentHandler` — delegate to OpenClaude, dispatch registered actions, or trigger app self-learning

Each handler encapsulates its own state (pending confirmations, run IDs) and is independently testable without audio or voice.

Current learning-related intents: `learn_alias`, `learn_preference`, `forget_alias`, `list_learning`.

Not implemented yet: `learn_location`, `learn_command`.

### Action Registry

System actions are declared in `src/actions/actions.yaml` and loaded by `src/actions/action_loader.py`.

Supported action types include:

- `url`
- `exe`
- `exe_vault`
- task/logging helpers

Unknown or incomplete executable targets should not be guessed silently. The intended flow is confirmation first, then an assisted lookup/update.

### Safe Self-Learning

The active self-learning layer is intentionally narrow.

Implemented:

- Exact normalized voice aliases.
- Simple preferences.
- Explicit confirmation before writing.
- Alias rewriting before LLM intent classification.

Files:

- `src/learning/learning_manager.py`
- `src/learning/learned_aliases.yaml`
- `src/learning/learned_preferences.yaml`

Placeholders for future design:

- `src/learning/learned_locations.yaml`
- `src/learning/learned_commands.yaml`

Those placeholder files exist to document direction, not to enable command execution.

## Requirements

- Python 3.9+
- Windows is the primary development target.
- Microphone and speakers/headset.
- NVIDIA GPU is recommended for local Whisper. The current development machine validates `faster-whisper` with `turbo/cuda/float16`.
- OpenClaude installed locally if you want code-agent delegation.
- Tesseract OCR installed if OCR features are used.

Install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

For tests:

```powershell
pip install -r requirements_dev.txt
```

## Configuration

Copy `.env.example` to `.env` and fill the values you need.

Important variables:

```dotenv
LUMINA_USER_NAME=Adriano
LUMINA_WAKE_WORD=lumina
LUMINA_POST_TTS_MUTE_SECONDS=0.25
LUMINA_WAKE_COOLDOWN_SECONDS=0.4

LUMINA_STT_BACKEND=auto
LUMINA_LOCAL_WHISPER_MODEL=turbo
LUMINA_LOCAL_WHISPER_DEVICE=cuda
LUMINA_LOCAL_WHISPER_COMPUTE_TYPE=float16
LUMINA_LOCAL_WHISPER_CACHE_DIR=./data/models/huggingface

GROQ_API_KEY=

OPENCLAUDE_API_KEY=
OPENCLAUDE_BASE_URL=https://api.deepseek.com/v1
OPENCLAUDE_MODEL=deepseek-chat
OPENCLAUDE_BIN=
OPENCLAUDE_SENTINEL_TIMEOUT=300

OBSIDIAN_VAULT_PATH=
OBSIDIAN_DEV_VAULT=

TTS_ENGINE=edge-tts
TTS_VOICE=pt-br
```

Do not hardcode user-specific paths in Python modules. Put local paths in `.env` and read them through `config.py`.

## Running Lumina

```powershell
python .\main.py
```

Typical voice examples:

```text
Lumina, tira print da tela direita e me fala o que tem nela.
Lumina, abre o terminal.
Lumina, clique no botão Yes, I accept.
Lumina, aprende que "abre meu vault dev" significa "abre Obsidian".
Lumina, lista seus aprendizados.
```

## Tests

Run the default suite:

```powershell
python -m pytest -q
```

Current validated result:

```text
161 passed
```

Compile check used during recent refactors:

```powershell
python -m py_compile main.py src\brain\intent_router.py src\intents\intent_loader.py
```

## Obsidian Vault

The project uses an Obsidian vault as a working memory and planning layer. The active project map is expected under the development vault configured by `.env`.

Important notes:

- The vault is documentation and context, not a replacement for tests.
- Recent sessions can be injected as context to improve continuity.
- If the project map grows too large or Lumina starts ignoring vault context, semantic memory integration should be investigated before adding more raw text.

## Safety Rules

- Conversation should not automatically become execution.
- Any learned behavior that can affect the system must require explicit confirmation.
- Learned aliases may rewrite text, but execution still goes through the normal IntentRouter and Action Gate.
- Future learned commands must use allowlists or manual review before becoming executable.
- OpenClaude subprocess execution should have a timeout and visible status handling.

## Roadmap

Short term:

- Benchmark local STT in real voice sessions: `turbo` vs `large-v3`, `float16` vs `int8_float16`, and latency after first model load.
- Improve capture/VAD so short follow-up commands are not clipped after TTS.
- Continue tightening Action Gate behavior around Brazilian Portuguese phrasing and STT misreads.
- Expand tests around local STT initialization, pending confirmations, screenshot requests, and voice edge cases.
- Improve OpenClaude status visibility and sentinel handling.

Later:

- Safe `learn_location`.
- Safe `learn_command`.
- Better visual understanding pipeline.
- Guarded UI control through PyAutoGUI.
- LuminaXR client/server integration for Meta Quest.

## License

Private project. All rights reserved.
