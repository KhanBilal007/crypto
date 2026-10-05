from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from abtp.domain import OrderSide
from abtp.paper import (
    PaperEvaluationInput,
    PaperEvaluationPolicy,
    PaperGateRecommendation,
    PaperTrade,
    PaperTradingSessionSummary,
    build_paper_evaluation_metrics,
    build_paper_evaluation_report,
    evaluate_paper_promotion_gate,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _Cycle:
    metrics: dict[str, Decimal]
    audit_events: tuple[dict[str, str], ...] = ({"audit": "ok"},)


def test_insufficient_sample_remains_paper() -> None:
    result = evaluate_paper_promotion_gate(
        _evaluation_input(days=5, trades=_profitable_trades(pair_count=1))
    )

    assert result.recommendation is PaperGateRecommendation.REMAIN_PAPER
    assert "minimum paper-trading days not met" in result.rejection_reasons[0]
    assert result.live_trading_locked


def test_drawdown_breach_makes_more_conservative() -> None:
    result = evaluate_paper_promotion_gate(
        _evaluation_input(
            sessions=(
                _session(
                    "drawdown",
                    0,
                    30,
                    starting=Decimal("10000"),
                    ending=Decimal("10100"),
                    equities=(Decimal("10000"), Decimal("8500"), Decimal("10100")),
                ),
            )
        )
    )

    assert result.recommendation is PaperGateRecommendation.MAKE_MORE_CONSERVATIVE
    assert any("drawdown breach" in reason for reason in result.rejection_reasons)


def test_loss_limits_stop_loss_capital_and_governance_pause_for_review() -> None:
    result = evaluate_paper_promotion_gate(
        _evaluation_input(
            daily_loss_events=1,
            stop_loss_violations=1,
            capital_preservation_events=1,
            governance_violations=1,
        )
    )

    assert result.recommendation is PaperGateRecommendation.PAUSE_FOR_REVIEW
    assert any("stop-loss violation" in reason for reason in result.rejection_reasons)
    assert any("capital-preservation event" in reason for reason in result.rejection_reasons)
    assert any("governance violation" in reason for reason in result.rejection_reasons)


def test_positive_paper_result_is_only_future_tiny_live_proposal_eligible() -> None:
    result = evaluate_paper_promotion_gate(_evaluation_input())

    assert result.recommendation is PaperGateRecommendation.ELIGIBLE_FOR_FUTURE_TINY_LIVE_PROPOSAL
    assert result.eligible_for_future_tiny_live_proposal
    assert result.live_trading_locked
    assert result.rejection_reasons == ()
    with pytest.raises(ValueError, match="cannot enable live trading"):
        result.enable_live_trading()


def test_high_fee_blocked_cycle_and_confidence_calibration_reject_future_live_review() -> None:
    result = evaluate_paper_promotion_gate(
        _evaluation_input(
            sessions=(
                _session(
                    "blocked",
                    0,
                    30,
                    starting=Decimal("10000"),
                    ending=Decimal("10100"),
                    blocked=8,
                    executed=2,
                    cycle_count=10,
                ),
            ),
            trades=_profitable_trades(pair_count=3, fee=Decimal("50")),
            confidence_calibration_error=Decimal("0.35"),
        )
    )

    assert result.recommendation is PaperGateRecommendation.MAKE_MORE_CONSERVATIVE
    assert any("excessive fee impact" in reason for reason in result.rejection_reasons)
    assert any("blocked-cycle rate too high" in reason for reason in result.rejection_reasons)
    assert any(
        "confidence calibration error too high" in reason for reason in result.rejection_reasons
    )


def test_missing_audit_evidence_prevents_future_live_consideration() -> None:
    result = evaluate_paper_promotion_gate(
        _evaluation_input(
            audit_refs=(),
            sessions=(
                _session(
                    "missing-audit",
                    0,
                    30,
                    starting=Decimal("10000"),
                    ending=Decimal("10300"),
                    audit_complete=False,
                ),
            ),
        )
    )

    assert result.recommendation is PaperGateRecommendation.REMAIN_PAPER
    assert "missing audit evidence for paper evaluation" in result.rejection_reasons


def test_beginner_report_answers_required_questions_and_keeps_live_locked() -> None:
    report = build_paper_evaluation_report(_evaluation_input())

    assert "Did paper trading help?" in report.beginner_summary
    assert "What went wrong?" in report.beginner_summary
    assert "What should be changed?" in report.beginner_summary
    assert "Is real trading still locked? Yes." in report.beginner_summary
    assert report.audit_payload()["live_trading_locked"] == "True"
    with pytest.raises(ValueError, match="cannot create live orders"):
        report.create_live_order()


def test_metrics_completed_trade_pairing_and_public_imports() -> None:
    metrics = build_paper_evaluation_metrics(_evaluation_input())

    assert metrics.completed_trade_count == 3
    assert metrics.win_rate == Decimal("1.0000")
    assert metrics.audit_complete

    import abtp.paper as paper

    assert paper.PaperEvaluationPolicy is PaperEvaluationPolicy
    assert paper.evaluate_paper_promotion_gate is evaluate_paper_promotion_gate


def test_entry_and_exit_fees_turn_apparent_win_into_loss() -> None:
    entry, exit_trade = _profitable_trades(pair_count=1, fee=Decimal("0.2"))
    trades = (entry, replace(exit_trade, price=Decimal("100.3")))
    result = evaluate_paper_promotion_gate(
        _evaluation_input(trades=trades),
        policy=PaperEvaluationPolicy(min_completed_trades=1),
    )
    assert result.metrics.completed_trade_count == 1
    assert result.metrics.expectancy == Decimal("-0.1000")
    assert result.metrics.win_rate == 0
    assert result.metrics.total_fees == Decimal("0.4")
    assert not result.eligible_for_future_tiny_live_proposal
    assert any("unstable expectancy" in reason for reason in result.rejection_reasons)
    assert result.live_trading_locked


def test_partial_exits_do_not_inflate_completed_sample_or_ignore_fees() -> None:
    entry, exit_trade = _profitable_trades(pair_count=1, fee=Decimal("0.2"))
    trades = (
        entry,
        replace(exit_trade, quantity=Decimal("0.4"), fee_paid=Decimal("0.1")),
        replace(
            exit_trade,
            order_intent_id=uuid4(),
            quantity=Decimal("0.6"),
            occurred_at=NOW + timedelta(days=2),
            fee_paid=Decimal("0.1"),
        ),
    )
    result = evaluate_paper_promotion_gate(_evaluation_input(trades=trades))
    assert result.metrics.completed_trade_count == 1
    assert result.metrics.expectancy == Decimal("9.6000")
    assert not result.eligible_for_future_tiny_live_proposal
    assert any("minimum completed paper trades" in reason for reason in result.rejection_reasons)
    open_result = evaluate_paper_promotion_gate(_evaluation_input(trades=trades[:2]))
    assert open_result.metrics.completed_trade_count == 0
    assert not open_result.eligible_for_future_tiny_live_proposal


def test_promotion_metrics_match_shared_closed_position_statistics() -> None:
    from abtp.paper.trade_metrics import trade_metrics

    trades = _profitable_trades(pair_count=3)
    expected = trade_metrics(trades)
    metrics = build_paper_evaluation_metrics(_evaluation_input(trades=tuple(reversed(trades))))
    assert metrics.completed_trade_count == int(expected["closed_trade_count"])
    assert metrics.win_rate == Decimal(expected["win_rate"])
    assert metrics.expectancy == Decimal(expected["expectancy"])


@pytest.mark.parametrize("sell_quantity", ["1", "2"])
def test_incomplete_ledger_cannot_produce_promotion_eligibility(sell_quantity: str) -> None:
    entry, exit_trade = _profitable_trades(pair_count=1)
    trades = (
        (exit_trade,)
        if sell_quantity == "1"
        else (entry, replace(exit_trade, quantity=Decimal(sell_quantity)))
    )
    with pytest.raises(ValueError, match="without matching entry quantity"):
        evaluate_paper_promotion_gate(_evaluation_input(trades=trades))


def _evaluation_input(
    *,
    days: int = 30,
    sessions: tuple[PaperTradingSessionSummary, ...] | None = None,
    trades: tuple[PaperTrade, ...] | None = None,
    daily_loss_events: int = 0,
    weekly_loss_events: int = 0,
    stop_loss_violations: int = 0,
    confidence_calibration_error: Decimal | None = Decimal("0.05"),
    capital_preservation_events: int = 0,
    governance_violations: int = 0,
    audit_refs: tuple[str, ...] = ("audit:paper-evaluation",),
) -> PaperEvaluationInput:
    end = NOW + timedelta(days=days)
    return PaperEvaluationInput(
        sessions=sessions
        or (
            _session(
                "positive",
                0,
                days,
                starting=Decimal("10000"),
                ending=Decimal("10300"),
                executed=3,
                cycle_count=6,
            ),
        ),
        completed_trades=trades or _profitable_trades(pair_count=3),
        evaluation_start=NOW,
        evaluation_end=end,
        generated_at=end,
        daily_loss_events=daily_loss_events,
        weekly_loss_events=weekly_loss_events,
        stop_loss_violations=stop_loss_violations,
        confidence_calibration_error=confidence_calibration_error,
        capital_preservation_events=capital_preservation_events,
        governance_violations=governance_violations,
        audit_refs=audit_refs,
        source_refs={"fixture": "stage073"},
    )


def _session(
    session_id: str,
    start_day: int,
    end_day: int,
    *,
    starting: Decimal,
    ending: Decimal,
    executed: int = 3,
    blocked: int = 0,
    risk_rejected: int = 0,
    no_signal: int = 0,
    cycle_count: int = 6,
    equities: tuple[Decimal, ...] | None = None,
    audit_complete: bool = True,
) -> PaperTradingSessionSummary:
    equity_values = equities or tuple(starting for _ in range(max(0, cycle_count - 1)))
    cycles = tuple(
        _Cycle(
            metrics={"equity": equity},
            audit_events=({"audit": "ok"},) if audit_complete else (),
        )
        for equity in equity_values[:cycle_count]
    )
    return PaperTradingSessionSummary(
        session_id=session_id,
        started_at=NOW + timedelta(days=start_day),
        ended_at=NOW + timedelta(days=end_day),
        cycles=cycles,  # type: ignore[arg-type]
        executed_count=executed,
        blocked_count=blocked,
        risk_rejected_count=risk_rejected,
        no_signal_count=no_signal,
        starting_equity=starting,
        ending_equity=ending,
        realized_pnl=ending - starting,
        total_fees=Decimal("0.30"),
        status="completed",
        blocked_reason_counts={"fixture block": blocked} if blocked else {},
    )


def _profitable_trades(
    *,
    pair_count: int,
    fee: Decimal = Decimal("0.10"),
) -> tuple[PaperTrade, ...]:
    trades: list[PaperTrade] = []
    for index in range(pair_count):
        trades.append(
            PaperTrade(
                order_intent_id=uuid4(),
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                price=Decimal("100") + Decimal(index),
                fee_paid=fee,
                occurred_at=NOW + timedelta(days=index * 2),
            )
        )
        trades.append(
            PaperTrade(
                order_intent_id=uuid4(),
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                price=Decimal("110") + Decimal(index),
                fee_paid=fee,
                occurred_at=NOW + timedelta(days=index * 2 + 1),
            )
        )
    return tuple(trades)
