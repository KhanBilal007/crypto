# Incident Response

Incident response prioritizes stopping risk, preserving evidence, and keeping
secrets out of logs and records.

## Immediate Stop

Use the strongest available stop control:

1. Activate the paper or automation kill switch.
2. Keep `SAFE_MODE=true`.
3. Set `ABTP_ENABLE_LIVE_TRADING=false`.
4. Stop scheduled collectors, paper loops, or automation loops.
5. Preserve logs, metrics, audit records, and database backups.

Automation must stop on daily loss, weekly loss, max drawdown, stale data,
exchange outage, abnormal spread, volatility shock, model error, risk error, or
missing operator presence.

## Common Incidents

Stale or degraded data:
Stop new entries, mark outputs degraded or rejected, and reconstruct the
decision trail from market input, feature, regime, signal, risk, and order
events.

Risk rejection or circuit-breaker trip:
Do not override the rejection. Review risk checks, portfolio context, data
quality, and audit reasons before any restart.

Notification failure:
Critical live-mode alerts fail closed. Keep trading blocked until an operator
confirms delivery health or an approved fallback channel is available.

Suspected credential leak:
Disable the exchange key at the provider, rotate credentials, verify no
withdrawal-capable scopes existed, inspect logs/audit rows for secret-like
keys, and keep live mode disabled.

Database corruption or loss:
Stop the process, preserve the damaged file, restore from the latest backup or
dump, run migrations, and verify audit reconstruction before resuming.

## Evidence To Preserve

- environment profile and safe-mode state
- data-quality status and stream health
- feature schema version and source references
- prediction/regime/strategy explanations
- risk checks and rejection reasons
- order intent and execution status
- portfolio/equity state
- logs, metrics, notification deliveries, and audit correlation IDs

## Restart Criteria

Restart only after the cause is understood, the full verification gate passes,
the release checklist is re-reviewed, and the operator acknowledges that ABTP
does not guarantee profit and only risk capital may be used.
