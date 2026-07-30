# Strategy Framework

Stage 020 adds a pluggable strategy framework that turns trusted features,
optional prediction context, and optional regime context into non-executable
`Signal` objects.

## Inputs

Strategies receive a `StrategyContext` containing:

- Stage 015 `FeatureSnapshot`
- evaluation timestamp
- timeframe
- optional Stage 019 `PredictionServiceResult`
- optional Stage 018 `RegimeClassification`

The framework does not fetch market data, call exchanges, call providers, train
models, approve risk, create orders, or execute trades.

## Plugin Contract

Each plugin implements `StrategyPlugin`:

- `config`: strategy name, version, enabled state, supported timeframes, and
  description
- `evaluate(context)`: returns a `StrategyEvaluation`

`StrategyEvaluation` contains:

- strategy name and version
- enabled state
- domain `Signal`
- non-executable signal plan metadata
- reasons
- optional signal row id
- optional audit event id

The signal plan records entry reason, timeframe, feature snapshot reference,
optional stop/target suggestions, optional regime label, and optional prediction
reference. Stop and target suggestions are advisory metadata for later risk
modules; they are not executable orders.

## Engine

`StrategyRegistry` registers plugins by name and supports explicit
enable/disable overrides. `StrategyEngine` evaluates registered strategies in
stable name order, optionally persists signals through `IntelligenceRepository`,
and optionally appends signal audit events through `AuditRepository`.

Disabled strategies emit `HOLD` with zero confidence.

## Safety Behavior

Strategies emit `Signal` only. They cannot create `OrderIntent`,
`RiskDecision`, exchange adapter calls, or live execution paths. Stage 022 must
remain the mandatory risk gate before any future order creation.

The included `ThresholdRuleStrategy` is a deterministic framework fixture and
example. It emits `BUY`, `SELL`, or `HOLD` from prediction probabilities and
confidence after checking strategy enablement, timeframe support, feature
quality, prediction actionability, and blocking regime context.

## Operating Limits

Stage 020 is not a profitable trading strategy. It is framework plumbing for
future strategy stages. Live trading remains disabled, and no profit is
guaranteed.
