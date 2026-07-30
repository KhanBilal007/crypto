# AI Model Manager

Stage 042 adds metadata-only management for multiple AI model versions. It
tracks model registry entries, training history, evaluation snapshots,
comparison results, retirement state, and advisory active-model recommendations.
It does not train models, serve predictions, create signals, approve risk, or
execute orders.

## Registry

`ModelRegistryEntry` records:

- model name and version
- feature schema version
- model family
- label horizon
- lifecycle status: registered, candidate, active, degraded, retired, rejected
- approval status: unapproved, research, paper, or live approved
- limitations and source references

`ModelRegistry` stores entries in memory for deterministic tests and supports
registration, lookup, filtering, training-history recording, evaluation
recording, latest-record lookup, retirement, and compact audit payloads.

## Training History

`ModelTrainingRecord` stores auditable metadata only:

- trained_at
- training window
- feature schema version
- label horizon
- sample count
- training metrics
- limitations
- source reference

No model artifacts, credentials, secrets, or external-service handles are stored
in these records.

## Evaluation

`ModelEvaluationSnapshot` records deterministic evaluation metrics for a dataset
or split. Current selection scoring uses accuracy, directional hit rate,
precision, recall, and calibration error when present. Poor quality, stale
evaluation snapshots, missing training history, weak metrics, unapproved models,
retired models, or rejected models fail closed.

## Selection

`select_active_model` returns an `ActiveModelRecommendation` with:

- selected model reference
- ranked comparison results
- confidence score
- rejected reasons
- downgrade recommendations
- manual approval flag
- quality status
- audit payload

In research, backtest, and paper modes, `AIModelManager` may apply an advisory
selection to its local active-model metadata reference. In live mode, active
model changes require manual approval and later live-stage controls.

## Operating Limits

- Model manager recommendations are advisory metadata decisions.
- The manager cannot serve predictions.
- The manager cannot train models.
- The manager cannot create strategy signals.
- The manager cannot create risk decisions or order intents.
- The manager cannot submit orders or call exchanges.
- Live model swaps are not applied automatically.
- No real external AI services, exchange/API calls, or external providers are
  used.
- No profit is guaranteed.
