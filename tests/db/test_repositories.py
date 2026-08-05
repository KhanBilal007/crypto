from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from sqlite3 import Connection, IntegrityError
from uuid import UUID

import pytest

from abtp.domain import (
    Asset,
    AssetPair,
    AuditEvent,
    AuditEventType,
    Candle,
    Exchange,
    FeatureVector,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioPosition,
    PortfolioSnapshot,
    Prediction,
    PredictionHorizon,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
    Trade,
)
from abtp.repositories import (
    AuditRepository,
    IntelligenceRepository,
    MarketDataRepository,
    OrderLifecycleEvent,
    OrderRepository,
    PaperDashboardRepository,
    PortfolioSnapshotRepository,
    RiskDecisionRepository,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def fixture_pair() -> AssetPair:
    return AssetPair(Asset("BTC", "Bitcoin"), Asset("USDT", "Tether USD"))


def fixture_exchange() -> Exchange:
    return Exchange("fixture")


def fixture_signal() -> Signal:
    return Signal(
        source="fixture-strategy",
        pair=fixture_pair(),
        generated_at=NOW,
        direction=SignalDirection.HOLD,
        confidence=Decimal("0.60"),
        inputs_ref="fixture:features:1",
        rationale="Fixture signal.",
    )


def test_market_data_repository_round_trips_and_enforces_timestamp_uniqueness(
    migrated_connection: Connection,
) -> None:
    repo = MarketDataRepository(migrated_connection)
    candle = Candle(
        exchange=fixture_exchange(),
        pair=fixture_pair(),
        interval="1m",
        opened_at=NOW,
        closed_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("95"),
        close=Decimal("105"),
        volume=Decimal("1.5"),
    )

    repo.add_candle(candle, data_quality_flags={"gap": False})
    stored = repo.get_candle(
        exchange="fixture",
        pair="BTC/USDT",
        interval="1m",
        opened_at=NOW.isoformat(),
    )

    assert stored == candle
    with pytest.raises(IntegrityError):
        repo.add_candle(candle)


def test_market_data_repository_stores_order_books_and_trades(
    migrated_connection: Connection,
) -> None:
    repo = MarketDataRepository(migrated_connection)
    level = OrderBookLevel(price=Decimal("100"), quantity=Decimal("2"))
    snapshot = OrderBookSnapshot(
        exchange=fixture_exchange(),
        pair=fixture_pair(),
        captured_at=NOW,
        bids=(level,),
        asks=(OrderBookLevel(price=Decimal("101"), quantity=Decimal("1")),),
        source_ref="fixture:book:1",
    )
    trade = Trade(
        exchange=fixture_exchange(),
        pair=fixture_pair(),
        traded_at=NOW,
        price=Decimal("100.5"),
        quantity=Decimal("0.25"),
        side=OrderSide.BUY,
        trade_id="trade-1",
    )

    snapshot_id = repo.add_order_book(snapshot)
    repo.add_trade(trade)

    assert repo.get_order_book(snapshot_id) == snapshot
    assert repo.get_trade(exchange="fixture", trade_id="trade-1") == trade


def test_intelligence_repository_round_trips_features_predictions_and_signals(
    migrated_connection: Connection,
) -> None:
    repo = IntelligenceRepository(migrated_connection)
    pair = fixture_pair()
    repo.add_indicator_value(
        pair=pair.symbol,
        generated_at=NOW,
        indicator_name="sma_20",
        indicator_value=Decimal("100.25"),
        source_ref="fixture:candle:1",
    )
    features = FeatureVector(
        pair=pair,
        generated_at=NOW,
        values={"sma_20": Decimal("100.25")},
        inputs_ref="fixture:candle:1",
        feature_version="features-v1",
    )
    prediction = Prediction(
        pair=pair,
        generated_at=NOW,
        horizon=PredictionHorizon.INTRADAY,
        expected_return=Decimal("0.01"),
        confidence=Decimal("0.7"),
        model_version="model-v1",
        features_ref="fixture:features:1",
        rationale="Fixture prediction.",
    )
    signal = Signal(
        source="fixture-strategy",
        pair=pair,
        generated_at=NOW,
        direction=SignalDirection.BUY,
        confidence=Decimal("0.8"),
        inputs_ref="fixture:prediction:1",
        rationale="Fixture signal.",
        prediction_ref="fixture:prediction:1",
    )

    feature_id = repo.add_feature_vector(features)
    prediction_id = repo.add_prediction(prediction)
    signal_id = repo.add_signal(signal)

    assert repo.get_feature_vector(feature_id) == features
    assert repo.get_prediction(prediction_id) == prediction
    assert repo.get_signal(signal_id) == signal


def test_decision_order_portfolio_and_audit_records_reconstruct_trade_decision(
    migrated_connection: Connection,
) -> None:
    orders = OrderRepository(migrated_connection)
    risks = RiskDecisionRepository(migrated_connection)
    portfolios = PortfolioSnapshotRepository(migrated_connection)
    audits = AuditRepository(migrated_connection)

    signal = fixture_signal()
    intent = OrderIntent(
        pair=signal.pair,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        created_at=NOW,
        signal=signal,
        client_order_ref="fixture-order-1",
    )
    decision = RiskDecision(
        order_intent_id=intent.id,
        status=RiskDecisionStatus.REJECTED,
        checks=(RiskCheck("max-position", False, "position limit exceeded"),),
        evaluated_at=NOW,
        policy_version="risk-v1",
        rationale="Rejected fixture order.",
        max_position_size=Decimal("0.005"),
        stop_loss_required=True,
        kill_switch_active=False,
    )
    snapshot = PortfolioSnapshot(
        captured_at=NOW,
        positions=(
            PortfolioPosition(
                asset=Asset("BTC"),
                quantity=Decimal("0.5"),
                valuation_quote=Asset("USDT"),
                valuation=Decimal("50000"),
            ),
        ),
        source_ref="fixture:portfolio:1",
    )
    audit = AuditEvent(
        event_type=AuditEventType.RISK_DECISION,
        occurred_at=NOW,
        payload={
            "order_intent_id": str(intent.id),
            "risk_policy_version": decision.policy_version,
        },
        causation_id=intent.id,
        correlation_id=UUID("00000000-0000-0000-0000-000000000008"),
    )

    orders.append_intent(intent)
    risks.append(decision)
    snapshot_id = portfolios.add_snapshot(snapshot)
    audits.append(audit)
    orders.append_lifecycle_event(
        OrderLifecycleEvent(
            order_intent_id=intent.id,
            status=OrderStatus.RISK_REJECTED,
            occurred_at=NOW,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            payload={"reason": "risk rejected"},
        )
    )

    assert orders.get_intent(str(intent.id)) == intent
    assert risks.list_for_order(str(intent.id)) == (decision,)
    assert portfolios.get_snapshot(snapshot_id) == snapshot
    assert audits.list_by_correlation(str(audit.correlation_id)) == (audit,)
    assert orders.list_lifecycle_events(str(intent.id))[0].status is OrderStatus.RISK_REJECTED


def test_append_only_tables_reject_update_and_delete(migrated_connection: Connection) -> None:
    audit = AuditEvent(
        event_type=AuditEventType.ORDER_INTENT,
        occurred_at=NOW,
        payload={"order_intent_id": "fixture"},
    )
    event_id = AuditRepository(migrated_connection).append(audit)

    with pytest.raises(IntegrityError, match="append-only"):
        migrated_connection.execute(
            "UPDATE audit_events SET event_type = 'changed' WHERE id = ?",
            (event_id,),
        )
    with pytest.raises(IntegrityError, match="append-only"):
        migrated_connection.execute("DELETE FROM audit_events WHERE id = ?", (event_id,))


def test_secret_like_payload_keys_are_rejected_without_value_leakage(
    migrated_connection: Connection,
) -> None:
    secret_value = "do-not-store-this"
    event = AuditEvent(
        event_type=AuditEventType.MARKET_INPUT,
        occurred_at=NOW,
        payload={"api_key": secret_value},
    )

    with pytest.raises(ValueError) as exc_info:
        AuditRepository(migrated_connection).append(event)

    message = str(exc_info.value)
    assert "api_key" in message
    assert secret_value not in message


def test_order_client_reference_is_unique(migrated_connection: Connection) -> None:
    repo = OrderRepository(migrated_connection)
    signal = fixture_signal()

    first = OrderIntent(
        pair=signal.pair,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        created_at=NOW,
        signal=signal,
        client_order_ref="same-ref",
    )
    second = OrderIntent(
        pair=signal.pair,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        created_at=NOW,
        signal=signal,
        client_order_ref="same-ref",
    )

    repo.append_intent(first)
    with pytest.raises(IntegrityError):
        repo.append_intent(second)


def test_paper_dashboard_repository_round_trips_ledger_payload(
    migrated_connection: Connection,
) -> None:
    repo = PaperDashboardRepository(migrated_connection)
    payload = {
        "version": 2,
        "updated_at": NOW.isoformat(),
        "market_data_source": "demo",
        "ui_preferences": {
            "mode": "strategy_lab",
            "strategy_lab": {
                "strategy": "min_risk_spot_v1",
                "symbol": "BTC/USDT",
                "timeframe": "4h",
                "run_mode": "backtest",
                "parameter_profile": "defensive",
            },
        },
        "account": {
            "cash": "9990",
            "base_quantity": "0.01",
            "average_entry_price": "100",
            "realized_pnl": "0",
            "fees_paid": "0.10",
            "equity_history": ["10000", "9991"],
        },
        "trades": [
            {
                "order_intent_id": "00000000-0000-0000-0000-000000000001",
                "side": "buy",
                "quantity": "0.01",
                "price": "100",
                "fee_paid": "0.10",
                "occurred_at": NOW.isoformat(),
            }
        ],
        "open_paper_orders": [
            {
                "order_id": "paper-order-1",
                "symbol": "BTC/USDT",
                "order_type": "limit",
                "side": "buy",
                "quantity": "0.01",
                "limit_price": "101",
                "stop_price": "not_available",
                "take_profit_price": "not_available",
                "status": "open",
                "created_at": NOW.isoformat(),
                "reason": "fixture",
                "paper_only": True,
            }
        ],
        "alert_rules": [
            {
                "alert_id": "alert-1",
                "alert_type": "price_above",
                "symbol": "BTC/USDT",
                "threshold": "103",
                "expected_value": "",
                "enabled": True,
                "created_at": NOW.isoformat(),
                "paper_only": True,
            }
        ],
        "journal_entries": [
            {
                "journal_id": "journal-1",
                "trade_ref": "00000000-0000-0000-0000-000000000001",
                "symbol": "BTC/USDT",
                "setup_type": "pullback",
                "tags": ["review"],
                "notes": "fixture note",
                "mistake_review": "",
                "lesson": "fixture lesson",
                "chart_context": "fixture chart",
                "strategy": "MinRiskSpotStrategyV1",
                "regime": "bull",
                "created_at": NOW.isoformat(),
                "updated_at": NOW.isoformat(),
                "paper_only": True,
            }
        ],
        "trader_feedback": [
            {
                "feedback_id": "feedback-1",
                "reviewer_role": "trader",
                "category": "order_ticket",
                "severity": "high",
                "status": "open",
                "summary": "Clarify paper-only order ticket.",
                "recommendation": "Add stronger paper-only copy near submit.",
                "resolution": "",
                "created_at": NOW.isoformat(),
                "resolved_at": "",
                "paper_only": True,
            }
        ],
        "chart_drawings": [
            {
                "drawing_id": "drawing-1",
                "drawing_type": "horizontal_level",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_time": NOW.isoformat(),
                "end_time": "",
                "start_price": "104",
                "end_price": "not_available",
                "text": "fixture level",
                "color": "#1264a3",
                "enabled": True,
                "created_at": NOW.isoformat(),
                "paper_only": True,
            }
        ],
    }

    repo.save_state_payload(
        payload,
        strategy_evaluations=[
            {
                "strategy_name": "min_risk_spot_v1",
                "strategy_version": "stage-021.v1",
                "signal_direction": "buy",
                "generated_at": NOW.isoformat(),
            }
        ],
        risk_decisions=[
            {
                "order_intent_id": "00000000-0000-0000-0000-000000000001",
                "status": "approved",
                "evaluated_at": NOW.isoformat(),
            }
        ],
        simulated_fills=[
            {
                "order_intent_id": "00000000-0000-0000-0000-000000000001",
                "side": "buy",
                "quantity": "0.01",
                "price": "100",
                "fee_paid": "0.10",
                "occurred_at": NOW.isoformat(),
            }
        ],
        operator_actions=[
            {
                "event_type": "approve_paper_trade",
                "message": "approved",
                "reason": "fixture",
                "occurred_at": NOW.isoformat(),
            }
        ],
    )

    restored = repo.load_latest_state_payload()

    assert restored is not None
    assert restored["account"]["cash"] == "9990"  # type: ignore[index]
    assert repo.list_transactions()[0]["quantity"] == "0.01"
    assert migrated_connection.execute("SELECT COUNT(*) FROM paper_preferences").fetchone()[0] == 6
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_strategy_evaluations").fetchone()[0]
        == 1
    )
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_risk_decisions").fetchone()[0] == 1
    )
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_simulated_fills").fetchone()[0] == 1
    )
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_operator_actions").fetchone()[0]
        == 1
    )
    assert migrated_connection.execute("SELECT COUNT(*) FROM paper_open_orders").fetchone()[0] == 1
    assert migrated_connection.execute("SELECT COUNT(*) FROM paper_alert_rules").fetchone()[0] == 1
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_journal_entries").fetchone()[0] == 1
    )
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_chart_drawings").fetchone()[0] == 1
    )
    assert (
        migrated_connection.execute("SELECT COUNT(*) FROM paper_trader_feedback").fetchone()[0] == 1
    )
    assert (
        migrated_connection.execute("SELECT order_id FROM paper_open_orders").fetchone()[0]
        == "paper-order-1"
    )
    assert (
        migrated_connection.execute("SELECT alert_type FROM paper_alert_rules").fetchone()[0]
        == "price_above"
    )
    assert (
        migrated_connection.execute("SELECT setup_type FROM paper_journal_entries").fetchone()[0]
        == "pullback"
    )
    assert (
        migrated_connection.execute("SELECT drawing_type FROM paper_chart_drawings").fetchone()[0]
        == "horizontal_level"
    )
    assert (
        migrated_connection.execute("SELECT category FROM paper_trader_feedback").fetchone()[0]
        == "order_ticket"
    )
    assert (
        migrated_connection.execute("SELECT resolution FROM paper_trader_feedback").fetchone()[0]
        == ""
    )


def test_paper_ledger_tables_are_append_only(migrated_connection: Connection) -> None:
    repo = PaperDashboardRepository(migrated_connection)
    payload = {
        "version": 2,
        "updated_at": NOW.isoformat(),
        "market_data_source": "demo",
        "ui_preferences": {"mode": "beginner"},
        "account": {
            "cash": "10000",
            "base_quantity": "0",
            "average_entry_price": "0",
            "realized_pnl": "0",
            "fees_paid": "0",
            "equity_history": ["10000"],
        },
        "trades": [],
        "alert_rules": [
            {
                "alert_id": "alert-append-only",
                "alert_type": "risk_halt",
                "symbol": "BTC/USDT",
                "threshold": "",
                "expected_value": "",
                "enabled": True,
                "created_at": NOW.isoformat(),
                "paper_only": True,
            }
        ],
        "trader_feedback": [
            {
                "feedback_id": "feedback-append-only",
                "reviewer_role": "trader",
                "category": "ui",
                "severity": "low",
                "status": "open",
                "summary": "Fixture feedback.",
                "recommendation": "",
                "resolution": "",
                "created_at": NOW.isoformat(),
                "resolved_at": "",
                "paper_only": True,
            }
        ],
    }
    repo.save_state_payload(payload)
    snapshot_id = migrated_connection.execute(
        "SELECT id FROM paper_account_snapshots LIMIT 1"
    ).fetchone()["id"]
    alert_row_id = migrated_connection.execute(
        "SELECT id FROM paper_alert_rules LIMIT 1"
    ).fetchone()["id"]
    feedback_row_id = migrated_connection.execute(
        "SELECT id FROM paper_trader_feedback LIMIT 1"
    ).fetchone()["id"]

    with pytest.raises(IntegrityError, match="append-only"):
        migrated_connection.execute(
            "UPDATE paper_account_snapshots SET cash = '1' WHERE id = ?",
            (snapshot_id,),
        )
    with pytest.raises(IntegrityError, match="append-only"):
        migrated_connection.execute(
            "UPDATE paper_alert_rules SET enabled = 'False' WHERE id = ?",
            (alert_row_id,),
        )
    with pytest.raises(IntegrityError, match="append-only"):
        migrated_connection.execute(
            "UPDATE paper_trader_feedback SET status = 'closed' WHERE id = ?",
            (feedback_row_id,),
        )
