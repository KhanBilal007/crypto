# Feature Engineering

Stage 015 transforms normalized market inputs and indicator outputs into
versioned, model-ready feature vectors. It does not train models, emit
predictions, create signals, make risk decisions, create order intents, execute
orders, call exchanges, or enable live trading.

## Inputs

`FeaturePipelineInput` accepts:

- normalized `Candle` objects
- a `DataQualityStatus` for candle sources
- Stage 014 `IndicatorResult` objects
- optional order-book metrics
- optional stream health
- optional Stage 013 `ParameterValue` objects
- optional portfolio context

Historical backfills and live decision cycles use the same `FeaturePipeline`
and `FeatureSchema` contracts.

## Schema

`FeatureSchema` defines stable feature names, data types, source family,
source name, required/optional status, and descriptions. The default schema
version is `stage-015.v1`.

Required features currently include:

- latest close
- one-candle return
- three-candle return
- volume ratio
- SMA value
- RSI value
- ATR percentage
- data-quality flag count

Optional features cover liquidity, conservative slippage estimate, stream
health, parameter registry values, and portfolio context.

## Quality

Every `FeatureSnapshot` carries:

- trust level: trusted, degraded, or rejected
- source issue flags
- `generated_at`
- lookback start and end timestamps
- schema version
- source references

Feature snapshots are live-eligible only when trusted. Stale, degraded,
rejected, incomplete, or leakage-prone inputs make the snapshot non-actionable
for future live signal generation.

## Leakage Protection

The pipeline rejects any source observed after `generated_at`, including future
candles, future indicator calculations, future parameter observations, and
future portfolio snapshots. Rejected leakage snapshots emit no values.

## Storage

`RepositoryFeatureStore` maps Stage 015 snapshots into the Stage 008
`IntelligenceRepository` by converting them to the existing domain
`FeatureVector` contract. `InMemoryFeatureStore` is provided for deterministic
tests and local composition.

## Operating Limits

The feature layer emits feature values and metadata only. It does not infer
live mode, create signals, approve risk, or place orders. Live trading remains
disabled by repository-level configuration and by the absence of any execution
logic in this stage.
