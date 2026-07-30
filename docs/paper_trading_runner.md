# Paper Trading Runner

Stage 072 adds a deterministic paper-trading runner that connects the existing
paper account, strategy, Risk Management Engine, paper-safe execution, command
center, audit, metrics, and summary contracts into complete simulated cycles.
It is a paper-only loop. It does not create live orders, call live exchange
trading endpoints, mutate real account state, or enable live trading.

## Cycle Contract

Each `PaperTradingCycleInput` contains a normalized market snapshot, the Stage
071 command-center recommendation, stop-loss metadata, risk and safety flags,
and source references for audit reconstruction. The runner performs fail-closed
preflight checks before it routes anything to the existing paper engine.

A cycle is skipped when live mode is requested, live credentials are present,
safe mode is off, the command label is not `BUY REVIEW`, stop-loss metadata is
missing, a kill switch is active, market data is stale, exchange health blocks
new entries, capital protection blocks entries, or a portfolio loss halt is
active. Skipped cycles still emit deterministic audit payloads and local
metrics.

If preflight passes, the existing paper engine receives the market snapshot.
The engine can still produce no signal, a Risk Management Engine rejection, or a
simulated paper fill. `BUY REVIEW` is necessary but not sufficient: a strategy
signal, risk approval, conservative sizing, and stop-loss metadata are still
required before any simulated fill can be created.

## Session Contract

`PaperTradingRunner.run_session()` processes a deterministic sequence of cycle
inputs and returns `PaperTradingSessionSummary`. The summary records cycle
counts, executed counts, blocked counts, risk rejections, no-signal cycles,
starting and ending equity, realized P/L, fees, blocked-reason distribution,
plain-language status, and an audit payload.

## Operating Limits

- The default session mode is paper with `SAFE_MODE=true`.
- Live credentials are forbidden for the runner.
- The runner cannot submit, cancel, or create live orders.
- The runner cannot approve risk or bypass the Risk Management Engine.
- The runner cannot change strategy, risk, portfolio, or production
  configuration automatically.
- Results are deterministic fixtures suitable for research, paper review, and
  audit reconstruction only.

ABTP does not guarantee profit. Paper trading is simulated evidence, not proof
that real trading will succeed. Only risk capital may ever be considered in a
later explicit live stage.
