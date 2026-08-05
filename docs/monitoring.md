# Logging, Monitoring, and Audit Trail

Stage 029 adds structured logs, deterministic metrics, and audit-trail helpers
for reconstructing ABTP decision cycles.

## Structured Logs

`src/abtp/observability/logging.py` defines JSON-compatible
`StructuredLogRecord` values and an `InMemoryStructuredLogger` for deterministic
tests and future adapters. Log records include timestamp, level, component,
event, message, fields, causation id, and correlation id.

Sensitive fields are redacted recursively when keys look like secrets, API keys,
passwords, passphrases, tokens, or credentials. Logs should capture blocked
decision reasons, but never plaintext secret values.

## Metrics

`src/abtp/observability/metrics.py` defines `MetricPoint` and
`MetricsRegistry`. Stage 029 records deterministic counters and gauges for:

- data latency
- signal count
- risk rejection count
- order status count
- blocked trade count
- paper equity
- paper drawdown
- paper realized P/L

Metric labels reject secret-like keys. Metrics remain local in-memory records in
this stage; future adapters may export them to a monitoring backend.

## Audit Trail

`src/abtp/audit/events.py` builds append-only domain `AuditEvent` objects and
records them through the existing Stage 008 `AuditRepository`. SQLite triggers
already prevent audit updates and deletes.

Paper-cycle audit events include market input, feature vector, regime, signal,
risk decision, order intent, and blocked-trade records when applicable. Risk
rejection reasons and blocked trade reasons are preserved so operators can
reconstruct why a trade did or did not happen.

## Operating Limits

Stage 029 does not add exchange calls, live execution, order placement, strategy
logic, or risk approval behavior. Observability failures must never permit
trading. Live execution remains disabled, and every future order path must still
pass through the Risk Management Engine.
