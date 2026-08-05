# Execution Quality Analyzer

Stage 041 adds read-only execution quality analysis for stored or fixture order
execution records. It does not place, modify, cancel, route, or approve orders.

## Inputs

`ExecutionObservation` combines:

- a Stage 024 `ExecutionResult`
- expected price from the decision cycle
- submit, acknowledgement, and fill timestamps
- optional order-book metrics
- source references for auditability

The analyzer reuses existing `OrderIntent`, `RiskDecision`, `FillSummary`,
`ExecutionFill`, order status, and order-book metric contracts.

## Calculations

The module calculates:

- adverse slippage in basis points
- partial-fill ratio
- fee impact in basis points of filled notional
- acknowledgement latency
- fill latency
- conservative market-impact estimate from spread and depth
- aggregate execution quality score

For buys, fill prices above the expected price are adverse. For sells, fill
prices below the expected price are adverse. Favorable slippage is represented
as a negative value while absolute slippage is used for quality scoring.

## Reports

`ExecutionQualityReport` aggregates one or more execution observations into:

- per-order execution scores
- average quality score
- warning reasons
- rejection reasons
- data-quality status
- source references
- compact audit payload

Poor execution quality can be passed to future risk, performance, and operator
reporting modules as context. It cannot create any execution action.

## Operating Limits

- Execution quality analysis is reporting and risk-context only.
- Reports cannot submit or cancel orders.
- Reports cannot approve risk decisions.
- Reports cannot call exchanges or external providers.
- Poor execution quality should degrade eligibility or recommend tighter future
  limits, but only later risk modules may enforce those limits.
- All future order paths must still pass the Risk Management Engine.
- No profit is guaranteed.
