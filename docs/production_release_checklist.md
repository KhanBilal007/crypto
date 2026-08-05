# Production Release Checklist

Stage 073 readiness is controlled, minimum-risk readiness. It is not approval
for unsupervised live trading.

## Verification

- [x] Fresh environment installs with `python -m pip install -e ".[dev]"`.
- [x] `.\.venv\Scripts\python.exe -m pytest` passes.
- [x] `.\.venv\Scripts\python.exe -m ruff format --check .` passes.
- [x] `.\.venv\Scripts\python.exe -m ruff check .` passes.
- [x] `.\.venv\Scripts\python.exe -m mypy src` passes.
- [x] Database migrations recreate the schema from scratch.
- [x] Backup and restore drill preserves audit reconstruction.
- [x] `docs/source_material/ABTP_Sequential_Codex_Execution_Plan.md` Final
      Readiness Gate references all implemented stages through Stage 073.
- [x] Paper runner sessions produce deterministic executed, skipped,
      no-signal, risk-rejected, audit, and metrics evidence.
- [x] Paper evaluation gate reports remain paper, make more conservative,
      pause for review, or future tiny-live proposal eligibility without
      enabling live trading.

## Trader-Ready Adaptive UI

- [x] Stage A Adaptive View Shell implemented with persisted UI mode
      preference.
- [x] Stage B Beginner View implemented with plain-language command, portfolio,
      transaction, and glossary sections.
- [x] Stage C Advanced Trader View implemented with chart payload, metrics,
      exit review, and exports.
- [x] Stage D Strategy Lab implemented with strategy profile routing,
      selectors, required evidence, and run comparison.
- [x] Stage E Persistence Upgrade implemented with SQLite paper ledger tables
      and JSON fallback/export compatibility.
- [x] Stage F Trader Readiness Gate implemented at `/api/readiness` and in the
      dashboard UI.
- [x] Trader review handoff implemented at `/trader-handoff.md` and documented
      in `docs/trader_review_handoff.md`.
- [x] Trader evidence bundle implemented at `/trader-evidence.json` for
      machine-readable readiness and audit review.
- [x] Trader Feedback panel implemented for local paper-only reviewer
      corrections with SQLite-backed evidence rows.
- [x] Trader feedback CSV export implemented at `/trader-feedback.csv`.
- [x] Open blocker-severity trader feedback blocks paper-demo readiness until
      closed.
- [x] Closing blocker-severity trader feedback requires a resolution note for
      audit handoff.
- [x] Adaptive UI acceptance gate passed on 2026-08-01: full `pytest`, Ruff
      format/check, and mypy over `src`.
- [x] Generated runtime dashboard files are local artifacts and are ignored by
      git: `docs/paper_dashboard.sqlite` and
      `docs/paper_dashboard_state.json`.

## Minimum-Risk Gates

- [x] `SAFE_MODE=true` by default.
- [x] Default profile is paper or research.
- [x] `ABTP_ENABLE_LIVE_TRADING=false` by default.
- [ ] No real exchange or external provider calls are added outside adapters.
- [x] No order path bypasses the Risk Management Engine.
- [x] Leverage, margin, futures, options, withdrawals, transfers, and admin API
      scopes remain blocked.
- [x] Live gateway requires explicit flags, preflight, manual approval, and a
      risk-approved `OrderIntent`.
- [ ] Automation is disabled unless evidence gates pass and can be stopped
      instantly.
- [x] Critical alert failure blocks live-mode trading.
- [x] Confidence, research, governance, and institutional decision records are
      advisory and cannot bypass the Risk Management Engine.
- [x] Paper command-center BUY REVIEW labels are paper-only and cannot create
      signals, approve risk, create orders, or enable live trading.
- [x] Paper runner BUY REVIEW handling remains necessary but not sufficient:
      strategy signal, risk approval, sizing, stop-loss metadata, and safety
      flags must still pass before simulated fills.
- [x] Paper evaluation future tiny-live eligibility is evidence for a later
      supervised proposal only; it is not live approval.

## Documentation

- [x] `docs/trader_ready_adaptive_ui_plan.md` reviewed for beginner,
      advanced-trader, and strategy-specific dashboard behavior.
- [x] `docs/trader_review_handoff.md` documents paper-only trader review scope.
- [ ] `docs/final_integration.md` reviewed.
- [ ] `docs/user_guide.md` reviewed.
- [ ] `docs/deployment.md` reviewed.
- [ ] `docs/incident_response.md` reviewed.
- [x] `docs/architecture.md` matches the current stage.
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
