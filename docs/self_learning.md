# Self-Learning Module

Stage 035 adds deterministic analysis over completed trades. The module studies
trade outcomes, confidence calibration, regimes, features, and strategy slices
so future stages can review explainable recommendations.

It does not modify trading rules, retrain models online, create signals, create
risk decisions, create order intents, call exchanges, or execute orders.

## Inputs

Learning consumes normalized `TradeLearningRecord` objects. A record can point
to paper or backtest trade IDs and includes:

- strategy name
- regime label
- realized P/L and return
- fees
- signal confidence and optional prediction confidence
- risk decision status
- feature values
- source references
- optional data-quality status

Rejected records are excluded from learning recommendations. Degraded records
mark the analysis degraded so downstream consumers cannot treat the output as
fully trusted.

## Outputs

The module emits advisory objects only:

- `TradeOutcomeAnalysis`
- `PatternSummary`
- `FeatureImportanceObservation`
- `StrategyLearningRank`
- `ConfidenceCalibrationSuggestion`
- `LearningAnalysis`
- `LearningReport`

Every recommendation includes evidence references, rationale, and hard safety
flags:

- `requires_validation=true`
- `allowed_to_auto_apply=false`

## Confidence Calibration

Confidence calibration buckets completed trades by signal confidence and
compares average confidence with observed win rate. Suggested adjustments are
small, capped, deterministic, and advisory. They must be validated through
paper/backtest review before any later stage can adopt them.

## Reports

Monthly learning reports filter completed trades by `closed_at` month. Reports
include outcome analysis, calibration, source references, limitations, and a
compact audit payload that can be stored as an append-only audit event.

## Operating Limits

- No profit is guaranteed.
- Recommendations must never bypass the Risk Management Engine.
- Recommendations must not automatically change strategies, model weights, risk
  limits, or execution behavior.
- Live rule changes require later-stage explicit approval and manual review.
- Tests use deterministic fixtures only and require no real exchange
  credentials.
