"""Database table names and row aliases.

Stage 008 uses SQLite and the standard library rather than an ORM. Domain
contracts remain in `abtp.domain`; this module only names persistence tables.
"""

from __future__ import annotations

from sqlite3 import Row


class Tables:
    """Canonical table names used by repositories."""

    CANDLES = "candles"
    ORDER_BOOKS = "order_book_snapshots"
    TRADES = "trades"
    FEATURES = "feature_snapshots"
    INDICATORS = "indicator_values"
    PREDICTIONS = "predictions"
    SIGNALS = "signals"
    RISK_DECISIONS = "risk_decisions"
    ORDER_INTENTS = "order_intents"
    ORDER_LIFECYCLE_EVENTS = "order_lifecycle_events"
    PORTFOLIO_SNAPSHOTS = "portfolio_snapshots"
    POSITIONS = "positions"
    AUDIT_EVENTS = "audit_events"


DbRow = Row
