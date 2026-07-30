# User Guide

This guide is for local controlled operation of ABTP after Stage 034. It assumes
the repository has already been cloned and that no real exchange credentials are
needed for tests.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy `.env.example` only as a local starting point. Keep `SAFE_MODE=true` and
`ABTP_ENABLE_LIVE_TRADING=false` unless a later reviewed live stage explicitly
requires otherwise.

## Verification Gate

Run this gate before trusting any local change:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src
```

The test suite is deterministic and does not require live exchange credentials,
news providers, on-chain providers, or external notification accounts.

## Paper Operation

Paper trading consumes live-like snapshots and simulated fills. Operators can
inspect:

- paper state through `PaperTradingAPI.status`
- deterministic dashboard text through `render_paper_dashboard`
- simulated trades through `PaperTradingAPI.trades`
- decision cycles through `PaperTradingAPI.cycles`
- audit trails through `DecisionAuditRecorder.reconstruct`

Paper controls expose pause and kill-switch state. They do not create real
orders and do not connect to exchanges.

## Safety Checks

Before any controlled run, confirm:

- `SAFE_MODE=true`
- `ABTP_TRADING_MODE=paper`, `research`, or `backtest`
- `ABTP_ENABLE_LIVE_TRADING=false`
- no withdrawal, transfer, margin, futures, options, or admin exchange-key
  scopes are configured
- data health is trusted
- the latest risk decision is explicit and auditable
- incident-response and backup steps are available

## Reading The Project

Start with:

- `docs/architecture.md` for module boundaries
- `docs/final_integration.md` for the integrated lifecycle
- `docs/production_release_checklist.md` for readiness gates
- `docs/incident_response.md` for stop and recovery steps
- `docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md` for the staged
  implementation source plan

ABTP is a controlled engineering platform, not a profit claim. Treat outputs as
research, paper-trading, or supervised-risk context until future stages and
human review explicitly approve more.
