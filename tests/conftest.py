from __future__ import annotations

from collections.abc import Iterator
from sqlite3 import Connection

import pytest

from abtp.db import apply_migrations, connect_database


@pytest.fixture(autouse=True)
def offline_dashboard_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production defaults to Binance; unit tests explicitly select deterministic data."""
    monkeypatch.setenv("ABTP_MARKET_DATA_SOURCE", "demo")


@pytest.fixture
def migrated_connection() -> Iterator[Connection]:
    connection = connect_database(":memory:")
    apply_migrations(connection)
    try:
        yield connection
    finally:
        connection.close()
