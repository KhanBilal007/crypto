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
    PAPER_ACCOUNT_SNAPSHOTS = "paper_account_snapshots"
    PAPER_TRANSACTIONS = "paper_transactions"
    PAPER_STRATEGY_EVALUATIONS = "paper_strategy_evaluations"
    PAPER_RISK_DECISIONS = "paper_risk_decisions"
    PAPER_SIMULATED_FILLS = "paper_simulated_fills"
    PAPER_OPERATOR_ACTIONS = "paper_operator_actions"
    PAPER_PREFERENCES = "paper_preferences"
    PAPER_OPEN_ORDERS = "paper_open_orders"
    PAPER_ALERT_RULES = "paper_alert_rules"
    PAPER_JOURNAL_ENTRIES = "paper_journal_entries"
    PAPER_CHART_DRAWINGS = "paper_chart_drawings"
    PAPER_TRADER_FEEDBACK = "paper_trader_feedback"


DbRow = Row
