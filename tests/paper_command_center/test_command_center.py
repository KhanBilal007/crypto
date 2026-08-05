from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.api import (
    PaperCommandCenterResponse,
    PaperPortfolioStatus,
    PaperStatusResponse,
    build_paper_command_center_response,
)
from abtp.dashboard import render_paper_command_center
from abtp.data import DataQualityIssue, DataQualityStatus, DataTrustLevel, OrderBookMetrics
from abtp.data.heartbeat import StreamHealth
from abtp.exchanges.health import ExchangeHealthInput, score_exchange_health
from abtp.exchanges.reliability import ReliabilityInput, score_reliability
from abtp.intelligence import (
    DecisionEvidence,
    DecisionEvidenceType,
    DecisionHubInput,
    DecisionStance,
    build_institutional_decision,
)
from abtp.paper import (
    PaperCommandCenterInput,
    PaperCommandLabel,
    PaperTradeChecklistInput,
    build_paper_command_recommendation,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
MISSING = object()


def test_command_center_returns_buy_review_when_all_paper_checks_pass() -> None:
    recommendation = build_paper_command_recommendation(_command_input())

    assert recommendation.label is PaperCommandLabel.BUY_REVIEW
    assert recommendation.paper_trade_ready
    assert recommendation.max_paper_position_size == Decimal("0.05")
    assert recommendation.stop_loss_required
    assert recommendation.audit_payload()["label"] == "BUY REVIEW"


def test_hold_decision_maps_to_hold_without_paper_trade_ready() -> None:
    recommendation = build_paper_command_recommendation(
        _command_input(decision=_decision(support=Decimal("0.50")))
    )

    assert recommendation.label is PaperCommandLabel.HOLD
    assert not recommendation.paper_trade_ready
    assert any("hold_review" in reason for reason in recommendation.blocked_reasons)


def test_missing_stop_loss_or_exchange_health_fails_closed_to_avoid() -> None:
    recommendation = build_paper_command_recommendation(
        _command_input(exchange_health=MISSING, stop_loss_price=None)
    )

    assert recommendation.label is PaperCommandLabel.AVOID
    assert not recommendation.paper_trade_ready
    assert "exchange health evidence is missing" in recommendation.blocked_reasons
    assert "stop-loss metadata is required" in recommendation.blocked_reasons


def test_protect_capital_overrides_buy_review() -> None:
    recommendation = build_paper_command_recommendation(
        _command_input(status=_paper_status(kill_switch_active=True))
    )

    assert recommendation.label is PaperCommandLabel.PROTECT_CAPITAL
    assert not recommendation.paper_trade_ready
    assert "paper kill switch is active" in recommendation.blocked_reasons


def test_stale_or_rejected_data_blocks_paper_review() -> None:
    rejected_quality = DataQualityStatus(
        trust_level=DataTrustLevel.REJECTED,
        issues=(
            DataQualityIssue(
                flag="rejected_stage071_fixture",
                severity=DataTrustLevel.REJECTED,
                reason="fixture data is rejected",
            ),
        ),
        source_ref="fixture:rejected",
        checked_at=NOW,
    )
    recommendation = build_paper_command_recommendation(
        _command_input(
            status=_paper_status(data_health="stale"),
            data_quality=rejected_quality,
        )
    )

    assert recommendation.label is PaperCommandLabel.AVOID
    assert recommendation.quality.is_rejected
    assert "paper data health is stale" in recommendation.blocked_reasons
    assert "data quality is not trusted" in recommendation.blocked_reasons


def test_confidence_threshold_blocks_buy_review() -> None:
    recommendation = build_paper_command_recommendation(
        _command_input(decision=_decision(confidence=Decimal("0.50")))
    )

    assert recommendation.label is PaperCommandLabel.AVOID
    assert "decision confidence is below paper checklist threshold" in (
        recommendation.blocked_reasons
    )


def test_dashboard_text_and_api_response_are_deterministic() -> None:
    recommendation = build_paper_command_recommendation(_command_input())
    rendered = render_paper_command_center(recommendation)
    response = build_paper_command_center_response(recommendation)

    assert "Action: BUY REVIEW" in rendered
    assert "Ready for paper review: True" in rendered
    assert response.as_dict()["recommendation"]["label"] == "BUY REVIEW"
    assert isinstance(response, PaperCommandCenterResponse)


def test_command_center_has_no_signal_risk_order_or_live_authority() -> None:
    recommendation = build_paper_command_recommendation(_command_input())
    response = build_paper_command_center_response(recommendation)

    with pytest.raises(ValueError, match="cannot create strategy signals"):
        recommendation.create_signal(object())
    with pytest.raises(ValueError, match="cannot approve risk"):
        recommendation.approve_risk(object())
    with pytest.raises(ValueError, match="cannot create order intents"):
        recommendation.create_order_intent(object())
    with pytest.raises(ValueError, match="cannot submit orders"):
        recommendation.submit_order(object())
    with pytest.raises(ValueError, match="cannot enable live trading"):
        recommendation.enable_live_trading()
    with pytest.raises(ValueError, match="cannot enable live trading"):
        response.enable_live_trading()


def test_public_imports_are_available() -> None:
    import abtp.api as api
    import abtp.dashboard as dashboard
    import abtp.paper as paper

    assert paper.build_paper_command_recommendation is build_paper_command_recommendation
    assert dashboard.render_paper_command_center is render_paper_command_center
    assert api.build_paper_command_center_response is build_paper_command_center_response


def _command_input(
    *,
    decision=None,
    status: PaperStatusResponse | None = None,
    exchange_health=...,
    data_quality: DataQualityStatus | None = None,
    stop_loss_price: Decimal | None = Decimal("95000"),
) -> PaperCommandCenterInput:
    return PaperCommandCenterInput(
        checklist_input=PaperTradeChecklistInput(
            decision=decision or _decision(),
            paper_status=status or _paper_status(),
            data_quality=data_quality or _trusted_quality("fixture:data"),
            exchange_health=(
                _exchange_health()
                if exchange_health is ...
                else None
                if exchange_health is MISSING
                else exchange_health
            ),
            generated_at=NOW,
            max_paper_position_size=Decimal("0.05"),
            stop_loss_required=True,
            stop_loss_price=stop_loss_price,
            daily_loss_pct=Decimal("0"),
            weekly_loss_pct=Decimal("0"),
            source_refs={"checklist": "fixture:stage071"},
        ),
        audit_ref="audit:stage071",
        generated_at=NOW,
        source_refs={"command": "fixture:stage071"},
    )


def _paper_status(
    *,
    data_health: str = "healthy",
    kill_switch_active: bool = False,
) -> PaperStatusResponse:
    return PaperStatusResponse(
        current_btc_price=Decimal("100000"),
        active_regime="trend_up",
        latest_signal="buy",
        latest_risk_decision="approved",
        blocked_reason="none",
        data_health=data_health,
        portfolio=PaperPortfolioStatus(
            cash=Decimal("10000"),
            base_quantity=Decimal("0"),
            average_entry_price=Decimal("0"),
            realized_pnl=Decimal("0"),
            fees_paid=Decimal("0"),
            equity=Decimal("10000"),
            drawdown_pct=Decimal("0"),
        ),
        parameter_health=(),
        paused=False,
        kill_switch_active=kill_switch_active,
        cycles_count=3,
        trades_count=0,
        updated_at=NOW,
    )


def _decision(
    *,
    confidence: Decimal = Decimal("0.74"),
    support: Decimal = Decimal("0.72"),
    risk: Decimal = Decimal("0.20"),
):
    return build_institutional_decision(
        DecisionHubInput(
            symbol="BTC",
            generated_at=NOW,
            evidence=tuple(
                _evidence(
                    evidence_type,
                    confidence=confidence,
                    support=support,
                    risk=risk,
                )
                for evidence_type in (
                    DecisionEvidenceType.MULTI_TIMEFRAME,
                    DecisionEvidenceType.MARKET_CYCLE,
                    DecisionEvidenceType.ONCHAIN,
                    DecisionEvidenceType.FUNDAMENTAL,
                    DecisionEvidenceType.MACRO_NARRATIVE,
                    DecisionEvidenceType.AI_COMMITTEE,
                    DecisionEvidenceType.PORTFOLIO_STATUS,
                    DecisionEvidenceType.RISK_ENGINE,
                    DecisionEvidenceType.OPPORTUNITY_SCANNER,
                    DecisionEvidenceType.CONFIDENCE_ENGINE,
                )
            ),
        )
    )


def _evidence(
    evidence_type: DecisionEvidenceType,
    *,
    confidence: Decimal,
    support: Decimal,
    risk: Decimal,
) -> DecisionEvidence:
    return DecisionEvidence(
        evidence_type=evidence_type,
        source_ref=f"fixture:{evidence_type.value}",
        summary=f"{evidence_type.value} supports paper review",
        confidence=confidence,
        support_score=support,
        risk_score=risk,
        quality=_trusted_quality(evidence_type.value),
        stance=DecisionStance.SUPPORTIVE,
        suggested_holding_period="2-6 weeks"
        if evidence_type is DecisionEvidenceType.MARKET_CYCLE
        else None,
    )


def _exchange_health():
    return score_exchange_health(
        ExchangeHealthInput(
            exchange_name="sandbox",
            checked_at=NOW,
            reliability=score_reliability(
                ReliabilityInput(
                    exchange_name="sandbox",
                    observed_at=NOW,
                    request_count=100,
                    error_count=0,
                    latency_ms_samples=(80, 90, 100),
                )
            ),
            stream_health=StreamHealth(
                is_connected=True,
                is_stale=False,
                is_degraded=False,
                disconnect_count=0,
                last_message_at=NOW,
                latency_ms=100,
                stale_after=timedelta(seconds=30),
            ),
            order_book_metrics=OrderBookMetrics(
                best_bid=Decimal("9995"),
                best_ask=Decimal("10005"),
                spread=Decimal("10"),
                bid_depth=Decimal("2.5"),
                ask_depth=Decimal("2.0"),
                imbalance=Decimal("0.11"),
            ),
        )
    )


def _trusted_quality(source_ref: str) -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=source_ref,
        checked_at=NOW,
    )
