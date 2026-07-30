from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from abtp.audit import DecisionAuditRecorder, build_audit_event
from abtp.learning import LearningRecommendation, TradeLearningRecord, build_monthly_learning_report
from abtp.repositories import AuditRepository

NOW = datetime(2026, 1, 15, tzinfo=UTC)
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000035")


def test_monthly_learning_report_filters_records_and_builds_audit_payload(
    migrated_connection,
) -> None:
    report = build_monthly_learning_report(
        (
            _record("jan-win", NOW, pnl=Decimal("10"), confidence=Decimal("0.70")),
            _record(
                "feb-loss",
                datetime(2026, 2, 1, tzinfo=UTC),
                pnl=Decimal("-2"),
                confidence=Decimal("0.60"),
            ),
        ),
        year=2026,
        month=1,
        generated_at=NOW,
        source_refs={"paper_cycles": "fixture:paper"},
    )

    assert report.period == "2026-01"
    assert report.analysis.outcomes.record_count == 1
    assert report.audit_payload()["recommendation_count"] == 1
    assert "advisory only" in report.summary

    recorder = DecisionAuditRecorder(AuditRepository(migrated_connection))
    event_id = recorder.append(
        build_audit_event(
            event_type="learning_report",
            occurred_at=NOW,
            payload={key: str(value) for key, value in report.audit_payload().items()},
            correlation_id=CORRELATION_ID,
        )
    )
    trail = recorder.reconstruct(str(CORRELATION_ID))

    assert event_id
    assert trail.events[0].payload["report_id"] == "learning-report-2026-01"
    assert trail.events[0].payload["quality"] == "trusted"


def test_learning_recommendations_cannot_be_auto_applied() -> None:
    try:
        LearningRecommendation(
            recommendation_type="confidence_calibration",
            target="signal_confidence:0.75-1.00",
            confidence_adjustment=Decimal("-0.05"),
            rationale="fixture unsafe recommendation",
            evidence_refs=("trade:1",),
            allowed_to_auto_apply=True,
        )
    except ValueError as exc:
        assert "cannot auto-apply" in str(exc)
    else:
        raise AssertionError("auto-apply recommendation should be rejected")


def _record(
    trade_id: str,
    closed_at: datetime,
    *,
    pnl: Decimal,
    confidence: Decimal,
) -> TradeLearningRecord:
    return TradeLearningRecord(
        trade_id=trade_id,
        strategy_name="fixture-strategy",
        regime_label="trend_up",
        opened_at=closed_at - timedelta(minutes=30),
        closed_at=closed_at,
        realized_pnl=pnl,
        return_pct=pnl / Decimal("100"),
        fees_paid=Decimal("0.01"),
        signal_confidence=confidence,
        risk_decision_status="approved",
        source_refs={"trade": f"fixture:{trade_id}"},
    )
