"""Paper runner session summaries for Stage 072."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from abtp.data import normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.paper.cycle import PaperRunnerCycleStatus, PaperTradingRunnerCycleResult


@dataclass(frozen=True, slots=True)
class PaperTradingSessionSummary:
    """Deterministic aggregate summary for one paper runner session."""

    session_id: str
    started_at: datetime
    ended_at: datetime
    cycles: tuple[PaperTradingRunnerCycleResult, ...]
    executed_count: int
    blocked_count: int
    risk_rejected_count: int
    no_signal_count: int
    starting_equity: Decimal
    ending_equity: Decimal
    realized_pnl: Decimal
    total_fees: Decimal
    status: str
    blocked_reason_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id is required")
        if self.ended_at < self.started_at:
            raise ValueError("session ended_at cannot be before started_at")
        for name, value in (
            ("executed_count", self.executed_count),
            ("blocked_count", self.blocked_count),
            ("risk_rejected_count", self.risk_rejected_count),
            ("no_signal_count", self.no_signal_count),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        object.__setattr__(self, "started_at", normalize_timestamp(self.started_at))
        object.__setattr__(self, "ended_at", normalize_timestamp(self.ended_at))
        object.__setattr__(self, "blocked_reason_counts", dict(self.blocked_reason_counts))

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    def render_text(self) -> str:
        """Return a deterministic plain-language session summary."""

        return "\n".join(
            (
                f"Paper session {self.session_id}: {self.status}",
                f"Cycles: {self.cycle_count}",
                f"Executed paper trades: {self.executed_count}",
                f"Blocked cycles: {self.blocked_count}",
                f"Risk rejected cycles: {self.risk_rejected_count}",
                f"No-signal cycles: {self.no_signal_count}",
                f"Starting equity: {self.starting_equity}",
                f"Ending equity: {self.ending_equity}",
                f"Realized P/L: {self.realized_pnl}",
                f"Fees: {self.total_fees}",
                f"Blocked reasons: {_reason_counts(self.blocked_reason_counts)}",
                "Live trading remains locked.",
            )
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "cycle_count": self.cycle_count,
            "executed_count": self.executed_count,
            "blocked_count": self.blocked_count,
            "risk_rejected_count": self.risk_rejected_count,
            "no_signal_count": self.no_signal_count,
            "starting_equity": str(self.starting_equity),
            "ending_equity": str(self.ending_equity),
            "realized_pnl": str(self.realized_pnl),
            "total_fees": str(self.total_fees),
            "status": self.status,
            "blocked_reason_counts": dict(self.blocked_reason_counts),
            "cycles": [cycle.as_dict() for cycle in self.cycles],
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "session_id": self.session_id,
            "cycle_count": str(self.cycle_count),
            "executed_count": str(self.executed_count),
            "blocked_count": str(self.blocked_count),
            "risk_rejected_count": str(self.risk_rejected_count),
            "no_signal_count": str(self.no_signal_count),
            "starting_equity": str(self.starting_equity),
            "ending_equity": str(self.ending_equity),
            "status": self.status,
            "blocked_reasons": "|".join(self.blocked_reason_counts),
        }


def summarize_paper_session(
    *,
    session_id: str,
    cycles: tuple[PaperTradingRunnerCycleResult, ...],
    started_at: datetime,
    ended_at: datetime,
    starting_equity: Decimal,
    ending_equity: Decimal,
    realized_pnl: Decimal,
    total_fees: Decimal,
) -> PaperTradingSessionSummary:
    """Aggregate runner cycles into a deterministic session summary."""

    executed = sum(1 for cycle in cycles if cycle.status is PaperRunnerCycleStatus.EXECUTED)
    blocked = sum(1 for cycle in cycles if cycle.status is PaperRunnerCycleStatus.SKIPPED)
    risk_rejected = sum(
        1 for cycle in cycles if cycle.status is PaperRunnerCycleStatus.RISK_REJECTED
    )
    no_signal = sum(1 for cycle in cycles if cycle.status is PaperRunnerCycleStatus.NO_SIGNAL)
    reason_counts: dict[str, int] = {}
    for cycle in cycles:
        for reason in cycle.blocked_reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    status = "completed"
    if not cycles:
        status = "empty"
    elif blocked == len(cycles):
        status = "all_cycles_blocked"
    elif risk_rejected:
        status = "completed_with_risk_rejections"
    return PaperTradingSessionSummary(
        session_id=session_id,
        started_at=started_at,
        ended_at=ended_at,
        cycles=cycles,
        executed_count=executed,
        blocked_count=blocked,
        risk_rejected_count=risk_rejected,
        no_signal_count=no_signal,
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        realized_pnl=realized_pnl,
        total_fees=total_fees,
        status=status,
        blocked_reason_counts=reason_counts,
    )


def _reason_counts(reason_counts: Mapping[str, int]) -> str:
    if not reason_counts:
        return "none"
    return "; ".join(f"{reason}={count}" for reason, count in sorted(reason_counts.items()))
