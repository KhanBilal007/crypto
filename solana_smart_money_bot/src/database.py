from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(f"sqlite:///{settings.DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from src import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Lightweight additive migration for older SQLite files created before
    # top_10_holder_percent was added to the Token model.
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tokens)")).fetchall()}
        if "top_10_holder_percent" not in columns:
            conn.execute(text("ALTER TABLE tokens ADD COLUMN top_10_holder_percent FLOAT NOT NULL DEFAULT 100.0"))
