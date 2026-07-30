# API Design

Stage 028 adds dependency-free API facades for paper trading state and safe
operator controls. These contracts are framework-neutral so a future HTTP or UI
adapter can wrap them without coupling to paper-engine internals.

## Paper Trading API

`src/abtp/api/paper.py` exposes:

- `PaperTradingAPI.status()` for current paper state
- `PaperTradingAPI.trades()` for simulated paper trades
- `PaperTradingAPI.cycles()` for decision-cycle audit inspection
- `pause()`, `resume()`, and `activate_kill_switch()` as safe controls

The API response includes current BTC price, active regime, latest signal,
latest risk decision, blocked-trade reason, data health, portfolio state,
drawdown, parameter health, cycle count, trade count, and control state.

## Authorization

Stage 028 uses role-based request context objects instead of API keys or stored
secrets:

- `paper:read` can inspect status, trades, and cycles
- `paper:control` can pause, resume, or activate the paper kill switch

No credentials are printed, logged, persisted, or inferred. Future web adapters
may map real authentication into these roles.

## Safety Limits

The API cannot submit orders. Direct order submission raises
`UnsafePaperActionError`. Paper trades can only originate from the Stage 027
paper engine after strategy evaluation, risk approval, and paper-safe execution.

The Stage 028 kill switch is intentionally one-way in this API layer. Clearing
it should be introduced only by a later explicit stage with stronger operator
confirmation and audit requirements.

Stage 028 remains paper-only and cannot enable live execution.

## Local Dashboard Adapter

`src/abtp/dashboard/paper_server.py` provides a standard-library local HTTP
adapter for the paper dashboard. It exposes `/`, `/api/status`, `/paper-report`,
and paper-only POST actions for approval logging, rejection logging, pause,
resume, and emergency stop. Approval is available only for an already
risk-approved simulated paper fill; risk-rejected recommendations cannot be
approved.
