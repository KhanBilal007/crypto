"""Exchange reconciliation orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, normalize_timestamp
from abtp.domain.models import JsonValue
from abtp.reconciliation.checks import (
    MismatchSeverity,
    ReconciliationMismatch,
    ReconciliationSnapshot,
    ReconciliationTolerance,
    compare_snapshots,
)
from abtp.reconciliation.recovery import RecoveryPlan, build_recovery_plan


@dataclass(frozen=True, slots=True)
class ReconciliationRequest:
    """Inputs for one deterministic reconciliation run."""

    database_snapshot: ReconciliationSnapshot
    exchange_snapshot: ReconciliationSnapshot
    checked_at: datetime | None = None
    tolerance: ReconciliationTolerance | None = None
    source_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", dict(self.source_refs))


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Auditable reconciliation result and recovery recommendation."""

    generated_at: datetime
    database_snapshot: ReconciliationSnapshot
    exchange_snapshot: ReconciliationSnapshot
    mismatches: tuple[ReconciliationMismatch, ...]
    recovery_plan: RecoveryPlan
    quality: DataQualityStatus
    source_refs: Mapping[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = (
        "Reconciliation output is advisory safety evidence only.",
        "The engine does not place, cancel, modify, or approve orders.",
        "Recovery recommendations require later operator or controlled workflow action.",
        "No credentials or raw secret values are stored in reconciliation records.",
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        if not self.limitations:
            raise ValueError("reconciliation report limitations are required")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def matched(self) -> bool:
        return not self.mismatches and self.quality.is_trusted

    @property
    def blocks_continuation(self) -> bool:
        return self.recovery_plan.block_new_entries or any(
            mismatch.blocks_continuation for mismatch in self.mismatches
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "database_snapshot": self.database_snapshot.as_dict(),
            "exchange_snapshot": self.exchange_snapshot.as_dict(),
            "mismatches": [mismatch.as_dict() for mismatch in self.mismatches],
            "recovery_plan": self.recovery_plan.as_dict(),
            "matched": self.matched,
            "blocks_continuation": self.blocks_continuation,
            "quality": self.quality.trust_level.value,
            "quality_flags": list(self.quality.flags),
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, JsonValue]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "database_source": self.database_snapshot.source_name,
            "exchange_source": self.exchange_snapshot.source_name,
            "mismatch_count": str(len(self.mismatches)),
            "mismatch_entities": "|".join(mismatch.entity.value for mismatch in self.mismatches),
            "recovery_actions": "|".join(
                item.action.value for item in self.recovery_plan.recommendations
            ),
            "matched": str(self.matched),
            "blocks_continuation": str(self.blocks_continuation),
            "quality": self.quality.trust_level.value,
            "quality_flags": "|".join(self.quality.flags),
        }

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject execution authority."""

        raise ValueError("reconciliation report cannot submit orders")

    def cancel_order(self, *_args: object, **_kwargs: object) -> None:
        """Reject cancellation authority."""

        raise ValueError("reconciliation report cannot cancel orders")

    def approve_risk(self, *_args: object, **_kwargs: object) -> None:
        """Reject risk-approval authority."""

        raise ValueError("reconciliation report cannot approve risk")


class ExchangeReconciliationEngine:
    """Compare stored state with adapter-provided state without exchange actions."""

    def __init__(self, tolerance: ReconciliationTolerance | None = None) -> None:
        self._tolerance = tolerance or ReconciliationTolerance()

    @property
    def tolerance(self) -> ReconciliationTolerance:
        return self._tolerance

    def reconcile(self, request: ReconciliationRequest) -> ReconciliationReport:
        checked_at = normalize_timestamp(request.checked_at or datetime.now(UTC))
        tolerance = request.tolerance or self.tolerance
        mismatches = compare_snapshots(
            request.database_snapshot,
            request.exchange_snapshot,
            tolerance=tolerance,
        )
        refs = dict(request.database_snapshot.source_refs)
        refs.update(request.exchange_snapshot.source_refs)
        refs.update(request.source_refs)
        recovery_plan = build_recovery_plan(
            mismatches=mismatches,
            database_snapshot=request.database_snapshot,
            exchange_snapshot=request.exchange_snapshot,
            generated_at=checked_at,
            source_refs=refs,
        )
        quality = _report_quality(mismatches, recovery_plan, checked_at)
        return ReconciliationReport(
            generated_at=checked_at,
            database_snapshot=request.database_snapshot,
            exchange_snapshot=request.exchange_snapshot,
            mismatches=mismatches,
            recovery_plan=recovery_plan,
            quality=quality,
            source_refs=refs,
        )


def _report_quality(
    mismatches: tuple[ReconciliationMismatch, ...],
    recovery_plan: RecoveryPlan,
    checked_at: datetime,
) -> DataQualityStatus:
    issues: list[DataQualityIssue] = [*recovery_plan.quality.issues]
    for mismatch in mismatches:
        if mismatch.severity is MismatchSeverity.INFO:
            continue
        issues.append(
            DataQualityIssue(
                flag=f"reconciliation_report_{mismatch.entity.value}",
                severity=(
                    DataTrustLevel.REJECTED
                    if mismatch.severity is MismatchSeverity.BLOCKER
                    else DataTrustLevel.DEGRADED
                ),
                reason=mismatch.reason,
            )
        )
    if any(issue.severity is DataTrustLevel.REJECTED for issue in issues):
        trust_level = DataTrustLevel.REJECTED
    elif issues:
        trust_level = DataTrustLevel.DEGRADED
    else:
        trust_level = DataTrustLevel.TRUSTED
    return DataQualityStatus(
        trust_level=trust_level,
        issues=tuple(issues),
        source_ref="reconciliation:report",
        checked_at=checked_at,
    )
