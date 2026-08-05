# Risk Management Engine

Stage 022 adds the mandatory Risk Management Engine. It evaluates strategy
signals before any future order creation and returns an explicit domain
`RiskDecision` containing allow/reject flags, checks, reasons, max position size,
stop-loss requirement, and kill-switch status.

## Inputs

`RiskEvaluationRequest` contains:

- Stage 020 `StrategyEvaluation`
- proposed future order id
- entry price
- spread and estimated slippage
- `RiskPortfolioContext`
- evaluation timestamp

`RiskPortfolioContext` includes total equity, available cash, current exposure,
correlated exposure, drawdown, daily/weekly P/L, and data-quality status.

## Policy

`RiskPolicy` is fail-closed by default:

- maximum risk per trade
- maximum position percentage
- minimum cash reserve
- maximum drawdown
- daily and weekly loss limits
- spread and slippage ceilings
- fee assumption
- minimum signal confidence
- required stop-loss
- kill switch

## Checks

The engine rejects missing stops, HOLD signals, unsupported signal direction,
low confidence, rejected/degraded risk input quality, drawdown breach, daily or
weekly loss breach, excessive spread, excessive slippage, no available
risk-approved capacity, and an active kill switch.

Position size is calculated from equity risk, stop distance, fees/slippage,
available cash after reserve, and max exposure.

## Order Path Safety

Stage 022 does not create orders. It returns a `RiskDecision` tied to a proposed
order id. Future stages must create `OrderIntent` objects only with a matching
approved risk decision. `assert_order_intent_has_approved_risk()` fails closed
when an order intent lacks a matching approval.

No exchange calls, order routing, execution, live trading, strategy generation,
or portfolio accounting are implemented in this stage.
