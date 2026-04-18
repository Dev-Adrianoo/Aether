# Lumina Agent

Lumina is a voice-first development assistant that listens, speaks, reads the screen, routes intent, and can delegate heavier system/code tasks to OpenClaude. The current goal is not to be a generic chatbot, but a local "Jarvis-style" development companion that can stay in conversation mode while avoiding accidental command execution.

## Current Status

Lumina is in an active prototype stage. The core architecture has been refactored into separate modules for configuration, voice, vision, intent routing, actions, integrations, and safe learning.

Stable today:

- Voice loop with wake word support.
- Speech-to-text through Groq Whisper when configured, with Google Speech fallback.
- Text-to-speech responses.
- Screenshot capture and basic screen context handling.
- DeepSeek/OpenAI-compatible LLM integration.
- OpenClaude subprocess integration for heavier code/system work.
- Centralized configuration through `config.py` and `.env`.
- Dynamic intent loading through `src/intents/intents.yaml`.
- Dynamic action registry through `src/actions/actions.yaml`.
- Action Gate to reduce accidental execution while keeping conversation mode active.
- Safe self-learning for aliases and preferences, with explicit confirmation.

Experimental or future:

- UI control through PyAutoGUI is present but should remain guarded.
- `learned_locations.yaml` and `learned_commands.yaml` are placeholders only; the runtime does not use them yet.
- Vision-language model routing is still a design topic, not a finished feature.
- LuminaXR/Quest integration is a future server/client phase.

## Architecture

```text
lumina-agent/
|-- config.py                  # Centralized environment/config loader
|-- main.py                    # Runtime entry point
|-- src/
|   |-- actions/               # Dynamic actions and task storage
|   |-- brain/                 # IntentRouter and Obsidian context
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

### Intent Routing

Intent classification is handled by `src/brain/intent_router.py`. Intent definitions live in `src/intents/intents.yaml`, so new language-level intents can be adjusted without editing `main.py`.

Current learning-related intents include:

- `learn_alias`
- `learn_preference`
- `forget_alias`
- `list_learning`

Not implemented yet:

- `learn_location`
- `learn_command`
- `forget_learning` as a generic umbrella command

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
Lumina, take a screenshot.
Lumina, what do you see on my right monitor?
Lumina, open YouTube.
Lumina, remember that "open my dev vault" means "open Obsidian".
Lumina, list what you learned.
```

## Tests

Run the default suite:

```powershell
python -m pytest -q
```

Current validated result:

```text
64 passed
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

- Improve conversation mode without losing continuous listening.
- Continue tightening Action Gate behavior.
- Expand tests around intent routing, screenshots, and voice edge cases.
- Improve OpenClaude status visibility and sentinel handling.

Later:

- Safe `learn_location`.
- Safe `learn_command`.
- Better visual understanding pipeline.
- Guarded UI control through PyAutoGUI.
- LuminaXR client/server integration for Meta Quest.

## License

Private project. All rights reserved.
