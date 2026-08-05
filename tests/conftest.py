from __future__ import annotations

from collections.abc import Iterator
from sqlite3 import Connection

import pytest

from abtp.db import apply_migrations, connect_database


@pytest.fixture
def migrated_connection() -> Iterator[Connection]:
    connection = connect_database(":memory:")
    apply_migrations(connection)
    try:
        yield connection
    finally:
        connection.close()
