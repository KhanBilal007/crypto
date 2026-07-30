"""Audit event builders and decision reconstruction helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from abtp.domain import AuditEvent, AuditEventType
from abtp.domain.models import JsonValue
from abtp.paper import PaperTradingCycleResult
from abtp.repositories import AuditRepository
from abtp.repositories.serialization import ensure_no_secret_keys


@dataclass(frozen=True, slots=True)
class DecisionAuditTrail:
    """Reconstructed audit trail for one decision correlation id."""

    correlation_id: str
    events: tuple[AuditEvent, ...]

    @property
    def risk_rejection_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        for event in self.events:
            if str(event.event_type) == AuditEventType.RISK_DECISION.value:
                reason = event.payload.get("risk_rejection_reasons") or event.payload.get("reasons")
                if reason:
                    reasons.extend(item for item in reason.split("|") if item)
        return tuple(reasons)

    @property
    def blocked_trade_reasons(self) -> tuple[str, ...]:
        return tuple(
            event.payload["blocked_reason"]
            for event in self.events
            if "blocked_reason" in event.payload and event.payload["blocked_reason"]
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "correlation_id": self.correlation_id,
            "event_count": len(self.events),
            "event_types": [str(event.event_type) for event in self.events],
            "risk_rejection_reasons": list(self.risk_rejection_reasons),
            "blocked_trade_reasons": list(self.blocked_trade_reasons),
        }


class DecisionAuditRecorder:
    """Append-only audit recorder for platform decision cycles."""

    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    def append(self, event: AuditEvent) -> str:
        ensure_no_secret_keys(event.payload)
        return self._repository.append(event)

    def append_many(self, events: tuple[AuditEvent, ...]) -> tuple[str, ...]:
        return tuple(self.append(event) for event in events)

    def reconstruct(self, correlation_id: str) -> DecisionAuditTrail:
        return DecisionAuditTrail(
            correlation_id=correlation_id,
            events=self._repository.list_by_correlation(correlation_id),
        )


def build_audit_event(
    *,
    event_type: AuditEventType | str,
    occurred_at: datetime,
    payload: Mapping[str, JsonValue],
    causation_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> AuditEvent:
    """Build a domain audit event after validating sensitive keys."""

    ensure_no_secret_keys(payload)
    return AuditEvent(
        event_type=event_type,
        occurred_at=occurred_at,
        payload={key: str(value) if value is not None else "" for key, value in payload.items()},
        causation_id=causation_id,
        correlation_id=correlation_id,
    )


def build_paper_cycle_audit_events(
    cycle: PaperTradingCycleResult,
    *,
    correlation_id: UUID | None = None,
) -> tuple[AuditEvent, ...]:
    """Build audit events needed to reconstruct one paper decision cycle."""

    active_correlation = correlation_id or uuid4()
    occurred_at = cycle.snapshot.received_at
    events = [
        build_audit_event(
            event_type=AuditEventType.MARKET_INPUT,
            occurred_at=occurred_at,
            payload={
                "pair": cycle.snapshot.candle.pair.symbol,
                "price": str(cycle.snapshot.candle.close),
                "data_latency_ms": str(cycle.snapshot.health.latency_ms),
                "data_health": cycle.snapshot.health.status,
            },
            correlation_id=active_correlation,
        ),
        build_audit_event(
            event_type=AuditEventType.FEATURE_VECTOR,
            occurred_at=cycle.features.generated_at,
            payload={
                "feature_schema_version": cycle.features.schema_version,
                "inputs_ref": cycle.features.inputs_ref,
                "quality": cycle.features.quality.trust_level.value,
                "flags": "|".join(cycle.features.flags),
            },
            correlation_id=active_correlation,
        ),
        build_audit_event(
            event_type="market_regime",
            occurred_at=cycle.regime.generated_at,
            payload={
                "regime": cycle.regime.label.value,
                "confidence": str(cycle.regime.confidence),
                "reasons": "|".join(cycle.regime.reasons),
            },
            correlation_id=active_correlation,
        ),
    ]
    if cycle.strategy_evaluation is not None:
        events.append(
            build_audit_event(
                event_type=AuditEventType.SIGNAL,
                occurred_at=cycle.strategy_evaluation.generated_at,
                payload={
                    "strategy": cycle.strategy_evaluation.strategy_name,
                    "direction": cycle.strategy_evaluation.signal.direction.value,
                    "confidence": str(cycle.strategy_evaluation.signal.confidence),
                    "reasons": "|".join(cycle.strategy_evaluation.reasons),
                },
                correlation_id=active_correlation,
            )
        )
    if cycle.risk_decision_status is not None:
        risk_reason = (
            "risk engine rejected proposed paper order"
            if cycle.risk_decision_status == "rejected"
            else "risk engine approved proposed paper order"
        )
        events.append(
            build_audit_event(
                event_type=AuditEventType.RISK_DECISION,
                occurred_at=occurred_at,
                payload={
                    "status": cycle.risk_decision_status,
                    "risk_rejection_reasons": (
                        risk_reason if cycle.risk_decision_status == "rejected" else ""
                    ),
                    "reasons": risk_reason,
                },
                correlation_id=active_correlation,
            )
        )
    if cycle.execution_result is not None:
        events.append(
            build_audit_event(
                event_type=AuditEventType.ORDER_INTENT,
                occurred_at=occurred_at,
                payload={
                    "order_intent_id": str(cycle.execution_result.intent.id),
                    "status": cycle.execution_result.status.value,
                    "accepted": str(cycle.execution_result.accepted),
                    "reason": cycle.execution_result.reason or "",
                },
                causation_id=cycle.execution_result.intent.id,
                correlation_id=active_correlation,
            )
        )
    if cycle.skipped_reason is not None:
        events.append(
            build_audit_event(
                event_type="blocked_trade",
                occurred_at=occurred_at,
                payload={
                    "blocked_reason": cycle.skipped_reason,
                    "data_health": cycle.snapshot.health.status,
                },
                correlation_id=active_correlation,
            )
        )
    return tuple(events)
