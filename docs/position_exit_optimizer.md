# Position Exit Optimizer

Stage 046 adds advisory position-exit recommendations for open spot positions.

## Scope

The optimizer consumes stored position inputs, entry price, current price, ATR,
current stop, holding time, data-quality status, volatility context, and market
regime labels. It produces deterministic recommendations for hold, tighten stop,
partial profit, full exit review, or manual review.

This stage does not create order intents, submit orders, cancel orders, approve
risk, call exchanges, call external providers, or perform live trading.

## Contracts

- `TrailingStopPolicy` and `TrailingStopState` define dynamic percentage and ATR
  trailing-stop behavior.
- `PositionExitInput` contains the current position, market price, optional ATR,
  stop, holding time, regime context, quality status, and source references.
- `ExitRecommendation` records the advisory action, recommended fraction,
  stop price, trailing-stop state, reasons, evidence, quality status, and audit
  payload.
- `ExitQualityReport` records unrealized P/L, stop distance, quality score,
  warning/rejection reasons, and source references.

## Safety Behavior

Rejected source quality, stop breaches, shock regime, shock-level volatility,
and expired holding windows recommend blocking continued holding or manual
review. High-volatility and degraded data tighten stops. Profit thresholds can
recommend partial profit taking. All outputs are advisory and must flow through
future strategy, risk, and execution controls before any action.

## Operating Limits

- Spot positions only.
- No direct exchange/API/provider calls.
- No credentials are read, stored, or required.
- No recommendation bypasses the Risk Management Engine.
- No recommendation modifies orders or positions directly.
- No profit is guaranteed by exit recommendations.

Live execution remains disabled unless a later explicit production stage enables
it with supervised controls, manual approval, and risk gates.
