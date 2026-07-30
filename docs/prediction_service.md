# Prediction Service

Stage 019 exposes model predictions through a stable service contract. The
service records model version, feature inputs, confidence, explanation, quality
status, optional regime context, optional prediction persistence, and optional
append-only audit events.

## Inputs

The service accepts a `PredictionRequest` containing:

- a Stage 015 `FeatureSnapshot`
- optional Stage 018 `RegimeClassification`
- optional correlation id for audit tracing
- a per-call persistence flag

Models must implement the `PredictionModel` protocol and return probability and
confidence output. The current deterministic baseline model remains
research/backtest-only.

## Outputs

`PredictionServiceResult` contains:

- probability of upward and downward movement
- expected return and expected volatility
- confidence
- model name and version
- feature reference
- generated explanation
- quality status and flags
- actionability state and non-actionable reasons
- optional prediction row id
- optional audit event id

The result is probability context only. It is not a signal, risk decision, order
intent, execution command, or profitability claim.

## Explainability

`PredictionExplanation` provides a deterministic explanation using stable
feature contribution weights, source references, data-quality score, model
metadata, limitations, and optional regime label. Contributions are based on
current/past feature snapshot values only.

## Safety Gates

Predictions are marked non-actionable when confidence is below the configured
threshold, feature quality is not trusted, model output quality is not trusted,
or supplied regime context blocks new entries. Rejected source quality remains
rejected; degraded inputs remain degraded.

Stage 019 does not fetch exchange data, call external providers, train models,
serve live models, create signals, create order intents, make risk decisions, or
execute trades. Live execution remains disabled.

## Persistence

When repositories are supplied, the service stores a Stage 007 domain
`Prediction` through `IntelligenceRepository` and appends an audit event through
`AuditRepository`. Audit payloads contain identifiers, metadata, confidence,
actionability, quality, and regime label. Secrets and credentials are never
accepted or stored by this layer.
