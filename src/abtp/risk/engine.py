"""Mandatory Risk Management Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from abtp.data import normalize_timestamp
from abtp.domain import AuditEvent, AuditEventType, RiskDecision, RiskDecisionStatus
from abtp.repositories import AuditRepository, RiskDecisionRepository
from abtp.risk.rules import (
    RiskPortfolioContext,
    evaluate_risk_checks,
    position_size_for_request,
)
from abtp.strategies import StrategyEvaluation


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Fail-closed policy limits for Stage 022."""

    policy_version: str = "stage-022.v1"
    max_risk_per_trade_pct: Decimal = Decimal("0.01")
    max_position_pct: Decimal = Decimal("0.25")
    min_cash_reserve_pct: Decimal = Decimal("0.20")
    max_drawdown_pct: Decimal = Decimal("0.10")
    max_daily_loss_pct: Decimal = Decimal("0.03")
    max_weekly_loss_pct: Decimal = Decimal("0.07")
    max_spread_bps: Decimal = Decimal("50")
    max_slippage_bps: Decimal = Decimal("25")
    fee_bps: Decimal = Decimal("10")
    min_signal_confidence: Decimal = Decimal("0.35")
    require_stop_loss: bool = True
    kill_switch_active: bool = False

    def __post_init__(self) -> None:
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")
        for value, field_name in (
            (self.max_risk_per_trade_pct, "max_risk_per_trade_pct"),
            (self.max_position_pct, "max_position_pct"),
            (self.min_cash_reserve_pct, "min_cash_reserve_pct"),
            (self.max_drawdown_pct, "max_drawdown_pct"),
            (self.max_daily_loss_pct, "max_daily_loss_pct"),
            (self.max_weekly_loss_pct, "max_weekly_loss_pct"),
            (self.min_signal_confidence, "min_signal_confidence"),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{field_name} must be between 0 and 1")
        if self.fee_bps < Decimal("0"):
            raise ValueError("fee_bps cannot be negative")
        if self.max_spread_bps < Decimal("0") or self.max_slippage_bps < Decimal("0"):
            raise ValueError("spread/slippage ceilings cannot be negative")


@dataclass(frozen=True, slots=True)
class RiskEvaluationRequest:
    """Inputs for evaluating whether a signal may become a future order intent."""

    strategy_evaluation: StrategyEvaluation
    portfolio: RiskPortfolioContext
    evaluated_at: datetime
    proposed_order_id: UUID = field(default_factory=uuid4)
    entry_price: Decimal | None = None
    spread_bps: Decimal = Decimal("0")
    estimated_slippage_bps: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluated_at", normalize_timestamp(self.evaluated_at))
        if self.entry_price is not None and self.entry_price <= Decimal("0"):
            raise ValueError("entry_price must be positive when supplied")
        if self.spread_bps < Decimal("0") or self.estimated_slippage_bps < Decimal("0"):
            raise ValueError("spread_bps and estimated_slippage_bps cannot be negative")


@dataclass(frozen=True, slots=True)
class RiskEngineConfig:
    """Persistence and audit behavior for risk decisions."""

    persist_decisions: bool = True
    audit_decisions: bool = True


class RiskManagementEngine:
    """Mandatory fail-closed gate for strategy signals before order creation."""

    def __init__(
        self,
        *,
        policy: RiskPolicy | None = None,
        config: RiskEngineConfig | None = None,
        risk_repository: RiskDecisionRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self._policy = policy or RiskPolicy()
        self._config = config or RiskEngineConfig()
        self._risk_repository = risk_repository
        self._audit_repository = audit_repository

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    def evaluate(self, request: RiskEvaluationRequest) -> RiskDecision:
        """Evaluate a signal and return an explicit allow/reject decision."""

        position_size = position_size_for_request(request=request, policy=self.policy)
        checks = evaluate_risk_checks(
            request=request,
            policy=self.policy,
            position_size=position_size,
        )
        approved = all(check.passed for check in checks)
        decision = RiskDecision(
            order_intent_id=request.proposed_order_id,
            status=RiskDecisionStatus.APPROVED if approved else RiskDecisionStatus.REJECTED,
            checks=checks,
            evaluated_at=request.evaluated_at,
            policy_version=self.policy.policy_version,
            rationale=(
                "Risk checks approved proposed order id."
                if approved
                else "Risk checks rejected proposed order id."
            ),
            max_position_size=(
                position_size.max_quantity
                if approved and position_size is not None
                else Decimal("0")
            ),
            stop_loss_required=self.policy.require_stop_loss,
            kill_switch_active=self.policy.kill_switch_active,
        )
        self._persist(decision)
        self._audit(decision, request)
        return decision

    def _persist(self, decision: RiskDecision) -> None:
        if self._config.persist_decisions and self._risk_repository is not None:
            self._risk_repository.append(decision)

    def _audit(self, decision: RiskDecision, request: RiskEvaluationRequest) -> None:
        if not self._config.audit_decisions or self._audit_repository is None:
            return
        event = AuditEvent(
            event_type=AuditEventType.RISK_DECISION,
            occurred_at=decision.evaluated_at,
            payload={
                "order_intent_id": str(decision.order_intent_id),
                "signal_source": request.strategy_evaluation.signal.source,
                "status": decision.status.value,
                "allow": str(decision.allowed),
                "reject": str(decision.rejected),
                "policy_version": decision.policy_version,
                "reasons": ",".join(decision.reasons),
                "max_position_size": str(decision.max_position_size),
            },
            causation_id=decision.order_intent_id,
            correlation_id=decision.order_intent_id,
        )
        self._audit_repository.append(event)
