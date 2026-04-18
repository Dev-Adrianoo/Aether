# Architecture Refactor Tasks

Goal: keep Lumina fast, safe, and extensible before the routing layer turns into a large conditional blob.

## Review Checklist For Each Task

- No deadlocks or unbounded waits introduced.
- No hardcoded user paths; config must come from `config.py` or injected dependencies.
- The changed module has a clear single responsibility.
- The integration path is explicit and easy to test.
- Existing behavior remains covered by tests.
- New command behavior has a focused unit/integration test.
- Runtime/generated data is not added to Git.

## Task 1 - Extract ActionGate

Status: done

Move executable-intent safety checks out of `IntentRouter` into `src/brain/action_gate.py`.

Why:
- Action safety policy is independent from routing and handler execution.
- It is a pure function/class and should be easy to test.
- It reduces the risk of adding more safety conditions directly into `IntentRouter`.

Review:
- No async waits introduced.
- No config/path dependencies.
- Executable intent set stays explicit in `ActionGate.executable_intents`.
- Tests: `tests/unit/test_action_gate.py`, `tests/unit/test_intent_router_learning.py`.
- Review result: integrates through `IntentRouter._action_gate`; no deadlock risk; no hardcoded paths.

## Task 2 - Extract Conversation State

Status: done

Move recent-turn memory, last assistant text, and pending confirmation detection out of `IntentRouter`.

Why:
- Conversation memory is state management, not intent dispatch.
- Pending confirmations need isolated tests because they can accidentally execute actions.

Review:
- Bounded memory size via `ConversationState(max_turns=6)`.
- No long-lived task, lock, filesystem, config, or network access.
- Confirmation phrases remain conservative and tested.
- Tests: `tests/unit/test_conversation_state.py`, `tests/unit/test_intent_router_learning.py`.
- Review result: integrates through `IntentRouter._conversation_state`; action execution remains in `IntentRouter`.

## Task 3 - Extract FastCommandRouter

Status: done

Move deterministic commands such as screenshot requests out of `IntentRouter`.

Why:
- Common commands should not call DeepSeek.
- STT misreads in Brazilian Portuguese should be handled before LLM routing.

Review:
- No broad command execution; router only returns `FastCommand`.
- No filesystem/config/async dependencies.
- Monitor mapping is explicit: default/left = 1, right = 2.
- Ambiguous first-person narrative falls through unless it also asks Lumina to answer/analyze.
- Tests: `tests/unit/test_fast_command_router.py`, `tests/unit/test_intent_router_learning.py`.
- Review result: integrates through `IntentRouter._fast_command_router`; LLM bypass is limited to screenshot requests.

## Task 4 - Split Domain Handlers

Status: done

Extract screenshot, terminal, UI action, learning, task, and code-agent handlers incrementally.

Why:
- `IntentRouter` should orchestrate, not own all behavior.

Review:
- All handlers extracted to `src/brain/handlers/`:
  - `ui_action_handler.py` — click com feedback honesto (attempt → success/failure)
  - `terminal_handler.py` — abrir/fechar terminal via openclaude; openclaude expõe `is_terminal_open()`
  - `learning_handler.py` — alias, preferência, forget, list, confirm; estado `_pending_learning` interno
  - `task_handler.py` — extrai tarefa por keyword, confirma via LLM
  - `code_agent_handler.py` — code_agent, action dispatch, app self-learning, sentinel polling
- Dependencies are injected in all handlers (speak, modules, optional fns).
- Handlers have no config imports at module level; use local imports where needed.
- `IntentRouter` now orchestrates only: delegates to handler, checks `has_pending_*` properties.
- Tests: 161 passing (2026-04-18).
- Known pending: `Path.home() / "Documents"` in `code_agent_handler.py` (tracked in Task 6).

## Task 5 - Runtime Safety Review

Status: in progress

Review async tasks and runtime files after extraction.

Focus:
- `asyncio.create_task` monitor flows.
- Sentinel cleanup.
- Shutdown/cancel behavior.
- Generated files under `data/`.

Initial review after Tasks 1-4:
- New extracted modules (`ActionGate`, `ConversationState`, `FastCommandRouter`, `UIActionHandler`) introduce no async tasks, sleeps, locks, filesystem access, or network access.
- Existing runtime risks remain in `IntentRouter`: OpenClaude sentinel polling and learned-path polling use `asyncio.create_task` + `wait_for`.
- Existing dynamic-config issue remains: fallback working directory uses `Path.home() / "Documents"` in code. This is not newly introduced, but should move to `config.py`.

## Task 6 - Dynamic Configuration Review

Status: pending

Search for hardcoded paths, device IDs, model names, and executable locations.

Expected:
- Local machine values stay in `.env`.
- Defaults live in `config.py`.
- Runtime-generated files are ignored or intentionally tracked.

Known findings:
- `Path.home() / "Documents"` appears in `IntentRouter` and `openclaude_subprocess.py`.
- CUDA DLL names are intentionally static because they are versioned runtime library names (`cublas64_12.dll`, `cudnn64_9.dll`), not local paths.
