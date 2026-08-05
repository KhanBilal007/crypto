# Market Crash Protection

Stage 037 detects abnormal market conditions and returns fail-safe protection
decisions. It is a protection and recovery contract only. It does not call real
exchanges, cancel real orders, execute trades, train AI models, or create a new
order path.

## Inputs

`MarketProtectionSnapshot` accepts deterministic inputs from existing modules:

- price return
- realized volatility
- order-book spread and depth metrics
- live stream heartbeat state
- data-quality status
- API failure flag
- pending-order count
- source references

## Detected Conditions

Crash protection detects:

- flash crash
- abnormal volatility
- exchange outage
- stale data
- high spread
- liquidity collapse
- API failure
- rejected data quality

Any detected condition activates protection mode and blocks new trades.

## Protective Actions

The module can recommend:

- block new entries
- pause trading
- request pending-order cancellation
- request kill switch
- notify operator
- wait for recovery

Cancellation and kill-switch actions are requests only in this stage and require
manual review. No real exchange cancellation call is implemented.

## Recovery

Recovery requires healthy snapshots with no active crash conditions. When manual
approval is configured, recovery remains blocked until the operator supplies
approval. Successful recovery is gradual; it does not grant unsupervised live
trading permission.

## Auditability

Every `CrashProtectionDecision` includes detections, reasons, action types,
quality status, policy version, source references, and a compact audit payload.
Operators can reconstruct why protection mode did or did not activate.

## Operating Limits

- Default behavior is fail-safe.
- No new trades during protection mode.
- All future order paths must still pass the Risk Management Engine.
- Leverage, margin, futures, options, withdrawals, and unsupervised live trading
  remain unsupported.
- No profit is guaranteed.
