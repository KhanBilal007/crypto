# Portfolio Allocation Optimizer

Stage 047 adds advisory portfolio allocation recommendations for spot-first
portfolio management.

## Scope

The optimizer consumes stored portfolio snapshots, total equity, available cash,
target weights, data quality, drawdown, confidence scores, volatility estimates,
liquidity scores, regime labels, correlation snapshots, and optional Monte Carlo
allocation multipliers. It emits deterministic asset-level rebalance lines,
cash-reserve evidence, rejection reasons, reduction reasons, and audit payloads.

This stage does not create order intents, approve risk, submit orders, execute
trades, call exchanges, call external providers, or change live behavior.

## Contracts

- `CorrelationEstimate` and `CorrelationSnapshot` represent deterministic
  pairwise correlation evidence.
- `AllocationPolicy` defines cash reserve, exposure, asset-weight, correlation,
  drawdown, volatility, confidence, and rebalance thresholds.
- `AllocationInput` packages portfolio state and advisory context for one
  allocation review.
- `RebalanceLine` records per-asset current, target, recommended weight,
  notional delta, action, and reasons.
- `PortfolioAllocationRecommendation` records the full advisory result,
  quality status, source references, limitations, and audit payload.

## Safety Behavior

Rejected data quality, breached cash reserve, drawdown breach, or excessive
gross exposure blocks allocation expansion. Degraded data, shock/high-volatility
regime, Monte Carlo reduction, low confidence, excessive volatility, and high
correlation reduce or hold allocation rather than expanding exposure.

All outputs are advisory and must flow through future strategy, risk, and
execution controls before any action.

## Operating Limits

- Spot allocation only.
- Cash reserves are preserved by policy.
- No credentials are read, stored, or required.
- No exchange or external provider calls are made.
- No recommendation bypasses the Risk Management Engine.
- No profit is guaranteed by allocation recommendations.

Live execution remains disabled unless a later explicit production stage enables
it with supervised controls, manual approval, and risk gates.
