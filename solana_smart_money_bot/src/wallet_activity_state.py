from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _path() -> Path:
    return Path(settings.BASE_DIR) / "data" / "wallet_activity_snapshot.json"


@dataclass
class WalletActivitySnapshot:
    generated_at_utc: str = ""
    source: str = "unknown"
    total_active_wallets: int = 0
    total_recent_transactions: int = 0
    wallets_with_recent_transactions: int = 0
    wallets_with_zero_recent_transactions: int = 0
    parser_attempted: int = 0
    parser_succeeded: int = 0
    parser_failed: int = 0
    buy_like_transactions: int = 0
    buy_signals: int = 0
    api_errors: int = 0
    rate_limit_errors: int = 0
    forward_signals: int = 0
    zero_signals_cause: str = "unknown"
    rejection_breakdown: dict[str, int] = field(default_factory=dict)
    wallets: list[dict[str, Any]] = field(default_factory=list)


def load_wallet_activity_snapshot() -> WalletActivitySnapshot:
    path = _path()
    if not path.exists():
        return WalletActivitySnapshot()
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return WalletActivitySnapshot()
    return WalletActivitySnapshot(
        generated_at_utc=str(payload.get("generated_at_utc") or ""),
        source=str(payload.get("source") or "unknown"),
        total_active_wallets=int(payload.get("total_active_wallets") or 0),
        total_recent_transactions=int(payload.get("total_recent_transactions") or 0),
        wallets_with_recent_transactions=int(payload.get("wallets_with_recent_transactions") or 0),
        wallets_with_zero_recent_transactions=int(payload.get("wallets_with_zero_recent_transactions") or 0),
        parser_attempted=int(payload.get("parser_attempted") or 0),
        parser_succeeded=int(payload.get("parser_succeeded") or 0),
        parser_failed=int(payload.get("parser_failed") or 0),
        buy_like_transactions=int(payload.get("buy_like_transactions") or 0),
        buy_signals=int(payload.get("buy_signals") or 0),
        api_errors=int(payload.get("api_errors") or 0),
        rate_limit_errors=int(payload.get("rate_limit_errors") or 0),
        forward_signals=int(payload.get("forward_signals") or 0),
        zero_signals_cause=str(payload.get("zero_signals_cause") or "unknown"),
        rejection_breakdown=dict(payload.get("rejection_breakdown") or {}),
        wallets=list(payload.get("wallets") or []),
    )


def save_wallet_activity_snapshot(snapshot: WalletActivitySnapshot | dict[str, Any]) -> WalletActivitySnapshot:
    if isinstance(snapshot, dict):
        snapshot = WalletActivitySnapshot(
            generated_at_utc=str(snapshot.get("generated_at_utc") or _utcnow().isoformat(timespec="seconds")),
            source=str(snapshot.get("source") or "unknown"),
            total_active_wallets=int(snapshot.get("total_active_wallets") or 0),
            total_recent_transactions=int(snapshot.get("total_recent_transactions") or 0),
            wallets_with_recent_transactions=int(snapshot.get("wallets_with_recent_transactions") or 0),
            wallets_with_zero_recent_transactions=int(snapshot.get("wallets_with_zero_recent_transactions") or 0),
            parser_attempted=int(snapshot.get("parser_attempted") or 0),
            parser_succeeded=int(snapshot.get("parser_succeeded") or 0),
            parser_failed=int(snapshot.get("parser_failed") or 0),
            buy_like_transactions=int(snapshot.get("buy_like_transactions") or 0),
            buy_signals=int(snapshot.get("buy_signals") or 0),
            api_errors=int(snapshot.get("api_errors") or 0),
            rate_limit_errors=int(snapshot.get("rate_limit_errors") or 0),
            forward_signals=int(snapshot.get("forward_signals") or 0),
            zero_signals_cause=str(snapshot.get("zero_signals_cause") or "unknown"),
            rejection_breakdown=dict(snapshot.get("rejection_breakdown") or {}),
            wallets=list(snapshot.get("wallets") or []),
        )

    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(snapshot), indent=2, sort_keys=True, default=str))
    tmp.replace(path)
    return snapshot
