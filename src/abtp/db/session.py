"""SQLite session and migration helpers."""

from __future__ import annotations

from pathlib import Path
from sqlite3 import Connection, Row, connect


def connect_database(database_url: str | Path = ":memory:") -> Connection:
    """Create a SQLite connection with repository-friendly defaults."""

    path = _sqlite_path(database_url)
    connection = connect(path)
    connection.row_factory = Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def apply_migrations(
    connection: Connection, migrations_path: Path | None = None
) -> tuple[str, ...]:
    """Apply all unapplied up migrations."""

    path = _migration_path(migrations_path)
    _ensure_migration_table(connection)
    applied = set(get_applied_migrations(connection))
    applied_now: list[str] = []

    for up_file in sorted(path.glob("*.up.sql")):
        version = up_file.name.removesuffix(".up.sql")
        if version in applied:
            continue
        connection.executescript(up_file.read_text(encoding="utf-8"))
        applied_now.append(version)

    connection.commit()
    return tuple(applied_now)


def rollback_migrations(
    connection: Connection, migrations_path: Path | None = None
) -> tuple[str, ...]:
    """Apply down migrations in reverse applied order."""

    path = _migration_path(migrations_path)
    rolled_back: list[str] = []
    for version in reversed(get_applied_migrations(connection)):
        down_file = path / f"{version}.down.sql"
        if not down_file.exists():
            raise FileNotFoundError(f"missing down migration for {version}")
        connection.executescript(down_file.read_text(encoding="utf-8"))
        rolled_back.append(version)

    connection.commit()
    return tuple(rolled_back)


def get_applied_migrations(connection: Connection) -> tuple[str, ...]:
    """Return applied migration versions."""

    try:
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    except Exception:
        return ()
    return tuple(str(row["version"]) for row in rows)


def _sqlite_path(database_url: str | Path) -> str:
    raw = str(database_url)
    if raw in {":memory:", ""}:
        return ":memory:"
    if raw.startswith("sqlite:///"):
        return raw.removeprefix("sqlite:///")
    if raw.startswith("sqlite://"):
        return raw.removeprefix("sqlite://")
    return raw


def _migration_path(migrations_path: Path | None) -> Path:
    if migrations_path is not None:
        return migrations_path
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "migrations"
        if candidate.exists():
            return candidate
    return current.parents[3] / "migrations"


def _ensure_migration_table(connection: Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
