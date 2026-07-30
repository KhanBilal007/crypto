"""Deterministic paper-trade readiness checklist for Stage 071."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.exchanges.health import ExchangeHealthScore, ExchangeHealthStatus
from abtp.intelligence import FinalInvestmentDecision, InstitutionalDecisionRecord
from abtp.protection import CapitalPreservationDecision

if TYPE_CHECKING:
    from abtp.api.paper import PaperStatusResponse

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class PaperTradeChecklistPolicy:
    """Conservative paper command-center thresholds."""

    min_confidence_score: Decimal = Decimal("0.60")
    max_risk_score: Decimal = Decimal("0.55")
    min_paper_cash: Decimal = Decimal("1")
    max_daily_loss_pct: Decimal = Decimal("0.03")
    max_weekly_loss_pct: Decimal = Decimal("0.07")
    require_stop_loss: bool = True
    policy_version: str = "stage-071.checklist.v1"

    def __post_init__(self) -> None:
        for name, value in (
            ("min_confidence_score", self.min_confidence_score),
            ("max_risk_score", self.max_risk_score),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
            ("max_weekly_loss_pct", self.max_weekly_loss_pct),
        ):
            if not DECIMAL_ZERO <= value <= DECIMAL_ONE:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.min_paper_cash < DECIMAL_ZERO:
            raise ValueError("min_paper_cash cannot be negative")
        if not self.policy_version.strip():
            raise ValueError("policy_version is required")


@dataclass(frozen=True, slots=True)
class PaperAccountSummary:
    """Operator-facing paper account summary."""

    cash: Decimal
    equity: Decimal
    base_quantity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees_paid: Decimal
    drawdown_pct: Decimal
    open_positions: int

    def __post_init__(self) -> None:
        for name, value in (
            ("cash", self.cash),
            ("equity", self.equity),
            ("base_quantity", self.base_quantity),
            ("fees_paid", self.fees_paid),
            ("drawdown_pct", self.drawdown_pct),
        ):
            if value < DECIMAL_ZERO:
                raise ValueError(f"{name} cannot be negative")
        if self.open_positions < 0:
            raise ValueError("open_positions cannot be negative")

    @classmethod
    def from_paper_status(cls, status: PaperStatusResponse) -> PaperAccountSummary:
        """Create an account summary from the existing paper API status."""

        portfolio = status.portfolio
        mark_price = status.current_btc_price or portfolio.average_entry_price
        unrealized = (
            (mark_price - portfolio.average_entry_price) * portfolio.base_quantity
            if portfolio.base_quantity > DECIMAL_ZERO and mark_price > DECIMAL_ZERO
            else DECIMAL_ZERO
        )
        return cls(
            cash=portfolio.cash,
            equity=portfolio.equity,
            base_quantity=portfolio.base_quantity,
            realized_pnl=portfolio.realized_pnl,
            unrealized_pnl=unrealized,
            fees_paid=portfolio.fees_paid,
            drawdown_pct=portfolio.drawdown_pct,
            open_positions=1 if portfolio.base_quantity > DECIMAL_ZERO else 0,
        )

    def as_dict(self) -> dict[str, str | int]:
        return {
            "cash": str(self.cash),
            "equity": str(self.equity),
            "base_quantity": str(self.base_quantity),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "fees_paid": str(self.fees_paid),
            "drawdown_pct": str(self.drawdown_pct),
            "open_positions": self.open_positions,
        }


@dataclass(frozen=True, slots=True)
class PaperTradeChecklistInput:
    """Inputs required before a paper trade may be reviewed."""

    decision: InstitutionalDecisionRecord
    paper_status: PaperStatusResponse
    data_quality: DataQualityStatus
    exchange_health: ExchangeHealthScore | None
    generated_at: datetime
    capital_preservation: CapitalPreservationDecision | None = None
    max_paper_position_size: Decimal = DECIMAL_ZERO
    stop_loss_required: bool = True
    stop_loss_price: Decimal | None = None
    daily_loss_pct: Decimal = DECIMAL_ZERO
    weekly_loss_pct: Decimal = DECIMAL_ZERO
    capital_protection_block: bool = False
    crash_protection_active: bool = False
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_paper_position_size < DECIMAL_ZERO:
            raise ValueError("max_paper_position_size cannot be negative")
        if self.stop_loss_price is not None and self.stop_loss_price <= DECIMAL_ZERO:
            raise ValueError("stop_loss_price must be positive when supplied")
        if self.daily_loss_pct > DECIMAL_ONE or self.weekly_loss_pct > DECIMAL_ONE:
            raise ValueError("loss percentages cannot exceed 1")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def account(self) -> PaperAccountSummary:
        return PaperAccountSummary.from_paper_status(self.paper_status)


@dataclass(frozen=True, slots=True)
class PaperTradeChecklistResult:
    """Deterministic paper trade readiness result."""

    passed: bool
    blocked_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    account: PaperAccountSummary
    max_paper_position_size: Decimal
    stop_loss_required: bool
    stop_loss_price: Decimal | None
    data_quality: DataQualityStatus
    generated_at: datetime
    policy_version: str
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_paper_position_size < DECIMAL_ZERO:
            raise ValueError("max_paper_position_size cannot be negative")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def paper_trade_ready(self) -> bool:
        return self.passed and not self.blocked_reasons and self.data_quality.is_trusted

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "paper_trade_ready": self.paper_trade_ready,
            "blocked_reasons": list(self.blocked_reasons),
            "warnings": list(self.warnings),
            "account": self.account.as_dict(),
            "max_paper_position_size": str(self.max_paper_position_size),
            "stop_loss_required": self.stop_loss_required,
            "stop_loss_price": None if self.stop_loss_price is None else str(self.stop_loss_price),
            "data_quality": self.data_quality.trust_level.value,
            "data_quality_flags": list(self.data_quality.flags),
            "generated_at": self.generated_at.isoformat(),
            "policy_version": self.policy_version,
            "source_refs": dict(self.source_refs),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "passed": str(self.passed),
            "paper_trade_ready": str(self.paper_trade_ready),
            "blocked_reasons": "|".join(self.blocked_reasons),
            "warnings": "|".join(self.warnings),
            "cash": str(self.account.cash),
            "equity": str(self.account.equity),
            "drawdown_pct": str(self.account.drawdown_pct),
            "max_paper_position_size": str(self.max_paper_position_size),
            "stop_loss_required": str(self.stop_loss_required),
            "stop_loss_price": "" if self.stop_loss_price is None else str(self.stop_loss_price),
            "data_quality": self.data_quality.trust_level.value,
            "policy_version": self.policy_version,
        }

    def create_order_intent(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper trade checklist cannot create order intents")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper trade checklist cannot approve risk")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper trade checklist cannot submit orders")


def evaluate_paper_trade_checklist(
    inputs: PaperTradeChecklistInput,
    *,
    policy: PaperTradeChecklistPolicy | None = None,
) -> PaperTradeChecklistResult:
    """Evaluate paper command-center readiness without creating orders."""

    active_policy = policy or PaperTradeChecklistPolicy()
    reasons: list[str] = []
    warnings: list[str] = []
    issues = [*inputs.data_quality.issues, *inputs.decision.quality.issues]
    _decision_checks(inputs, active_policy, reasons)
    _paper_status_checks(inputs, active_policy, reasons)
    _quality_checks(inputs, reasons, issues)
    _exchange_health_checks(inputs, reasons, warnings, issues)
    _protection_checks(inputs, reasons, issues)
    _risk_and_stop_checks(inputs, active_policy, reasons)
    data_quality = _result_quality(inputs, reasons, issues)
    return PaperTradeChecklistResult(
        passed=not reasons and data_quality.is_trusted,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
        account=inputs.account,
        max_paper_position_size=inputs.max_paper_position_size,
        stop_loss_required=inputs.stop_loss_required or active_policy.require_stop_loss,
        stop_loss_price=inputs.stop_loss_price,
        data_quality=data_quality,
        generated_at=inputs.generated_at,
        policy_version=active_policy.policy_version,
        source_refs=inputs.source_refs,
    )


def _decision_checks(
    inputs: PaperTradeChecklistInput,
    policy: PaperTradeChecklistPolicy,
    reasons: list[str],
) -> None:
    if not inputs.decision.advisory_only:
        reasons.append("decision record is not advisory-only")
    if inputs.decision.final_decision is not FinalInvestmentDecision.FAVORABLE_REVIEW:
        reasons.append(f"decision is {inputs.decision.final_decision.value}")
    if not inputs.decision.actionable_review:
        reasons.append("Stage 070 decision is not actionable for paper review")
    if inputs.decision.confidence_score < policy.min_confidence_score:
        reasons.append("decision confidence is below paper checklist threshold")
    if inputs.decision.risk_assessment.risk_score > policy.max_risk_score:
        reasons.append("decision risk score exceeds paper checklist threshold")
    if inputs.decision.risk_assessment.block_new_entries:
        reasons.append("decision risk assessment blocks new entries")


def _paper_status_checks(
    inputs: PaperTradeChecklistInput,
    policy: PaperTradeChecklistPolicy,
    reasons: list[str],
) -> None:
    status = inputs.paper_status
    if status.paused:
        reasons.append("paper trading is paused")
    if status.kill_switch_active:
        reasons.append("paper kill switch is active")
    if status.data_health in {"stale", "degraded", "unavailable"}:
        reasons.append(f"paper data health is {status.data_health}")
    if status.blocked_reason and status.blocked_reason != "none":
        reasons.append(status.blocked_reason)
    if inputs.account.cash < policy.min_paper_cash:
        reasons.append("paper cash is below minimum")
    if inputs.daily_loss_pct <= -policy.max_daily_loss_pct:
        reasons.append("daily paper loss halt is active")
    if inputs.weekly_loss_pct <= -policy.max_weekly_loss_pct:
        reasons.append("weekly paper loss halt is active")


def _quality_checks(
    inputs: PaperTradeChecklistInput,
    reasons: list[str],
    _issues: list[DataQualityIssue],
) -> None:
    if not inputs.data_quality.is_trusted:
        reasons.append("data quality is not trusted")
    if not inputs.decision.quality.is_trusted:
        reasons.append("decision quality is not trusted")


def _exchange_health_checks(
    inputs: PaperTradeChecklistInput,
    reasons: list[str],
    warnings: list[str],
    issues: list[DataQualityIssue],
) -> None:
    if inputs.exchange_health is None:
        reasons.append("exchange health evidence is missing")
        return
    exchange = inputs.exchange_health
    issues.extend(exchange.quality.issues)
    if exchange.status is ExchangeHealthStatus.UNAVAILABLE:
        reasons.append("exchange health is unavailable")
    elif exchange.status is ExchangeHealthStatus.MANUAL_REVIEW:
        reasons.append("exchange health requires manual review")
    elif exchange.status is ExchangeHealthStatus.DEGRADED:
        warnings.append("exchange health is degraded")
    if exchange.permission_gate.block_new_entries:
        reasons.append("exchange health blocks new entries")
    if exchange.permission_gate.pause_trading:
        reasons.append("exchange health pauses trading")
    if not exchange.quality.is_trusted:
        reasons.append("exchange health quality is not trusted")
    reasons.extend(exchange.rejection_reasons)


def _protection_checks(
    inputs: PaperTradeChecklistInput,
    reasons: list[str],
    issues: list[DataQualityIssue],
) -> None:
    if inputs.capital_protection_block:
        reasons.append("capital protection blocks paper review")
    if inputs.crash_protection_active:
        reasons.append("crash protection is active")
    if inputs.capital_preservation is None:
        return
    decision = inputs.capital_preservation
    issues.extend(decision.quality.issues)
    if decision.block_new_trades:
        reasons.append("capital preservation blocks new trades")
    if not decision.quality.is_trusted:
        reasons.append("capital preservation quality is not trusted")


def _risk_and_stop_checks(
    inputs: PaperTradeChecklistInput,
    policy: PaperTradeChecklistPolicy,
    reasons: list[str],
) -> None:
    if inputs.max_paper_position_size <= DECIMAL_ZERO:
        reasons.append("max paper position size is missing")
    if (inputs.stop_loss_required or policy.require_stop_loss) and inputs.stop_loss_price is None:
        reasons.append("stop-loss metadata is required")


def _result_quality(
    inputs: PaperTradeChecklistInput,
    reasons: list[str],
    issues: list[DataQualityIssue],
) -> DataQualityStatus:
    issues.extend(
        DataQualityIssue(
            flag="paper_checklist_block",
            severity=DataTrustLevel.DEGRADED,
            reason=reason,
        )
        for reason in reasons
    )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust = DataTrustLevel.REJECTED
    elif issues:
        trust = DataTrustLevel.DEGRADED
    else:
        trust = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust,
        issues=tuple(issues),
        source_ref="paper:trade_checklist",
        checked_at=inputs.generated_at,
    )
