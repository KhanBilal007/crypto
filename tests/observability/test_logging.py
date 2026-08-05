from __future__ import annotations

from datetime import UTC, datetime

from abtp.observability import (
    REDACTED_VALUE,
    InMemoryStructuredLogger,
    LogLevel,
    StructuredLogRecord,
    log_blocked_decision,
    redact_sensitive_fields,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_structured_log_redacts_sensitive_values_recursively() -> None:
    record = StructuredLogRecord(
        timestamp=NOW,
        level=LogLevel.INFO,
        component="fixture",
        event="credential_check",
        message="fixture log",
        fields={
            "api_key": "do-not-leak",
            "nested": {"access_token": "also-secret", "safe": "visible"},
            "items": [{"password": "hidden"}],
        },
        correlation_id="cycle-1",
    )

    payload = record.as_dict()

    assert payload["fields"]["api_key"] == REDACTED_VALUE  # type: ignore[index]
    assert payload["fields"]["nested"]["access_token"] == REDACTED_VALUE  # type: ignore[index]
    assert payload["fields"]["nested"]["safe"] == "visible"  # type: ignore[index]
    assert "do-not-leak" not in str(payload)
    assert "also-secret" not in str(payload)


def test_in_memory_logger_groups_by_correlation_and_records_blocked_reason() -> None:
    logger = InMemoryStructuredLogger()

    log_blocked_decision(
        logger,
        occurred_at=NOW,
        component="paper",
        reason="risk engine rejected proposed paper order",
        correlation_id="cycle-1",
        fields={"status": "rejected"},
    )
    logger.log(
        timestamp=NOW,
        level=LogLevel.INFO,
        component="paper",
        event="heartbeat",
        message="healthy",
        correlation_id="cycle-2",
    )

    records = logger.by_correlation("cycle-1")

    assert len(records) == 1
    assert records[0].level is LogLevel.WARNING
    assert records[0].fields["blocked_reason"] == "risk engine rejected proposed paper order"


def test_redact_sensitive_fields_leaves_safe_payloads_readable() -> None:
    payload = redact_sensitive_fields({"model_version": "v1", "risk_rejects": 1})

    assert payload == {"model_version": "v1", "risk_rejects": 1}
