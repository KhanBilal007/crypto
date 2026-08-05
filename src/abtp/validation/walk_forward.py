"""Walk-forward validation orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from abtp.domain.models import JsonValue
from abtp.validation.robustness import (
    RobustnessPolicy,
    RobustnessScore,
    WindowMetricResult,
    score_robustness,
)
from abtp.validation.splits import ValidationWindow, assert_no_leakage


@dataclass(frozen=True, slots=True)
class WalkForwardValidationRequest:
    """Input request for one advisory walk-forward validation review."""

    strategy_name: str
    window_results: tuple[WindowMetricResult, ...]
    required_regime: str | None = None
    generated_at: datetime | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy_name.strip():
            raise ValueError("strategy_name is required")
        if not self.window_results:
            raise ValueError("window_results are required")
        if any(result.strategy_name != self.strategy_name for result in self.window_results):
            raise ValueError("window_results must match request strategy_name")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def windows(self) -> tuple[ValidationWindow, ...]:
        return tuple(result.window for result in self.window_results)


@dataclass(frozen=True, slots=True)
class WalkForwardValidationReport:
    """Auditable walk-forward validation report."""

    strategy_name: str
    generated_at: datetime
    windows: tuple[ValidationWindow, ...]
    window_results: tuple[WindowMetricResult, ...]
    robustness: RobustnessScore
    accepted_for_promotion: bool
    rejected_reasons: tuple[str, ...]
    source_refs: Mapping[str, str]
    limitations: tuple[str, ...] = (
        "Walk-forward validation is advisory evidence, not a trading signal.",
        "Rejected strategies must not be promoted to paper or live operation.",
        "All future signals must still pass the Strategy Engine and Risk Management Engine.",
        "No profit is guaranteed by validation results.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "strategy_name": self.strategy_name,
            "generated_at": self.generated_at.isoformat(),
            "windows": [window.as_dict() for window in self.windows],
            "window_results": [result.as_dict() for result in self.window_results],
            "robustness": self.robustness.as_dict(),
            "accepted_for_promotion": self.accepted_for_promotion,
            "rejected_reasons": list(self.rejected_reasons),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "strategy_name": self.strategy_name,
            "window_count": str(len(self.windows)),
            "accepted_for_promotion": str(self.accepted_for_promotion),
            "robustness_score": str(self.robustness.total_score),
            "pass_ratio": str(self.robustness.pass_ratio),
            "average_oos_return": str(self.robustness.average_out_of_sample_return),
            "worst_oos_drawdown": str(self.robustness.worst_out_of_sample_drawdown),
            "rejected_reasons": "|".join(self.rejected_reasons),
        }


class WalkForwardValidationEngine:
    """Validate strategy evidence without signal, risk, order, or exchange authority."""

    def __init__(self, *, policy: RobustnessPolicy | None = None) -> None:
        self._policy = policy or RobustnessPolicy()

    @property
    def policy(self) -> RobustnessPolicy:
        return self._policy

    def validate(self, request: WalkForwardValidationRequest) -> WalkForwardValidationReport:
        """Build an advisory walk-forward validation report."""

        generated_at = request.generated_at or datetime.now(UTC)
        assert_no_leakage(request.windows)
        robustness = score_robustness(
            request.window_results,
            policy=self._policy,
            required_regime=request.required_regime,
            generated_at=generated_at,
        )
        return WalkForwardValidationReport(
            strategy_name=request.strategy_name,
            generated_at=generated_at,
            windows=request.windows,
            window_results=request.window_results,
            robustness=robustness,
            accepted_for_promotion=robustness.accepted_for_promotion,
            rejected_reasons=robustness.rejected_reasons,
            source_refs=request.source_refs,
        )

    def create_signal(self, *_args: object, **_kwargs: object) -> None:
        """Reject direct signal creation; validation has no strategy authority."""

        raise ValueError("walk-forward validation cannot create strategy signals")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject direct order submission; validation has no execution authority."""

        raise ValueError("walk-forward validation cannot submit orders")
