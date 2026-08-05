"""Structured logging helpers with sensitive-field redaction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from abtp.data import normalize_timestamp
from abtp.domain.models import JsonValue

SENSITIVE_KEY_PARTS = ("secret", "api_key", "password", "passphrase", "token", "credential")
REDACTED_VALUE = "[REDACTED]"


class LogLevel(StrEnum):
    """Structured log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class StructuredLogRecord:
    """One JSON-compatible structured log record."""

    timestamp: datetime
    level: LogLevel
    component: str
    event: str
    message: str
    fields: Mapping[str, JsonValue]
    correlation_id: str | None = None
    causation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", normalize_timestamp(self.timestamp))
        for value, field_name in (
            (self.component, "log component"),
            (self.event, "log event"),
            (self.message, "log message"),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} is required")
        object.__setattr__(self, "fields", redact_sensitive_fields(self.fields))

    def as_dict(self) -> dict[str, JsonValue]:
        """Return a JSON-compatible record."""

        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "component": self.component,
            "event": self.event,
            "message": self.message,
            "fields": dict(self.fields),
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }


class InMemoryStructuredLogger:
    """Deterministic structured logger for tests and future adapters."""

    def __init__(self) -> None:
        self._records: list[StructuredLogRecord] = []

    @property
    def records(self) -> tuple[StructuredLogRecord, ...]:
        return tuple(self._records)

    def emit(self, record: StructuredLogRecord) -> StructuredLogRecord:
        """Append a structured log record."""

        self._records.append(record)
        return record

    def log(
        self,
        *,
        timestamp: datetime,
        level: LogLevel,
        component: str,
        event: str,
        message: str,
        fields: Mapping[str, JsonValue] | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> StructuredLogRecord:
        """Build and append a structured record."""

        return self.emit(
            StructuredLogRecord(
                timestamp=timestamp,
                level=level,
                component=component,
                event=event,
                message=message,
                fields=fields or {},
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
        )

    def by_correlation(self, correlation_id: str) -> tuple[StructuredLogRecord, ...]:
        return tuple(record for record in self.records if record.correlation_id == correlation_id)


def redact_sensitive_fields(payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    """Redact values whose keys look secret-like, recursively."""

    redacted: dict[str, JsonValue] = {}
    for key, value in payload.items():
        if _is_sensitive_key(key):
            redacted[key] = REDACTED_VALUE
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_fields(value)
        elif isinstance(value, list):
            redacted[key] = [_redact_list_item(item) for item in value]
        else:
            redacted[key] = value
    return redacted


def log_blocked_decision(
    logger: InMemoryStructuredLogger,
    *,
    occurred_at: datetime,
    component: str,
    reason: str,
    correlation_id: str,
    fields: Mapping[str, JsonValue] | None = None,
) -> StructuredLogRecord:
    """Log a blocked or rejected decision without hiding the reason."""

    return logger.log(
        timestamp=occurred_at,
        level=LogLevel.WARNING,
        component=component,
        event="decision_blocked",
        message=reason,
        fields={"blocked_reason": reason, **(fields or {})},
        correlation_id=correlation_id,
    )


def _redact_list_item(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return redact_sensitive_fields(value)
    if isinstance(value, list):
        return [_redact_list_item(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
