# Database Design

Stage 008 adds local SQLite persistence for ABTP. The storage layer is narrow:
it creates migrations, session helpers, and repositories that map to Stage 007
domain models. It does not implement exchange calls, live trading, AI training,
strategy logic, or order execution.

## Database Runtime

The default database is local SQLite:

```text
ABTP_DATABASE_URL=sqlite:///./abtp.sqlite3
```

Tests use in-memory SQLite databases and rebuild the schema from migrations.
No external database service or exchange credentials are required.

## Migrations

SQL migrations live in `migrations/`:

- `0001_stage008_storage.up.sql`
- `0001_stage008_storage.down.sql`

The migration helper in `src/abtp/db/session.py` can apply and roll back
migrations using a `sqlite3.Connection`.

## Tables

Stage 008 creates tables for:

- candles
- order book snapshots
- trades
- indicator values
- feature snapshots
- predictions
- signals
- risk decisions
- order intents
- order lifecycle events
- portfolio snapshots
- positions
- audit events

Domain payloads are stored as JSON snapshots alongside query-friendly columns.
This lets future modules reconstruct trading decisions from stored inputs,
signals, risk checks, order intents, portfolio snapshots, and audit events.

## Append-Only Controls

The following trade-decision tables are append-only through repository behavior
and SQLite triggers:

- `audit_events`
- `risk_decisions`
- `order_intents`
- `order_lifecycle_events`

Updates and deletes raise database errors. Later stages should model lifecycle
changes by appending new records rather than mutating previous decisions.

## Secret Handling

Live credentials must never be stored in database rows. Repositories reject
payload keys that look secret-bearing, such as `api_key`, `secret`, `password`,
`passphrase`, `token`, or `credential`. Error messages include the key name but
not the attempted value.

Configuration may contain credential presence references from Stage 006, but
those references are not persisted here.

## Repository Boundaries

Repositories live in `src/abtp/repositories/` and map database rows to Stage 007
domain models. They intentionally avoid direct exchange, database-global, AI, or
execution coupling:

- `MarketDataRepository`
- `IntelligenceRepository`
- `RiskDecisionRepository`
- `OrderRepository`
- `PortfolioSnapshotRepository`
- `AuditRepository`

Future services should depend on these repositories through narrow application
interfaces rather than bypassing risk, audit, or append-only controls.

