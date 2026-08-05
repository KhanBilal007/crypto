# Exchange Reconciliation Engine

Stage 045 adds deterministic reconciliation between stored database state and
adapter-provided exchange snapshots.

## Scope

The reconciliation engine compares balances, positions, orders, fills, and
adapter health markers. It produces mismatch records and recovery
recommendations for restart recovery, API outage, stale adapter state, missing
fills, stale orders, and balance or position differences.

This stage does not call real exchange APIs, read or store credentials, cancel
orders, submit orders, approve risk, create order intents, or perform live
trading.

## Contracts

- `ReconciliationSnapshot` represents one database or exchange state capture.
- `BalanceRecord`, `PositionRecord`, `OrderRecord`, and `FillRecord` contain
  non-secret state used for deterministic comparison.
- `ReconciliationMismatch` records entity, key, expected database value,
  observed exchange value, difference, severity, reason, and source references.
- `RecoveryPlan` records advisory actions such as pause, manual review,
  reconciliation hold, refresh exchange state, replay missing fill, restart
  recovery, or outage hold.
- `ReconciliationReport` packages snapshots, mismatches, recovery plan, quality
  status, limitations, and audit payload.

## Safety Behavior

Mismatch, stale adapter state, outage, restart markers, or unresolved fill
differences fail safe by recommending hold, pause, or manual review. The report
can be consumed by dashboards and future controlled workflows, but it cannot
take exchange actions itself.

## Operating Limits

- Only supplied snapshots are compared.
- No credentials or raw secret values are stored in reconciliation records.
- No exchange HTTP/websocket behavior is implemented.
- No recommendation bypasses the Risk Management Engine.
- No reconciliation result changes live behavior directly.

Live execution remains disabled unless a later explicit production stage enables
it with supervised controls, manual approval, and risk gates.
