from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SystemControlState:
    emergency_stop: bool = False
    sell_all_requested: bool = False
    approved_intents: list[str] | None = None
    rejected_intents: list[str] | None = None
    updated_at_utc: str = ""

    def normalized(self) -> "SystemControlState":
        self.approved_intents = list(dict.fromkeys(self.approved_intents or []))
        self.rejected_intents = list(dict.fromkeys(self.rejected_intents or []))
        if not self.updated_at_utc:
            self.updated_at_utc = _utcnow().isoformat(timespec="seconds")
        return self


def _path() -> Path:
    return Path(settings.CONTROL_STATE_PATH)


def load_state() -> SystemControlState:
    path = _path()
    if not path.exists():
        return SystemControlState().normalized()

    try:
        payload = json.loads(path.read_text())
    except Exception:
        return SystemControlState().normalized()

    state = SystemControlState(
        emergency_stop=bool(payload.get("emergency_stop", False)),
        sell_all_requested=bool(payload.get("sell_all_requested", False)),
        approved_intents=list(payload.get("approved_intents") or []),
        rejected_intents=list(payload.get("rejected_intents") or []),
        updated_at_utc=str(payload.get("updated_at_utc") or ""),
    )
    return state.normalized()


def save_state(state: SystemControlState) -> SystemControlState:
    state = state.normalized()
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2, sort_keys=True))
    tmp.replace(path)
    return state


def set_emergency_stop(enabled: bool) -> SystemControlState:
    state = load_state()
    state.emergency_stop = enabled
    state.updated_at_utc = _utcnow().isoformat(timespec="seconds")
    return save_state(state)


def request_sell_all() -> SystemControlState:
    state = load_state()
    state.sell_all_requested = True
    state.updated_at_utc = _utcnow().isoformat(timespec="seconds")
    return save_state(state)


def clear_sell_all_request() -> SystemControlState:
    state = load_state()
    state.sell_all_requested = False
    state.updated_at_utc = _utcnow().isoformat(timespec="seconds")
    return save_state(state)


def approve_intent(intent_id: str) -> SystemControlState:
    state = load_state()
    if intent_id not in state.approved_intents:
        state.approved_intents.append(intent_id)
    if intent_id in state.rejected_intents:
        state.rejected_intents.remove(intent_id)
    state.updated_at_utc = _utcnow().isoformat(timespec="seconds")
    return save_state(state)


def reject_intent(intent_id: str) -> SystemControlState:
    state = load_state()
    if intent_id not in state.rejected_intents:
        state.rejected_intents.append(intent_id)
    if intent_id in state.approved_intents:
        state.approved_intents.remove(intent_id)
    state.updated_at_utc = _utcnow().isoformat(timespec="seconds")
    return save_state(state)


def consume_approval(intent_id: str) -> bool:
    state = load_state()
    if intent_id not in state.approved_intents:
        return False
    state.approved_intents.remove(intent_id)
    state.updated_at_utc = _utcnow().isoformat(timespec="seconds")
    save_state(state)
    return True


def is_approved(intent_id: str) -> bool:
    state = load_state()
    return intent_id in state.approved_intents


def is_rejected(intent_id: str) -> bool:
    state = load_state()
    return intent_id in state.rejected_intents
