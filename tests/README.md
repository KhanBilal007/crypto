# Testing

ABTP tests must be deterministic and credential-free.

## Rules

- Do not call real exchange APIs from unit tests.
- Do not require `.env` files, API keys, wallets, or account balances.
- Prefer fixtures and explicit timestamps.
- Verify safety defaults whenever runtime configuration changes.
- Keep tests aligned with the same commands used in CI.

## Commands

```powershell
python -m pytest
python -m ruff format --check .
python -m ruff check .
python -m mypy src
```

