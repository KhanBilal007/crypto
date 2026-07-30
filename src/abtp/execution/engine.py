"""Paper-safe execution engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from abtp.domain import AuditEvent, AuditEventType, OrderIntent, OrderStatus
from abtp.execution.fills import FillSummary, build_fill_summary
from abtp.execution.order_router import OrderRouteRequest, OrderRouteResult, PaperOrderRouter
from abtp.repositories import AuditRepository, OrderLifecycleEvent, OrderRepository
from abtp.risk import assert_order_intent_has_approved_risk


@dataclass(frozen=True, slots=True)
class ExecutionEngineConfig:
    """Persistence/audit behavior for paper-safe execution."""

    persist_orders: bool = True
    audit_orders: bool = True


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result of one idempotent execution submission."""

    intent: OrderIntent
    idempotency_key: str
    accepted: bool
    status: OrderStatus
    route_result: OrderRouteResult | None
    fill_summary: FillSummary | None
    lifecycle_event_ids: tuple[str, ...]
    audit_event_id: str | None = None
    reason: str | None = None


class PaperSafeExecutionEngine:
    """Submit only risk-approved orders to paper/sandbox routes."""

    def __init__(
        self,
        *,
        router: PaperOrderRouter,
        config: ExecutionEngineConfig | None = None,
        order_repository: OrderRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self._router = router
        self._config = config or ExecutionEngineConfig()
        self._order_repository = order_repository
        self._audit_repository = audit_repository
        self._results_by_idempotency_key: dict[str, ExecutionResult] = {}

    def submit(
        self,
        intent: OrderIntent,
        *,
        idempotency_key: str,
        submitted_at: datetime,
        execution_price: Decimal | None = None,
    ) -> ExecutionResult:
        """Submit a risk-approved order intent idempotently."""

        if idempotency_key in self._results_by_idempotency_key:
            return self._results_by_idempotency_key[idempotency_key]
        try:
            assert_order_intent_has_approved_risk(intent)
        except ValueError as exc:
            result = ExecutionResult(
                intent=intent,
                idempotency_key=idempotency_key,
                accepted=False,
                status=OrderStatus.RISK_REJECTED,
                route_result=None,
                fill_summary=None,
                lifecycle_event_ids=(),
                reason=str(exc),
            )
            self._results_by_idempotency_key[idempotency_key] = result
            return result

        lifecycle_ids: list[str] = []
        self._persist_intent(intent)
        lifecycle_ids.append(
            self._append_lifecycle(
                intent,
                status=OrderStatus.SUBMITTED,
                occurred_at=submitted_at,
                payload={"idempotency_key": idempotency_key},
            )
        )
        route_result = self._router.route(
            OrderRouteRequest(
                intent=intent,
                idempotency_key=idempotency_key,
                submitted_at=submitted_at,
                execution_price=execution_price,
            )
        )
        fill_summary = build_fill_summary(
            route_result.fills,
            requested_quantity=intent.quantity,
        )
        lifecycle_ids.append(
            self._append_lifecycle(
                intent,
                status=route_result.status,
                occurred_at=route_result.submitted_at,
                payload={
                    "exchange_order_id": route_result.exchange_order_id,
                    "route_mode": route_result.route_mode.value,
                    "filled_quantity": str(fill_summary.filled_quantity),
                    "fee_paid": str(fill_summary.fee_paid),
                    "reason": route_result.reason,
                },
            )
        )
        accepted = route_result.status in {OrderStatus.SUBMITTED, OrderStatus.FILLED}
        audit_event_id = self._append_audit(
            intent,
            idempotency_key=idempotency_key,
            status=route_result.status,
            accepted=accepted,
            reason=route_result.reason,
        )
        result = ExecutionResult(
            intent=intent,
            idempotency_key=idempotency_key,
            accepted=accepted,
            status=route_result.status,
            route_result=route_result,
            fill_summary=fill_summary,
            lifecycle_event_ids=tuple(item for item in lifecycle_ids if item),
            audit_event_id=audit_event_id,
            reason=route_result.reason,
        )
        self._results_by_idempotency_key[idempotency_key] = result
        return result

    def _persist_intent(self, intent: OrderIntent) -> None:
        if self._config.persist_orders and self._order_repository is not None:
            self._order_repository.append_intent(intent)

    def _append_lifecycle(
        self,
        intent: OrderIntent,
        *,
        status: OrderStatus,
        occurred_at: datetime,
        payload: dict[str, object],
    ) -> str:
        if not self._config.persist_orders or self._order_repository is None:
            return ""
        return self._order_repository.append_lifecycle_event(
            OrderLifecycleEvent(
                order_intent_id=intent.id,
                status=status,
                occurred_at=occurred_at,
                payload={
                    key: str(value) if value is not None else None for key, value in payload.items()
                },
            )
        )

    def _append_audit(
        self,
        intent: OrderIntent,
        *,
        idempotency_key: str,
        status: OrderStatus,
        accepted: bool,
        reason: str | None,
    ) -> str | None:
        if not self._config.audit_orders or self._audit_repository is None:
            return None
        event = AuditEvent(
            event_type=AuditEventType.ORDER_INTENT,
            occurred_at=intent.created_at,
            payload={
                "order_intent_id": str(intent.id),
                "idempotency_key": idempotency_key,
                "status": status.value,
                "accepted": str(accepted),
                "reason": reason or "",
            },
            causation_id=intent.id,
            correlation_id=intent.id,
        )
        return self._audit_repository.append(event)
