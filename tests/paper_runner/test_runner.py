from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from abtp.api.paper import PaperPortfolioStatus, PaperStatusResponse
from abtp.config import TradingMode
from abtp.data import DataQualityStatus, DataTrustLevel, OrderBookMetrics
from abtp.data.heartbeat import StreamHealth
from abtp.domain import Asset, AssetPair, Candle, Exchange
from abtp.exchanges.health import ExchangeHealthInput, score_exchange_health
from abtp.exchanges.reliability import ReliabilityInput, score_reliability
from abtp.intelligence import (
    DecisionEvidence,
    DecisionEvidenceType,
    DecisionHubInput,
    DecisionStance,
    build_institutional_decision,
)
from abtp.observability.metrics import MetricsRegistry
from abtp.paper import (
    PaperCommandCenterInput,
    PaperMarketSnapshot,
    PaperRunnerCycleStatus,
    PaperTradeChecklistInput,
    PaperTradingConfig,
    PaperTradingCycleInput,
    PaperTradingEngine,
    PaperTradingRunner,
    PaperTradingSessionConfig,
    StopLossMetadata,
    build_paper_command_recommendation,
    run_paper_session,
)
from abtp.risk import RiskPolicy
from abtp.strategies import MinRiskSpotStrategyV1

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PAIR = AssetPair(Asset("BTC"), Asset("USDT"))
DEFAULT_STOP_LOSS = StopLossMetadata(
    stop_loss_price=Decimal("95"),
    source_ref="fixture:stop",
    rationale="fixture stop-loss",
)


def test_runner_executes_simulated_paper_trade_after_command_and_risk_gates() -> None:
    engine = _engine()
    runner = PaperTradingRunner(engine=engine, config=_session_config())
    results = [
        runner.run_cycle(_cycle_input(index, close))
        for index, close in enumerate(("100", "101", "102", "104"))
    ]

    assert results[-1].status is PaperRunnerCycleStatus.EXECUTED
    assert results[-1].engine_cycle is not None
    assert results[-1].engine_cycle.risk_decision_status == "approved"
    assert engine.account.trades
    assert engine.account.state.base_quantity > Decimal("0")


def test_runner_records_risk_rejection_without_paper_fill() -> None:
    engine = _engine(risk_policy=RiskPolicy(kill_switch_active=True))
    runner = PaperTradingRunner(engine=engine, config=_session_config())
    results = [
        runner.run_cycle(_cycle_input(index, close))
        for index, close in enumerate(("100", "101", "102", "104"))
    ]

    assert results[-1].status is PaperRunnerCycleStatus.RISK_REJECTED
    assert "Risk Management Engine rejected simulated paper order" in results[-1].blocked_reasons
    assert not engine.account.trades


def test_command_center_rejection_blocks_before_engine_route() -> None:
    engine = _engine()
    runner = PaperTradingRunner(engine=engine, config=_session_config())
    command = _command(confidence=Decimal("0.50"))

    result = runner.run_cycle(_cycle_input(0, "100", command=command))

    assert result.status is PaperRunnerCycleStatus.SKIPPED
    assert "command center label is AVOID" in result.blocked_reasons
    assert not engine.cycles


def test_missing_stop_loss_blocks_cycle() -> None:
    result = PaperTradingRunner(engine=_engine(), config=_session_config()).run_cycle(
        _cycle_input(0, "100", stop_loss=None)
    )

    assert result.status is PaperRunnerCycleStatus.SKIPPED
    assert "stop-loss metadata is required" in result.blocked_reasons


def test_stale_data_exchange_block_and_kill_switch_block_cycle() -> None:
    runner = PaperTradingRunner(engine=_engine(), config=_session_config())

    stale = runner.run_cycle(_cycle_input(0, "100", stale=True))
    exchange = runner.run_cycle(_cycle_input(1, "101", exchange_health_block=True))
    kill = runner.run_cycle(_cycle_input(2, "102", kill_switch_active=True))

    assert "market snapshot is stale" in stale.blocked_reasons
    assert "exchange health blocks paper runner" in exchange.blocked_reasons
    assert "paper runner kill switch is active" in kill.blocked_reasons


def test_session_summary_and_blocked_metrics_are_deterministic() -> None:
    metrics = MetricsRegistry()
    summary = run_paper_session(
        engine=_engine(),
        config=_session_config(session_id="session-072"),
        cycle_inputs=(
            _cycle_input(0, "100", exchange_health_block=True),
            _cycle_input(1, "101", exchange_health_block=True),
        ),
        metrics=metrics,
    )

    assert summary.status == "all_cycles_blocked"
    assert summary.blocked_count == 2
    assert summary.blocked_reason_counts["exchange health blocks paper runner"] == 2
    assert "Live trading remains locked." in summary.render_text()
    assert len(metrics.series("abtp_paper_runner_blocked_cycle_count")) == 2


def test_no_live_mode_and_live_credentials_fail_closed() -> None:
    runner = PaperTradingRunner(
        engine=_engine(),
        config=_session_config(trading_mode=TradingMode.LIVE, allow_live_credentials=True),
    )

    result = runner.run_cycle(_cycle_input(0, "100", live_mode_requested=True))

    assert "paper runner requires paper trading mode" in result.blocked_reasons
    assert "paper runner forbids live credentials" in result.blocked_reasons
    assert "live mode is not allowed for paper runner" in result.blocked_reasons


def test_runner_audit_payload_and_authority_guards() -> None:
    runner = PaperTradingRunner(engine=_engine(), config=_session_config())
    result = runner.run_cycle(_cycle_input(0, "100", capital_protection_block=True))

    assert result.audit_payload()["status"] == "skipped"
    assert result.audit_events[0]["command_label"] == "BUY REVIEW"
    with pytest.raises(ValueError, match="cannot create live orders"):
        result.create_live_order()
    with pytest.raises(ValueError, match="cannot submit orders"):
        runner.submit_order(object())
    with pytest.raises(ValueError, match="cannot enable live trading"):
        runner.enable_live_trading()


def test_public_imports_are_available() -> None:
    import abtp.paper as paper

    assert paper.PaperTradingRunner is PaperTradingRunner
    assert paper.run_paper_session is run_paper_session


def _engine(*, risk_policy: RiskPolicy | None = None) -> PaperTradingEngine:
    return PaperTradingEngine(
        strategy=MinRiskSpotStrategyV1(),
        config=PaperTradingConfig(timeframe="1h", order_quantity=Decimal("0.01")),
        risk_policy=risk_policy,
    )


def _session_config(
    *,
    session_id: str = "stage-072",
    trading_mode: TradingMode = TradingMode.PAPER,
    allow_live_credentials: bool = False,
) -> PaperTradingSessionConfig:
    return PaperTradingSessionConfig(
        session_id=session_id,
        trading_mode=trading_mode,
        allow_live_credentials=allow_live_credentials,
    )


def _cycle_input(
    index: int,
    close: str,
    *,
    command=None,
    stop_loss: StopLossMetadata | None = DEFAULT_STOP_LOSS,
    stale: bool = False,
    exchange_health_block: bool = False,
    kill_switch_active: bool = False,
    capital_protection_block: bool = False,
    live_mode_requested: bool = False,
) -> PaperTradingCycleInput:
    return PaperTradingCycleInput(
        snapshot=_snapshot(index, close, stale=stale),
        command=command or _command(),
        stop_loss=stop_loss,
        exchange_health_block=exchange_health_block,
        kill_switch_active=kill_switch_active,
        capital_protection_block=capital_protection_block,
        live_mode_requested=live_mode_requested,
    )


def _command(*, confidence: Decimal = Decimal("0.74")):
    return build_paper_command_recommendation(
        PaperCommandCenterInput(
            checklist_input=PaperTradeChecklistInput(
                decision=_decision(confidence=confidence),
                paper_status=_paper_status(),
                data_quality=_trusted_quality("fixture:data"),
                exchange_health=_exchange_health(),
                generated_at=NOW,
                max_paper_position_size=Decimal("0.05"),
                stop_loss_required=True,
                stop_loss_price=Decimal("95"),
            ),
            audit_ref="audit:stage072",
            generated_at=NOW,
        )
    )


def _paper_status() -> PaperStatusResponse:
    return PaperStatusResponse(
        current_btc_price=Decimal("100"),
        active_regime="trend_up",
        latest_signal="buy",
        latest_risk_decision="approved",
        blocked_reason="none",
        data_health="healthy",
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
        kill_switch_active=False,
        cycles_count=0,
        trades_count=0,
        updated_at=NOW,
    )


def _decision(*, confidence: Decimal = Decimal("0.74")):
    return build_institutional_decision(
        DecisionHubInput(
            symbol="BTC",
            generated_at=NOW,
            evidence=tuple(
                _evidence(evidence_type, confidence=confidence)
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


def _evidence(evidence_type: DecisionEvidenceType, *, confidence: Decimal) -> DecisionEvidence:
    return DecisionEvidence(
        evidence_type=evidence_type,
        source_ref=f"fixture:{evidence_type.value}",
        summary=f"{evidence_type.value} supports paper runner",
        confidence=confidence,
        support_score=Decimal("0.72"),
        risk_score=Decimal("0.20"),
        quality=_trusted_quality(evidence_type.value),
        stance=DecisionStance.SUPPORTIVE,
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
                best_bid=Decimal("99.95"),
                best_ask=Decimal("100.05"),
                spread=Decimal("0.10"),
                bid_depth=Decimal("2.5"),
                ask_depth=Decimal("2.0"),
                imbalance=Decimal("0.11"),
            ),
        )
    )


def _snapshot(index: int, close: str, *, stale: bool = False) -> PaperMarketSnapshot:
    candle = _candle(index, Decimal(close))
    received_at = candle.closed_at + timedelta(seconds=1)
    return PaperMarketSnapshot(
        candle=candle,
        order_book_metrics=OrderBookMetrics(
            best_bid=candle.close - Decimal("0.01"),
            best_ask=candle.close + Decimal("0.01"),
            spread=Decimal("0.02"),
            bid_depth=Decimal("5"),
            ask_depth=Decimal("4"),
            imbalance=Decimal("0.1111111111111111111111111111"),
        ),
        health=StreamHealth(
            is_connected=not stale,
            is_stale=stale,
            is_degraded=stale,
            disconnect_count=1 if stale else 0,
            last_message_at=received_at,
            latency_ms=2000 if stale else 10,
            stale_after=timedelta(seconds=30),
        ),
        received_at=received_at,
    )


def _candle(index: int, close: Decimal) -> Candle:
    opened_at = NOW + timedelta(hours=index)
    return Candle(
        exchange=Exchange("fixture"),
        pair=PAIR,
        interval="1h",
        opened_at=opened_at,
        closed_at=opened_at + timedelta(hours=1),
        open=close,
        high=close * Decimal("1.005"),
        low=close * Decimal("0.995"),
        close=close,
        volume=Decimal("1"),
    )


def _trusted_quality(source_ref: str) -> DataQualityStatus:
    return DataQualityStatus(
        trust_level=DataTrustLevel.TRUSTED,
        issues=(),
        source_ref=source_ref,
        checked_at=NOW,
    )
