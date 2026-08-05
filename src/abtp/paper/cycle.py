"""Paper runner cycle contracts for Stage 072."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from abtp.data import normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.paper.command_center import PaperCommandLabel, PaperCommandRecommendation
from abtp.paper.engine import PaperMarketSnapshot, PaperTradingCycleResult

DECIMAL_ZERO = Decimal("0")


class PaperRunnerCycleStatus(StrEnum):
    """Outcome for one Stage 072 paper runner cycle."""

    EXECUTED = "executed"
    SKIPPED = "skipped"
    RISK_REJECTED = "risk_rejected"
    NO_SIGNAL = "no_signal"


@dataclass(frozen=True, slots=True)
class StopLossMetadata:
    """Stop-loss metadata required before any simulated paper fill."""

    stop_loss_price: Decimal
    source_ref: str
    rationale: str

    def __post_init__(self) -> None:
        if self.stop_loss_price <= DECIMAL_ZERO:
            raise ValueError("stop_loss_price must be positive")
        if not self.source_ref.strip():
            raise ValueError("stop-loss source_ref is required")
        if not self.rationale.strip():
            raise ValueError("stop-loss rationale is required")

    def as_dict(self) -> dict[str, str]:
        return {
            "stop_loss_price": str(self.stop_loss_price),
            "source_ref": self.source_ref,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class PaperTradingCycleInput:
    """Inputs for one deterministic paper runner cycle."""

    snapshot: PaperMarketSnapshot
    command: PaperCommandRecommendation
    stop_loss: StopLossMetadata | None
    cycle_id: UUID = field(default_factory=uuid4)
    feature_snapshot_ref: str = "paper_runner:features"
    take_profit_context: str = "operator_review_required"
    max_paper_risk_per_trade: Decimal = Decimal("0.01")
    live_mode_requested: bool = False
    live_credentials_present: bool = False
    safe_mode: bool = True
    kill_switch_active: bool = False
    exchange_health_block: bool = False
    capital_protection_block: bool = False
    portfolio_loss_halt: bool = False
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_paper_risk_per_trade <= DECIMAL_ZERO:
            raise ValueError("max_paper_risk_per_trade must be positive")
        if not self.feature_snapshot_ref.strip():
            raise ValueError("feature_snapshot_ref is required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class PaperTradingRunnerCycleResult:
    """Result of one Stage 072 paper runner cycle."""

    cycle_id: UUID
    status: PaperRunnerCycleStatus
    snapshot: PaperMarketSnapshot
    command: PaperCommandRecommendation
    engine_cycle: PaperTradingCycleResult | None
    blocked_reasons: tuple[str, ...]
    audit_events: tuple[dict[str, JsonValue], ...]
    metrics: Mapping[str, Decimal | str | int]
    summary_text: str
    generated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", PaperRunnerCycleStatus(self.status))
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "metrics", dict(self.metrics))

    @property
    def executed(self) -> bool:
        return self.status is PaperRunnerCycleStatus.EXECUTED

    @property
    def skipped(self) -> bool:
        return self.status is PaperRunnerCycleStatus.SKIPPED

    def as_dict(self) -> dict[str, object]:
        return {
            "cycle_id": str(self.cycle_id),
            "status": self.status.value,
            "command_label": self.command.label.value,
            "executed": self.executed,
            "blocked_reasons": list(self.blocked_reasons),
            "audit_events": list(self.audit_events),
            "metrics": {key: str(value) for key, value in self.metrics.items()},
            "summary_text": self.summary_text,
            "generated_at": self.generated_at.isoformat(),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "cycle_id": str(self.cycle_id),
            "status": self.status.value,
            "command_label": self.command.label.value,
            "paper_trade_ready": str(self.command.paper_trade_ready),
            "blocked_reasons": "|".join(self.blocked_reasons),
            "executed": str(self.executed),
            "price": str(self.snapshot.candle.close),
            "data_health": self.snapshot.health.status,
        }

    def create_live_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper runner cycle cannot create live orders")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper runner cycle cannot submit orders")

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper runner cycle cannot enable live trading")


def blocked_cycle_result(
    cycle_input: PaperTradingCycleInput,
    *,
    reasons: tuple[str, ...],
    generated_at: datetime,
) -> PaperTradingRunnerCycleResult:
    """Build a skipped cycle result without touching the paper engine."""

    return PaperTradingRunnerCycleResult(
        cycle_id=cycle_input.cycle_id,
        status=PaperRunnerCycleStatus.SKIPPED,
        snapshot=cycle_input.snapshot,
        command=cycle_input.command,
        engine_cycle=None,
        blocked_reasons=reasons,
        audit_events=(
            _audit_dict(cycle_input, status=PaperRunnerCycleStatus.SKIPPED, reasons=reasons),
        ),
        metrics=_metrics_dict(cycle_input, status=PaperRunnerCycleStatus.SKIPPED),
        summary_text=_summary_text(PaperRunnerCycleStatus.SKIPPED, reasons),
        generated_at=generated_at,
    )


def cycle_result_from_engine(
    cycle_input: PaperTradingCycleInput,
    engine_cycle: PaperTradingCycleResult,
) -> PaperTradingRunnerCycleResult:
    """Build a runner result from the existing paper engine cycle output."""

    status = _status_from_engine_cycle(engine_cycle)
    reasons = _engine_reasons(engine_cycle)
    return PaperTradingRunnerCycleResult(
        cycle_id=cycle_input.cycle_id,
        status=status,
        snapshot=cycle_input.snapshot,
        command=cycle_input.command,
        engine_cycle=engine_cycle,
        blocked_reasons=reasons,
        audit_events=(_audit_dict(cycle_input, status=status, reasons=reasons),),
        metrics=_metrics_dict(cycle_input, status=status, engine_cycle=engine_cycle),
        summary_text=_summary_text(status, reasons),
        generated_at=cycle_input.snapshot.received_at,
    )


def preflight_block_reasons(cycle_input: PaperTradingCycleInput) -> tuple[str, ...]:
    """Return fail-closed reasons before paper engine routing is allowed."""

    reasons: list[str] = []
    if cycle_input.live_mode_requested:
        reasons.append("live mode is not allowed for paper runner")
    if cycle_input.live_credentials_present:
        reasons.append("live credentials are not allowed for paper runner")
    if not cycle_input.safe_mode:
        reasons.append("safe mode is required for paper runner")
    if cycle_input.command.label is not PaperCommandLabel.BUY_REVIEW:
        reasons.append(f"command center label is {cycle_input.command.label.value}")
    if not cycle_input.command.paper_trade_ready:
        reasons.append("command center did not approve paper review")
    if cycle_input.stop_loss is None:
        reasons.append("stop-loss metadata is required")
    if cycle_input.kill_switch_active:
        reasons.append("paper runner kill switch is active")
    if cycle_input.snapshot.health.is_stale:
        reasons.append("market snapshot is stale")
    if cycle_input.exchange_health_block:
        reasons.append("exchange health blocks paper runner")
    if cycle_input.capital_protection_block:
        reasons.append("capital protection blocks paper runner")
    if cycle_input.portfolio_loss_halt:
        reasons.append("portfolio loss halt blocks paper runner")
    return tuple(dict.fromkeys([*reasons, *cycle_input.command.blocked_reasons]))


def _status_from_engine_cycle(cycle: PaperTradingCycleResult) -> PaperRunnerCycleStatus:
    if cycle.executed:
        return PaperRunnerCycleStatus.EXECUTED
    if cycle.skipped_reason is not None:
        return PaperRunnerCycleStatus.SKIPPED
    if cycle.risk_decision_status == "rejected":
        return PaperRunnerCycleStatus.RISK_REJECTED
    return PaperRunnerCycleStatus.NO_SIGNAL


def _engine_reasons(cycle: PaperTradingCycleResult) -> tuple[str, ...]:
    if cycle.skipped_reason is not None:
        return (cycle.skipped_reason,)
    if cycle.risk_decision_status == "rejected":
        return ("Risk Management Engine rejected simulated paper order",)
    if not cycle.executed:
        return ("strategy did not produce executable paper signal",)
    return ()


def _audit_dict(
    cycle_input: PaperTradingCycleInput,
    *,
    status: PaperRunnerCycleStatus,
    reasons: tuple[str, ...],
) -> dict[str, JsonValue]:
    return {
        "cycle_id": str(cycle_input.cycle_id),
        "status": status.value,
        "pair": cycle_input.snapshot.candle.pair.symbol,
        "price": str(cycle_input.snapshot.candle.close),
        "command_label": cycle_input.command.label.value,
        "blocked_reasons": "|".join(reasons),
        "stop_loss_price": ""
        if cycle_input.stop_loss is None
        else str(cycle_input.stop_loss.stop_loss_price),
        "audit_ref": cycle_input.command.audit_ref,
    }


def _metrics_dict(
    cycle_input: PaperTradingCycleInput,
    *,
    status: PaperRunnerCycleStatus,
    engine_cycle: PaperTradingCycleResult | None = None,
) -> dict[str, Decimal | str | int]:
    return {
        "status": status.value,
        "price": cycle_input.snapshot.candle.close,
        "latency_ms": cycle_input.snapshot.health.latency_ms,
        "equity": engine_cycle.equity
        if engine_cycle is not None
        else cycle_input.command.checklist.account.equity,
        "executed": 1 if status is PaperRunnerCycleStatus.EXECUTED else 0,
        "blocked": 1 if status is PaperRunnerCycleStatus.SKIPPED else 0,
    }


def _summary_text(status: PaperRunnerCycleStatus, reasons: tuple[str, ...]) -> str:
    if status is PaperRunnerCycleStatus.EXECUTED:
        return "Paper cycle executed a simulated paper trade after command and risk gates."
    reason = reasons[0] if reasons else "no executable paper action"
    return f"Paper cycle {status.value}: {reason}."
