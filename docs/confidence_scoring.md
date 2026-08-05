# Confidence Scoring

Stage 049 adds a deterministic confidence scoring engine that aggregates
advisory confidence from normalized upstream components:

- trend
- momentum
- volatility
- volume
- order book
- AI prediction
- market regime
- sentiment
- on-chain context
- portfolio context
- risk context
- data quality

The engine does not create strategy signals, risk decisions, order intents,
exchange calls, order execution, live trading, or live configuration changes.
It produces decision-cycle context only.

## Contracts

`src/abtp/confidence/weights.py` defines stable component names and the
`ConfidenceWeightPolicy`.

`src/abtp/confidence/engine.py` defines component inputs, contribution records,
the scoring request, and the final `ConfidenceScoreResult`.

`src/abtp/confidence/reasons.py` defines rejection reason categories and quality
status helpers.

Every result includes:

- final weighted score
- actionable flag
- included and excluded contribution records
- component weights and weighted contribution values
- rejection and non-actionable reasons
- feature schema version
- data-quality status
- source references
- policy version
- audit payload

## Failure Handling

Missing required components, rejected quality, stale data, non-live-eligible
inputs, contradictory high-confidence components, poor exchange health, high
risk context, insufficient evidence, or low aggregate confidence mark the result
non-actionable. Degraded component quality reduces that component contribution
instead of silently trusting it.

Sentiment and on-chain context are weighted but optional by default because
external context remains lower-trust unless future stages configure trusted
providers.

## Operating Limits

Confidence is advisory only and cannot bypass the Risk Management Engine. A high
confidence score is not permission to trade and is not a profitability claim.
Future strategies may consume confidence context, but every trading action must
still pass strategy rules, supervised live gateway controls, preflight checks,
and the Risk Management Engine.
