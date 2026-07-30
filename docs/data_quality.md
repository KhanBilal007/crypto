# Data Quality

Stage 012 adds validation, normalization, and anomaly utilities for market data.
The engine is pure and fixture-driven: it does not call exchanges, databases,
AI models, strategies, risk engines, or order execution modules.

## Trust Status

`DataQualityStatus` classifies source data as:

- `trusted`: no quality issues detected
- `degraded`: usable only with caution; future strategy/risk modules should
  reject or down-rank this data unless explicitly allowed
- `rejected`: not safe for trading decisions

Statuses include flags, reasons, source references, and check timestamps so
future features and signals can trace whether their source data was trusted,
degraded, or rejected.

## Normalization

Normalization helpers cover:

- UTC timestamps
- supported candle intervals
- uppercase asset symbols
- asset pair construction
- decimal precision
- provider payload shape
- candle timestamp/interval normalization

Malformed provider payloads fail fast instead of silently flowing downstream.

## Quality Checks

The quality engine detects:

- missing candles
- duplicate timestamps
- stale data
- zero volume
- non-positive prices
- timestamp drift
- timestamp ordering errors
- abnormal spread
- outlier returns
- provider price disagreement
- degraded stream heartbeat state

Poor-quality data is marked degraded or rejected. It is never silently treated
as trusted.

## Conservative Thresholds

Default anomaly thresholds are intentionally conservative:

- absolute close-to-close return greater than `25%`
- order-book spread greater than `100` bps
- provider price disagreement greater than `50` bps

Later stages may make thresholds environment-driven, but this stage keeps them
deterministic for tests.

## Minimum-Risk Control

`DataQualityStatus.require_trusted()` raises when data is degraded or rejected.
Future risk and strategy modules should use this status to reject trades when
source quality is below threshold.

