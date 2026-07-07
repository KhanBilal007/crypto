from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.exc import OperationalError

from src.database import SessionLocal
from src.models import HistoricalPricePoint, HistoricalTokenSnapshot, HistoricalWalletTransaction


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def cache_wallet_transactions(wallet_address: str, txs: list[dict[str, Any]], *, source: str = "helius") -> int:
    saved = 0
    with SessionLocal() as db:
        for tx in txs:
            signature = str(tx.get("signature") or tx.get("tx_hash") or "")
            if not signature:
                continue
            timestamp = _coerce_dt(tx.get("timestamp")) or _utcnow()
            payload = json.dumps(tx, separators=(",", ":"), sort_keys=True, default=str)
            row = db.query(HistoricalWalletTransaction).filter(HistoricalWalletTransaction.signature == signature).first()
            if row is None:
                row = HistoricalWalletTransaction(
                    wallet_address=wallet_address,
                    signature=signature,
                    tx_timestamp=timestamp,
                    source=source,
                    payload_json=payload,
                )
                db.add(row)
                saved += 1
            else:
                row.wallet_address = wallet_address
                row.tx_timestamp = timestamp
                row.source = source
                row.payload_json = payload
                row.fetched_at = _utcnow()
        db.commit()
    return saved


def load_wallet_transactions(wallet_addresses: list[str], since: datetime, until: datetime | None = None) -> list[dict[str, Any]]:
    until = until or _utcnow()
    try:
        with SessionLocal() as db:
            rows = (
                db.query(HistoricalWalletTransaction)
                .filter(
                    and_(
                        HistoricalWalletTransaction.wallet_address.in_(wallet_addresses),
                        HistoricalWalletTransaction.tx_timestamp >= since,
                        HistoricalWalletTransaction.tx_timestamp <= until,
                    )
                )
                .order_by(HistoricalWalletTransaction.tx_timestamp.asc())
                .all()
            )
            return [json.loads(row.payload_json) for row in rows]
    except OperationalError:
        return []


def cache_token_snapshot(token_mint: str, source: str, snapshot: dict[str, Any]) -> None:
    observed_at = _coerce_dt(snapshot.get("observed_at")) or _utcnow()
    payload = json.dumps(snapshot, separators=(",", ":"), sort_keys=True, default=str)
    with SessionLocal() as db:
        row = HistoricalTokenSnapshot(
            token_mint=token_mint,
            source=source,
            observed_at=observed_at,
            price_usd=float(snapshot.get("price_usd") or 0.0),
            liquidity_usd=float(snapshot.get("liquidity_usd") or 0.0),
            token_age_minutes=float(snapshot.get("token_age_minutes") or 0.0),
            holder_count=int(snapshot.get("holder_count") or 0),
            top_holder_percent=float(snapshot.get("top_holder_percent") or 100.0),
            top_10_holder_percent=float(snapshot.get("top_10_holder_percent") or 100.0),
            mint_revoked=bool(snapshot.get("mint_revoked")),
            freeze_revoked=bool(snapshot.get("freeze_revoked")),
            raw_json=payload,
        )
        db.add(row)
        db.commit()


def load_latest_token_snapshot(token_mint: str, source: str | None = None) -> dict[str, Any] | None:
    try:
        with SessionLocal() as db:
            q = db.query(HistoricalTokenSnapshot).filter(HistoricalTokenSnapshot.token_mint == token_mint)
            if source:
                q = q.filter(HistoricalTokenSnapshot.source == source)
            row = q.order_by(HistoricalTokenSnapshot.observed_at.desc()).first()
            if not row:
                return None
            try:
                return json.loads(row.raw_json)
            except Exception:
                return {
                    "token_mint": token_mint,
                    "source": row.source,
                    "observed_at": row.observed_at.isoformat(),
                    "price_usd": row.price_usd,
                    "liquidity_usd": row.liquidity_usd,
                    "token_age_minutes": row.token_age_minutes,
                    "holder_count": row.holder_count,
                    "top_holder_percent": row.top_holder_percent,
                    "top_10_holder_percent": row.top_10_holder_percent,
                    "mint_revoked": row.mint_revoked,
                    "freeze_revoked": row.freeze_revoked,
                }
    except OperationalError:
        return None


def cache_price_point(token_mint: str, source: str, unix_timestamp: int, price_usd: float, raw: dict[str, Any] | None = None) -> None:
    with SessionLocal() as db:
        row = HistoricalPricePoint(
            token_mint=token_mint,
            source=source,
            unix_timestamp=int(unix_timestamp),
            price_usd=float(price_usd),
            raw_json=json.dumps(raw or {}, separators=(",", ":"), sort_keys=True, default=str),
        )
        db.add(row)
        db.commit()


def load_price_point(token_mint: str, unix_timestamp: int, source: str | None = None, tolerance_seconds: int = 120) -> float | None:
    try:
        with SessionLocal() as db:
            q = db.query(HistoricalPricePoint).filter(HistoricalPricePoint.token_mint == token_mint)
            if source:
                q = q.filter(HistoricalPricePoint.source == source)
            rows = q.order_by(HistoricalPricePoint.unix_timestamp.asc()).all()
            if not rows:
                return None
            target = int(unix_timestamp)
            best: HistoricalPricePoint | None = None
            best_gap = None
            for row in rows:
                gap = abs(int(row.unix_timestamp) - target)
                if gap <= tolerance_seconds and (best_gap is None or gap < best_gap):
                    best = row
                    best_gap = gap
            return float(best.price_usd) if best else None
    except OperationalError:
        return None
