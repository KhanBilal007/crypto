# Adaptive Position Management

Stage 058 adds advisory adaptive position management for open spot positions.
It combines the existing position-exit optimizer with supplied confidence,
volatility, regime-risk, scaling, stop, ATR, trailing-stop, holding-age, and
source-quality evidence.

The engine does not submit, modify, or cancel orders. It does not create order
intents, approve risk, call exchanges, call providers, or enable live trading.

## Inputs

`AdaptivePositionInput` contains:

- `PositionExitInput` for price, entry, ATR, current stop, trailing stop,
  holding period, volatility regime, source quality, and source references
- Confidence score
- Volatility score
- Regime-risk score
- Scaling score

Scores are normalized `Decimal` values between `0` and `1`.

## Outputs

`manage_adaptive_position` returns `AdaptivePositionRecommendation` with:

- Current risk
- Holding recommendation: hold, reduce, increase review, exit review, or manual
  review
- Hold percentage
- Sell percentage
- Increase percentage
- Exit percentage
- Stop price
- Nested exit recommendation
- Reasons, evidence, quality status, and audit payload

Percentages are advisory only. They are not executable orders.

## Safety Limits

Rejected source quality, stop breaches, shock/high-risk conditions, unsafe
holding, and high current risk fail closed to exit review or manual review.
Low confidence and medium risk recommend reduction, not automatic selling.
Increase recommendations are review-only and require trusted quality, high
confidence, low risk, low volatility, and low regime risk.

No profit is guaranteed. Any future action must still pass supervised controls,
order-intent creation, and the Risk Management Engine.
