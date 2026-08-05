from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from sqlite3 import Connection
from uuid import UUID

import pytest

from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel
from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.repositories import AuditRepository, RiskDecisionRepository
from abtp.risk import (
    RiskEngineConfig,
    RiskEvaluationRequest,
    RiskManagementEngine,
    RiskPolicy,
    RiskPortfolioContext,
    assert_order_intent_has_approved_risk,
)
from abtp.strategies import StrategyEvaluation, StrategySignalPlan

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_risk_engine_approves_valid_signal_and_guards_order_intent() -> None:
    intent = _intent_without_risk()
    decision = RiskManagementEngine(
        config=RiskEngineConfig(persist_decisions=False, audit_decisions=False)
    ).evaluate(_request(proposed_order_id=intent.id))
    approved_intent = OrderIntent(
        id=intent.id,
        pair=intent.pair,
        side=intent.side,
        order_type=intent.order_type,
        quantity=intent.quantity,
        created_at=intent.created_at,
        signal=intent.signal,
        risk_decision=decision,
        status=OrderStatus.RISK_APPROVED,
    )

    assert decision.status is RiskDecisionStatus.APPROVED
    assert decision.allowed
    assert decision.max_position_size == Decimal("25.00")
    assert_order_intent_has_approved_risk(approved_intent)
    with pytest.raises(ValueError, match="cannot bypass risk decision"):
        assert_order_intent_has_approved_risk(intent)


def test_risk_engine_rejects_missing_stop_and_low_confidence() -> None:
    evaluation = _strategy_evaluation(stop=None, confidence=Decimal("0.10"))

    decision = RiskManagementEngine(
        config=RiskEngineConfig(persist_decisions=False, audit_decisions=False)
    ).evaluate(_request(strategy_evaluation=evaluation))

    assert decision.status is RiskDecisionStatus.REJECTED
    assert not decision.allowed
    assert "missing stop-loss suggestion" in decision.reasons
    assert "signal confidence is below threshold" in decision.reasons
    assert decision.max_position_size == Decimal("0")


def test_risk_engine_rejects_stale_or_degraded_quality() -> None:
    stale_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="stale_data",
                severity=DataTrustLevel.REJECTED,
                reason="risk input is stale",
            ),
        ),
        source_ref="risk:stale",
        checked_at=NOW,
    )

    decision = RiskManagementEngine(
        config=RiskEngineConfig(persist_decisions=False, audit_decisions=False)
    ).evaluate(_request(portfolio=_portfolio(data_quality=stale_quality)))

    assert decision.status is RiskDecisionStatus.REJECTED
    assert "risk input data quality is not trusted" in decision.reasons


def test_risk_engine_circuit_breakers_reject() -> None:
    engine = RiskManagementEngine(
        policy=RiskPolicy(kill_switch_active=True),
        config=RiskEngineConfig(persist_decisions=False, audit_decisions=False),
    )
    bad_portfolio = _portfolio(
        current_drawdown_pct=Decimal("0.20"),
        daily_pnl=Decimal("-500"),
        weekly_pnl=Decimal("-900"),
    )

    decision = engine.evaluate(_request(portfolio=bad_portfolio, spread_bps=Decimal("80")))

    assert decision.status is RiskDecisionStatus.REJECTED
    assert decision.kill_switch_active
    assert "kill switch is active" in decision.reasons
    assert "drawdown breach" in decision.reasons
    assert "daily loss breach" in decision.reasons
    assert "weekly loss breach" in decision.reasons
    assert "excessive spread" in decision.reasons


def test_risk_decision_is_persisted_and_audited(migrated_connection: Connection) -> None:
    request = _request()
    risks = RiskDecisionRepository(migrated_connection)
    audits = AuditRepository(migrated_connection)
    engine = RiskManagementEngine(risk_repository=risks, audit_repository=audits)

    decision = engine.evaluate(request)

    stored = risks.list_for_order(str(request.proposed_order_id))
    audit_events = audits.list_by_correlation(str(request.proposed_order_id))
    assert stored == (decision,)
    assert len(audit_events) == 1
    assert audit_events[0].payload["status"] == RiskDecisionStatus.APPROVED.value
    assert audit_events[0].payload["allow"] == "True"


def _request(
    *,
    strategy_evaluation: StrategyEvaluation | None = None,
    portfolio: RiskPortfolioContext | None = None,
    proposed_order_id: UUID | None = None,
    spread_bps: Decimal = Decimal("10"),
) -> RiskEvaluationRequest:
    return RiskEvaluationRequest(
        strategy_evaluation=strategy_evaluation or _strategy_evaluation(),
        portfolio=portfolio or _portfolio(),
        evaluated_at=NOW,
        proposed_order_id=(
            proposed_order_id if proposed_order_id is not None else _intent_without_risk().id
        ),
        entry_price=Decimal("100"),
        spread_bps=spread_bps,
        estimated_slippage_bps=Decimal("5"),
    )


def _portfolio(
    *,
    data_quality: DataQualityStatus | None = None,
    current_drawdown_pct: Decimal = Decimal("0"),
    daily_pnl: Decimal = Decimal("0"),
    weekly_pnl: Decimal = Decimal("0"),
) -> RiskPortfolioContext:
    return RiskPortfolioContext(
        total_equity=Decimal("10000"),
        available_cash=Decimal("8000"),
        current_exposure=Decimal("0"),
        correlated_exposure=Decimal("0"),
        current_drawdown_pct=current_drawdown_pct,
        daily_pnl=daily_pnl,
        weekly_pnl=weekly_pnl,
        data_quality=data_quality or _trusted_quality(),
    )


def _strategy_evaluation(
    *,
    stop: Decimal | None = Decimal("98"),
    confidence: Decimal = Decimal("0.50"),
) -> StrategyEvaluation:
    signal = Signal(
        source="fixture-strategy",
        pair=_pair(),
        generated_at=NOW,
        direction=SignalDirection.BUY,
        confidence=confidence,
        inputs_ref="fixture:features:1",
        rationale="fixture buy signal",
    )
    return StrategyEvaluation(
        strategy_name="fixture-strategy",
        strategy_version="stage-022.fixture",
        enabled=True,
        signal=signal,
        plan=StrategySignalPlan(
            entry_reason="fixture entry",
            timeframe="1h",
            feature_snapshot_ref="fixture:features:1",
            stop_suggestion=stop,
            target_suggestion=Decimal("104") if stop is not None else None,
        ),
        reasons=("fixture signal passed",),
        generated_at=NOW,
    )


def _intent_without_risk() -> OrderIntent:
    return OrderIntent(
        pair=_pair(),
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        created_at=NOW,
        signal=_strategy_evaluation().signal,
    )


def _pair() -> AssetPair:
    return AssetPair(Asset("BTC"), Asset("USDT"))


def _trusted_quality() -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref="risk:trusted",
        checked_at=NOW,
    )
