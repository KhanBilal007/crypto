# Module Contracts

Stage 007 defines typed domain models and protocol interfaces shared across
future ABTP modules. These contracts are intentionally inert: they do not call
exchanges, databases, AI models, or order execution systems.

## Domain Models

Core models live in `src/abtp/domain/models.py`:

- `AssetPair`
- `Candle`
- `OrderBookSnapshot`
- `Trade`
- `FeatureVector`
- `Prediction`
- `Signal`
- `RiskDecision`
- `OrderIntent`
- `PortfolioSnapshot`
- `AuditEvent`

Models are frozen dataclasses with validation in `__post_init__`. They expose
`to_json_dict()` for audit-friendly, JSON-compatible snapshots where `Decimal`,
`datetime`, `UUID`, enum, tuple, and nested model values are rendered as stable
primitive values.

`TradingPair` remains as a compatibility alias for the Stage 005 public import.

## Enums

Enums live in `src/abtp/domain/enums.py` and use `StrEnum` for stable serialized
values. Spot trading remains the only supported market type for current stages;
margin, leverage, futures, and options stay disabled until a later explicit
stage enables them.

## Risk Decision Contract

Every future order path must pass through the Risk Management Engine before
execution. `RiskDecision` includes:

- `allow`
- `reject`
- `reasons`
- `max_position_size`
- `stop_loss_required`
- `kill_switch_active`
- per-policy `checks`

An approved decision cannot contain failed checks, and a kill-switch-active
decision cannot be approved.

## Interfaces

Protocols live in `src/abtp/interfaces/`:

- `MarketDataProvider`
- `PredictionEngine`
- `StrategyEngine`
- `RiskManagementEngine`
- `PortfolioRepository`
- `OrderExecutionGateway`

These protocols define exchange points between modules without implementation
coupling or database coupling. Implementations introduced in later stages should
depend on domain models and interfaces rather than importing concrete modules
across boundaries.

## Operating Limits

- No real exchange, database, AI model, or order execution behavior is present
  in Stage 007.
- Exchange API calls must remain inside future exchange adapter modules.
- Unit tests must remain deterministic and credential-free.
- Decisions must remain explainable through stored inputs, generated signals,
  risk checks, order intents, portfolio snapshots, and audit events.

