from __future__ import annotations

from sqlite3 import OperationalError

import pytest

from abtp.db import apply_migrations, connect_database, get_applied_migrations, rollback_migrations


def test_migrations_apply_idempotently_and_roll_back() -> None:
    connection = connect_database(":memory:")

    assert apply_migrations(connection) == (
        "0001_stage008_storage",
        "0002_stage_adaptive_paper_persistence",
        "0003_trader_dashboard_structured_state",
        "0004_trader_feedback",
    )
    assert apply_migrations(connection) == ()
    assert get_applied_migrations(connection) == (
        "0001_stage008_storage",
        "0002_stage_adaptive_paper_persistence",
        "0003_trader_dashboard_structured_state",
        "0004_trader_feedback",
    )
    assert connection.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM paper_account_snapshots").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM paper_open_orders").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM paper_alert_rules").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM paper_journal_entries").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM paper_chart_drawings").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM paper_trader_feedback").fetchone()[0] == 0

    assert rollback_migrations(connection) == (
        "0004_trader_feedback",
        "0003_trader_dashboard_structured_state",
        "0002_stage_adaptive_paper_persistence",
        "0001_stage008_storage",
    )
    assert get_applied_migrations(connection) == ()
    with pytest.raises(OperationalError, match="no such table"):
        connection.execute("SELECT COUNT(*) FROM candles").fetchone()

    connection.close()
