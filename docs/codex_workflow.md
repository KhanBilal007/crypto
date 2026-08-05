# Codex Workflow

## Stage Discipline

Each ABTP stage should be implemented narrowly:

1. Read the source documents and existing repository state.
2. Preserve user work and local project patterns.
3. Implement only the requested stage.
4. Add or update deterministic tests.
5. Run the documented verification commands.
6. Report created or modified files, commands run, risks, and assumptions.

## Engineering Standards

- Prefer clear interfaces and immutable data contracts for cross-module data.
- Keep exchange-specific behavior inside exchange adapter modules.
- Keep order execution behind the Risk Management Engine.
- Avoid credentials, network calls, and nondeterminism in unit tests.
- Prefer environment variables for runtime configuration.
- Record decision inputs, generated signals, risk checks, order intents, and
  audit events for explainability.

## Local Quality Gate

Run these before handing off a stage:

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
```

For CI, use the same commands so local and remote behavior match.

## Configuration Rules

- `SAFE_MODE=true` is the default.
- `ABTP_ENABLE_LIVE_TRADING=false` is the default.
- Unit tests must pass without `.env` files or exchange credentials.
- Any future production credential must be read only by the owning adapter or
  infrastructure module.

## Completion Report Template

Use this shape for stage completion:

```text
Created/modified:
- path: concise purpose

Tests run:
- command: result

Remaining risks:
- risk or none known

Assumptions:
- assumption or none
```

