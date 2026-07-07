from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models import TradeAuditLog


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_SENSITIVE_KEYS = {
    "private_key",
    "seed_phrase",
    "telegram_bot_token",
    "helius_api_key",
    "birdeye_api_key",
    "command_bridge_token",
    "signed_transaction",
    "raw_transaction",
    "transaction",
    "swap_transaction",
    "swap_tx",
    "tx_payload",
}


def _redact(value: Any, key: str | None = None) -> Any:
    if key and any(token in key.lower() for token in _SENSITIVE_KEYS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, key) for v in value]
    return value


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    intent_id: str = "",
    side: str = "",
    token_mint: str = "",
    message: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        TradeAuditLog(
            intent_id=intent_id,
            event_type=event_type,
            side=side,
            token_mint=token_mint,
            message=message,
            details_json=json.dumps(_redact(details or {}), separators=(",", ":"), sort_keys=True, default=str),
            created_at=_utcnow(),
        )
    )
