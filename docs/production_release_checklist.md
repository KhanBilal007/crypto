# Production Release Checklist

Stage 073 readiness is controlled, minimum-risk readiness. It is not approval
for unsupervised live trading.

## Verification

- [ ] Fresh environment installs with `python -m pip install -e ".[dev]"`.
- [ ] `.\.venv\Scripts\python.exe -m pytest` passes.
- [ ] `.\.venv\Scripts\python.exe -m ruff format --check .` passes.
- [ ] `.\.venv\Scripts\python.exe -m ruff check .` passes.
- [ ] `.\.venv\Scripts\python.exe -m mypy src` passes.
- [ ] Database migrations recreate the schema from scratch.
- [ ] Backup and restore drill preserves audit reconstruction.
- [ ] `docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md` Final
      Readiness Gate references all implemented stages through Stage 073.
- [ ] Paper runner sessions produce deterministic executed, skipped,
      no-signal, risk-rejected, audit, and metrics evidence.
- [ ] Paper evaluation gate reports remain paper, make more conservative,
      pause for review, or future tiny-live proposal eligibility without
      enabling live trading.

## Minimum-Risk Gates

- [ ] `SAFE_MODE=true` by default.
- [ ] Default profile is paper or research.
- [ ] `ABTP_ENABLE_LIVE_TRADING=false` by default.
- [ ] No real exchange or external provider calls are added outside adapters.
- [ ] No order path bypasses the Risk Management Engine.
- [ ] Leverage, margin, futures, options, withdrawals, transfers, and admin API
      scopes remain blocked.
- [ ] Live gateway requires explicit flags, preflight, manual approval, and a
      risk-approved `OrderIntent`.
- [ ] Automation is disabled unless evidence gates pass and can be stopped
      instantly.
- [ ] Critical alert failure blocks live-mode trading.
- [ ] Confidence, research, governance, and institutional decision records are
      advisory and cannot bypass the Risk Management Engine.
- [ ] Paper command-center BUY REVIEW labels are paper-only and cannot create
      signals, approve risk, create orders, or enable live trading.
- [ ] Paper runner BUY REVIEW handling remains necessary but not sufficient:
      strategy signal, risk approval, sizing, stop-loss metadata, and safety
      flags must still pass before simulated fills.
- [ ] Paper evaluation future tiny-live eligibility is evidence for a later
      supervised proposal only; it is not live approval.

## Documentation

- [ ] `docs/final_integration.md` reviewed.
- [ ] `docs/user_guide.md` reviewed.
- [ ] `docs/deployment.md` reviewed.
- [ ] `docs/incident_response.md` reviewed.
- [ ] `docs/architecture.md` matches the current stage.
- [ ] `docs/institutional_decision_hub.md` reviewed.
- [ ] `docs/simple_paper_command_center.md` reviewed.
- [ ] `docs/paper_trading_runner.md` reviewed.
- [ ] `docs/paper_evaluation_gate.md` reviewed.
- [ ] Known operating limits and assumptions are documented.

## Operator Acknowledgement

- [ ] ABTP does not guarantee profit.
- [ ] Cryptocurrency trading is risky.
- [ ] Only risk capital may be used.
- [ ] Live trading remains disabled unless a later explicit live-release review
      approves the exact environment, credentials, limits, and procedures.
- [ ] The operator knows how to activate kill switches and restore from backup.
