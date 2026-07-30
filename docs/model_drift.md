# Model Drift Detection

Stage 043 adds deterministic model drift detection for research, backtest, and
paper-safe model management workflows.

## Scope

The drift module compares a baseline model window with a current model window.
Each window contains stored feature distributions, recorded prediction
confidence values, observed evaluation quality, and optional label-distribution
metadata. The module does not train models, serve predictions, select active
models, create strategy signals, create risk decisions, create order intents,
call exchanges, call external providers, or execute trades.

## Contracts

- `DriftWindow` records model reference, time range, feature value series,
  quality status, confidence history, prediction outcome metrics, calibration
  error, label distribution, and source references.
- `DriftMeasurement` records one explainable drift check with baseline/current
  values, delta, threshold, severity, evidence, and source references.
- `DriftAssessment` aggregates measurements into severity, data-quality status,
  non-actionable state, downgrade recommendation, and retraining
  recommendation.
- `ModelDriftReport` summarizes one or more assessments for audit/dashboard
  consumers.

## Deterministic Checks

The rule engine in `src/abtp/ai/drift_rules.py` checks:

- feature mean shifts;
- feature variance/distribution shifts;
- concept-drift proxy using label-distribution shifts;
- prediction-quality degradation using accuracy, directional hit rate, and
  calibration error;
- confidence degradation using average model confidence;
- stale, degraded, or rejected drift windows.

Every measurement includes the threshold and the input values that caused the
status.

## Safety Behavior

Drift detection fails safe. Severe drift, stale current windows, rejected
current quality, major confidence degradation, or prediction-quality degradation
can recommend a model downgrade and mark the model non-actionable. Retraining
recommendations are advisory only and do not start training.

The model manager or operator may consume downgrade and retraining evidence in a
later controlled workflow. No live behavior is changed directly by Stage 043.

## Operating Limits

- No real external data source is queried.
- No credentials are read, logged, stored, or required.
- No live trading permission can be increased.
- No recommendation bypasses the Risk Management Engine.
- Deterministic fixtures are required for tests.

ABTP does not guarantee profit. Only risk capital should ever be used, and live
execution remains disabled unless a later explicit production stage enables it
with manual approval and risk controls.
