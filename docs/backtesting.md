# Backtesting Engine

Stage 025 adds deterministic historical replay for strategies using realistic
costs, risk checks, portfolio state, and paper-safe execution.

## Replay Flow

For each candle, the engine:

1. Builds current-only feature values from candles available up to that point.
2. Classifies market regime.
3. Evaluates the configured strategy.
4. Sends directional signals through the Risk Management Engine.
5. Creates an `OrderIntent` only after risk approval.
6. Executes through the Stage 024 paper-safe engine.
7. Applies fills, fees, and slippage to the backtest broker.
8. Records equity and step-level audit artifacts.

## Costs

Backtests include:

- fee assumptions
- half-spread cost
- slippage cost
- paper fill price adjustment

Results set `costs_included=true`. Gross-only performance is not considered a
valid success measure.

## Safety Controls

Backtests do not call exchanges, external providers, live routes, or real
accounts. No order can be simulated without an approved `RiskDecision`.
Drawdown halts block new execution when configured limits are breached.

## Operating Limits

Stage 025 is a deterministic simulation layer, not a profitability claim.
Reporting and paper-trading layers arrive in later stages.
