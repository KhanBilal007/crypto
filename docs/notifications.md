# Alerts and Notification Service

Stage 030 adds deterministic alert contracts, notification channels, throttling,
and fail-closed dispatch behavior for critical risk events.

## Alert Scope

The notification service can alert on:

- risk halts
- kill-switch activation
- exchange/data-feed outage
- stale market data
- drawdown breaches
- large slippage context
- repeated losses
- manual approval requests
- blocked paper trades

Alerts include category, severity, title, message, timestamp, correlation id,
and redacted context fields. Secret-like context keys are redacted before a
channel receives the alert.

## Channels

Stage 030 includes a deterministic `InMemoryNotificationChannel` only. It is
used for tests and future adapters. No email, SMS, chat, webhook, exchange,
network, or external provider integration is added in this stage.

Future channels must implement the `NotificationChannel` protocol and must not
print, log, or store plaintext secrets.

## Fail-Closed Rule

Critical live-mode risk alerts must be delivered successfully before trading can
be considered safe. If every channel fails for a critical live-mode alert,
`AlertDispatchResult.trading_permitted` is `false` and
`require_trading_permitted()` raises.

Alert failures do not permit trading. They are treated as an additional reason
to keep risk controls active.

## Throttling

Duplicate alerts with the same category, severity, and title are suppressed
inside the configured throttle window. Suppressed critical live-mode alerts
remain fail-closed.

## Operating Limits

Stage 030 does not add live trading, order submission, real exchange calls,
external notification providers, or credential storage. It reports safety
states; it does not approve risk or execute orders.
