"""Self-learning reports and audit payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from abtp.data import normalize_timestamp
from abtp.learning.analyzer import LearningAnalysis, TradeLearningRecord, build_learning_analysis
from abtp.learning.calibration import ConfidenceCalibrationReport, calibrate_confidence


@dataclass(frozen=True, slots=True)
class LearningReport:
    """Monthly advisory learning report."""

    report_id: str
    generated_at: datetime
    period: str
    analysis: LearningAnalysis
    calibration: ConfidenceCalibrationReport
    summary: str
    source_refs: Mapping[str, str]
    limitations: tuple[str, ...] = (
        "This report is advisory and cannot modify strategies or risk rules automatically.",
        "Recommendations require paper/backtest validation before adoption.",
        "No profit is guaranteed by learning analysis.",
    )

    def __post_init__(self) -> None:
        if not self.report_id.strip():
            raise ValueError("report_id is required")
        if not self.period.strip():
            raise ValueError("period is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        object.__setattr__(self, "generated_at", normalize_timestamp(self.generated_at))
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    def as_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "period": self.period,
            "analysis": self.analysis.as_dict(),
            "calibration": self.calibration.as_dict(),
            "summary": self.summary,
            "source_refs": dict(self.source_refs),
            "limitations": list(self.limitations),
        }

    def audit_payload(self) -> dict[str, object]:
        """Return a compact append-only audit payload for report generation."""

        return {
            "report_id": self.report_id,
            "period": self.period,
            "record_count": self.analysis.outcomes.record_count,
            "win_rate": str(self.analysis.outcomes.win_rate),
            "recommendation_count": len(self.analysis.recommendations),
            "quality": self.analysis.quality.trust_level.value,
            "summary": self.summary,
        }


def build_monthly_learning_report(
    records: Sequence[TradeLearningRecord],
    *,
    year: int,
    month: int,
    generated_at: datetime | None = None,
    source_refs: Mapping[str, str] | None = None,
) -> LearningReport:
    """Build a monthly advisory learning report."""

    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    checked_at = generated_at or datetime.now(UTC)
    period = f"{year:04d}-{month:02d}"
    monthly_records = tuple(
        record
        for record in records
        if record.closed_at.year == year and record.closed_at.month == month
    )
    refs = dict(source_refs or {})
    refs.setdefault("record_filter", f"closed_at:{period}")
    analysis = build_learning_analysis(
        monthly_records,
        generated_at=checked_at,
        source_refs=refs,
    )
    calibration = calibrate_confidence(monthly_records, generated_at=checked_at)
    return LearningReport(
        report_id=f"learning-report-{period}",
        generated_at=checked_at,
        period=period,
        analysis=analysis,
        calibration=calibration,
        summary=_summary(analysis),
        source_refs=refs,
    )


def _summary(analysis: LearningAnalysis) -> str:
    if analysis.outcomes.record_count == 0:
        return "No usable completed trades were available for this learning period."
    return (
        "Self-learning report reviewed "
        f"{analysis.outcomes.record_count} completed trades with "
        f"win_rate={analysis.outcomes.win_rate}; recommendations are advisory only."
    )
