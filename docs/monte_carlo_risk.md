# Monte Carlo Risk Simulator

Stage 044 adds deterministic-seeded Monte Carlo risk simulation for stress
testing strategy or portfolio return assumptions.

## Scope

The simulator consumes supplied return samples, position-size assumptions,
bounded fee/slippage ranges, a horizon, a trial count, and a deterministic
random seed. It creates capital paths and summarizes drawdown, tail loss,
survival probability, and risk of ruin.

The module does not create strategy signals, risk approvals, order intents,
exchange calls, external provider calls, order execution, or live trading
behavior.

## Contracts

- `SimulationAssumptions` defines starting equity, return samples, horizon,
  trial count, seed, position size, cost ranges, ruin threshold, volatility
  regime, and source references.
- `ScenarioPath` records a deterministic simulated equity path with per-step
  sampled return, fee, slippage, net return, equity, drawdown, tail loss, and
  survival state.
- `TailRiskSummary` aggregates worst ending return, 5th-percentile return,
  expected shortfall, 95th-percentile drawdown, maximum drawdown, survival
  probability, and risk of ruin.
- `MonteCarloRiskReport` packages assumptions, limits, paths, tail-risk
  summary, rejection reasons, allocation multiplier, quality status, and audit
  payload.

## Safety Behavior

Unsafe survival probability, excessive drawdown, large tail loss, or high risk
of ruin produces rejection reasons and `allocation_multiplier=0`. Softer
survival concerns can produce a reduced allocation multiplier. These outputs
are advisory risk evidence only and require later strategy, risk, and execution
controls before any action.

## Determinism

Tests and local research should supply explicit seeds and deterministic return
fixtures. Fee and slippage values are sampled from bounded ranges using the same
seeded generator, so repeated runs with the same assumptions return identical
paths and reports.

## Operating Limits

- No real credentials are required or used.
- No exchange or external provider is called.
- No recommendation increases trading permissions.
- No result bypasses the Risk Management Engine.
- No profit is guaranteed by simulation output.

Live execution remains disabled unless a later explicit production stage enables
it with supervised controls, manual approval, and risk gates.
