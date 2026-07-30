# Exchange Health Scoring

Stage 048 adds deterministic exchange-health scoring from supplied reliability,
heartbeat, order-book, and reconciliation evidence. It is a safety context layer
only: it does not call exchanges, infer live mode, submit orders, create order
intents, approve risk, or bypass the Risk Management Engine.

## Inputs

The health scorer consumes non-secret evidence:

- adapter reliability observations: request count, error count, latency samples,
  and outage flags
- live stream heartbeat status: connected, stale, degraded, disconnect count,
  and latency
- order-book metrics: spread, bid/ask depth, and imbalance
- reconciliation status: whether database and adapter state blocks
  continuation

All inputs are supplied by callers or deterministic fixtures. No credentials are
stored or required.

## Contracts

`src/abtp/exchanges/reliability.py` defines `ReliabilityInput`,
`ReliabilityPolicy`, `ReliabilityScore`, and `score_reliability`.

`src/abtp/exchanges/health.py` defines `ExchangeHealthInput`,
`ExchangeHealthPolicy`, `ExchangeHealthStatus`, `ExchangeHealthScore`, and
`score_exchange_health`.

`src/abtp/exchanges/permission_gates.py` defines `TradingPermission`,
`PermissionGateInput`, `PermissionGatePolicy`, `PermissionGateRecommendation`,
and `recommend_permission_gate`.

Every result includes quality status, reasons, source references, policy
version, and an audit payload.

## Permission Gates

Health scoring recommends one of these advisory permission states:

- `read_only`: evidence is healthy enough for monitoring workflows
- `paper_only`: use only paper/sandbox workflows until health improves
- `block_new_entries`: do not open new positions
- `pause_trading`: pause trading workflows and keep the system defensive
- `manual_review`: operator review is required before resuming normal behavior

Poor reliability, outage flags, stale streams, abnormal spreads, thin liquidity,
or reconciliation blockers degrade or reject health. Rejected health pauses
trading recommendations and requires manual review.

## Operating Limits

Exchange health is advisory risk context. It cannot create executable orders,
approve risk, submit to adapters, cancel orders, change live configuration, or
recover exchange state. Future trading workflows must still pass supervised live
gateway controls, preflight checks, and the Risk Management Engine.

No profit is guaranteed. Only risk capital may be used, and live trading remains
disabled by default.
