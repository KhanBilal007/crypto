from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.exchanges.health import ExchangeHealthStatus
from abtp.exchanges.permission_gates import (
    PermissionGateInput,
    TradingPermission,
    recommend_permission_gate,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_permission_gate_allows_read_only_monitoring_for_healthy_evidence() -> None:
    gate = recommend_permission_gate(_gate_input(score=Decimal("0.95"), status="healthy"))

    assert gate.permission is TradingPermission.READ_ONLY
    assert not gate.block_new_entries
    assert not gate.pause_trading
    assert gate.quality.is_trusted


def test_permission_gate_uses_paper_only_for_degraded_quality() -> None:
    gate = recommend_permission_gate(
        _gate_input(
            score=Decimal("0.90"),
            status="degraded",
            quality=DataQualityStatus(
                trust_level=DataTrustLevel.DEGRADED,
                issues=(
                    DataQualityIssue(
                        flag="fixture_degraded",
                        severity=DataTrustLevel.DEGRADED,
                        reason="fixture degraded",
                    ),
                ),
                source_ref="fixture:quality",
                checked_at=NOW,
            ),
        )
    )

    assert gate.permission is TradingPermission.PAPER_ONLY
    assert gate.block_new_entries
    assert gate.quality.is_degraded


def test_permission_gate_pauses_for_unavailable_or_rejected_health() -> None:
    gate = recommend_permission_gate(
        _gate_input(
            score=Decimal("0.75"),
            status=ExchangeHealthStatus.UNAVAILABLE.value,
            quality=DataQualityStatus(
                trust_level=DataTrustLevel.REJECTED,
                issues=(
                    DataQualityIssue(
                        flag="fixture_rejected",
                        severity=DataTrustLevel.REJECTED,
                        reason="fixture rejected",
                    ),
                ),
                source_ref="fixture:quality",
                checked_at=NOW,
            ),
            rejection_reasons=("exchange outage reported",),
        )
    )

    assert gate.permission is TradingPermission.PAUSE_TRADING
    assert gate.pause_trading
    assert gate.manual_review_required
    assert "exchange outage reported" in gate.reasons


def test_permission_gate_has_no_execution_or_risk_authority() -> None:
    gate = recommend_permission_gate(_gate_input(score=Decimal("0.95"), status="healthy"))

    with pytest.raises(ValueError, match="cannot submit orders"):
        gate.submit_order()
    with pytest.raises(ValueError, match="cannot create order intents"):
        gate.create_order_intent()
    with pytest.raises(ValueError, match="cannot approve risk"):
        gate.approve_risk()


def test_public_imports_are_available_from_stage_048_modules() -> None:
    from abtp.exchanges.health import ExchangeHealthInput, ExchangeHealthScore
    from abtp.exchanges.permission_gates import PermissionGateRecommendation
    from abtp.exchanges.reliability import ReliabilityScore

    assert ExchangeHealthInput is not None
    assert ExchangeHealthScore is not None
    assert PermissionGateRecommendation is not None
    assert ReliabilityScore is not None


def _gate_input(
    *,
    score: Decimal,
    status: str,
    quality: DataQualityStatus | None = None,
    rejection_reasons: tuple[str, ...] = (),
) -> PermissionGateInput:
    return PermissionGateInput(
        exchange_name="sandbox",
        checked_at=NOW,
        health_score=score,
        health_status=status,
        quality=quality
        or DataQualityStatus(
            trust_level=DataTrustLevel.TRUSTED,
            issues=(),
            source_ref="fixture:trusted",
            checked_at=NOW,
        ),
        rejection_reasons=rejection_reasons,
        health_reasons=("fixture health evidence",),
        source_refs={"health": "fixture:health"},
    )
