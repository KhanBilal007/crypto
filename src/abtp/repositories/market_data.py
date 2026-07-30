"""Repositories for market data domain models."""

from __future__ import annotations

from collections.abc import Mapping
from sqlite3 import Connection, IntegrityError
from uuid import uuid4

from abtp.db.models import Tables
from abtp.domain import Candle, OrderBookSnapshot, Trade
from abtp.domain.models import JsonValue
from abtp.repositories.serialization import (
    candle_from_payload,
    dumps_json,
    dumps_model,
    order_book_from_payload,
    pair_symbol,
    trade_from_payload,
)


class MarketDataRepository:
    """Persist and retrieve market data without exchange API behavior."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def add_candle(
        self, candle: Candle, data_quality_flags: Mapping[str, JsonValue] | None = None
    ) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO candles (
                exchange, pair, interval, opened_at, closed_at, open, high, low,
                close, volume, data_quality_flags, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candle.exchange.name,
                pair_symbol(candle.pair),
                candle.interval,
                candle.opened_at.isoformat(),
                candle.closed_at.isoformat(),
                str(candle.open),
                str(candle.high),
                str(candle.low),
                str(candle.close),
                str(candle.volume),
                dumps_json(data_quality_flags or {}),
                dumps_model(candle),
            ),
        )
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("candle insert did not return a row id")
        return cursor.lastrowid

    def add_candle_if_absent(
        self, candle: Candle, data_quality_flags: Mapping[str, JsonValue] | None = None
    ) -> bool:
        """Insert a candle and return whether a new row was stored."""

        try:
            self.add_candle(candle, data_quality_flags=data_quality_flags)
        except IntegrityError:
            self._connection.rollback()
            return False
        return True

    def get_candle(
        self, *, exchange: str, pair: str, interval: str, opened_at: str
    ) -> Candle | None:
        row = self._connection.execute(
            """
            SELECT payload_json FROM candles
            WHERE exchange = ? AND pair = ? AND interval = ? AND opened_at = ?
            """,
            (exchange, pair, interval, opened_at),
        ).fetchone()
        return candle_from_payload(str(row["payload_json"])) if row else None

    def add_order_book(self, snapshot: OrderBookSnapshot) -> str:
        snapshot_id = str(uuid4())
        payload = snapshot.to_json_dict()
        self._connection.execute(
            """
            INSERT INTO order_book_snapshots (
                id, exchange, pair, captured_at, bids_json, asks_json, source_ref, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                snapshot.exchange.name,
                pair_symbol(snapshot.pair),
                snapshot.captured_at.isoformat(),
                dumps_json({"bids": payload["bids"]}),
                dumps_json({"asks": payload["asks"]}),
                snapshot.source_ref,
                dumps_model(snapshot),
            ),
        )
        self._connection.commit()
        return snapshot_id

    def get_order_book(self, snapshot_id: str) -> OrderBookSnapshot | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.ORDER_BOOKS} WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        return order_book_from_payload(str(row["payload_json"])) if row else None

    def add_trade(self, trade: Trade) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO trades (
                exchange, pair, trade_id, traded_at, price, quantity, side, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.exchange.name,
                pair_symbol(trade.pair),
                trade.trade_id,
                trade.traded_at.isoformat(),
                str(trade.price),
                str(trade.quantity),
                trade.side.value,
                dumps_model(trade),
            ),
        )
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("trade insert did not return a row id")
        return cursor.lastrowid

    def get_trade(self, *, exchange: str, trade_id: str) -> Trade | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {Tables.TRADES} WHERE exchange = ? AND trade_id = ?",
            (exchange, trade_id),
        ).fetchone()
        return trade_from_payload(str(row["payload_json"])) if row else None
