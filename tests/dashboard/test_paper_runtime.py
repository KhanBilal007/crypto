from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from threading import Event, Thread

import pytest

from abtp.dashboard import paper_app
from abtp.dashboard.paper_server import PaperDashboardHTTPServer


def test_binance_outage_cannot_load_demo_candles(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable() -> None:
        raise OSError("offline")

    monkeypatch.setattr(paper_app, "_binance_snapshots_and_daily_confirmation", unavailable)
    with pytest.raises(ValueError, match="demo fallback is disabled"):
        paper_app.build_default_paper_dashboard_controller(market_data_source="binance")


def test_default_source_is_binance_not_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABTP_MARKET_DATA_SOURCE")

    def unavailable() -> None:
        raise OSError("offline")

    monkeypatch.setattr(paper_app, "_binance_snapshots_and_daily_confirmation", unavailable)
    with pytest.raises(ValueError, match="Binance market data unavailable"):
        paper_app.build_default_paper_dashboard_controller()
    with pytest.raises(ValueError, match="market data source must be"):
        paper_app.build_default_paper_dashboard_controller(market_data_source="typo")


def test_missing_binance_tickers_and_tape_never_invent_prices_or_trades() -> None:
    class UnavailableAdapter:
        pass

    adapter = UnavailableAdapter()
    watchlist = paper_app._binance_watchlist(adapter)  # type: ignore[arg-type]
    assert all(item.price is None and item.source == "binance spot" for item in watchlist)
    assert paper_app._binance_recent_market_trades(adapter) == ()  # type: ignore[arg-type]


def test_binance_latency_is_measured_and_consistent_across_views() -> None:
    controller = paper_app.build_default_paper_dashboard_controller(market_data_source="demo")
    controller.requested_market_data_source = "binance"
    state = controller.state()
    assert state["market"]["latency_ms"] == "not_available"  # type: ignore[index]
    assert state["runtime_telemetry"]["latency_ms"] == "not_available"  # type: ignore[index]

    controller.last_market_latency_ms = 1234
    state = controller.state()
    assert state["market"]["latency_ms"] == "1234"  # type: ignore[index]
    assert state["runtime_telemetry"]["latency_ms"] == "1234"  # type: ignore[index]


def test_server_advances_without_browser_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = paper_app.build_default_paper_dashboard_controller(market_data_source="demo")
    refreshed = Event()

    def refresh(self: paper_app.PaperDashboardController) -> None:
        refreshed.set()

    monkeypatch.setattr(paper_app.PaperDashboardController, "refresh_market_data_if_due", refresh)
    server = PaperDashboardHTTPServer(("127.0.0.1", 0), controller)
    worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    worker.start()
    try:
        assert refreshed.wait(timeout=2)
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()
    assert not worker.is_alive()


def test_refresh_backfills_observations_without_stale_fills_and_pause_applies_to_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = paper_app.build_default_paper_dashboard_controller(market_data_source="demo")
    controller.requested_market_data_source = "binance"
    new = tuple(paper_app._candle(i, Decimal("104")) for i in range(4, 7))

    class Adapter:
        def __init__(self, *args: object) -> None:
            pass

        def order_book(self, pair: object) -> paper_app.OrderBookSnapshot:
            return paper_app._demo_order_book(Decimal("104"))

        def candles(self, pair: object, interval: str, limit: int) -> tuple[paper_app.Candle, ...]:
            if interval == "1h":
                return new
            return tuple(replace(candle, interval="1d") for candle in new)

    monkeypatch.setattr(paper_app, "BinanceSpotMarketDataAdapter", Adapter)
    controller.pause()
    before = [
        len(engine.account.trades)
        for engine in (controller.engine, *controller.shadow_engines.values())
    ]
    now = new[-1].closed_at + paper_app.timedelta(seconds=1)
    controller.refresh_market_data_if_due(now=now)
    assert controller.missed_execution_candles == 2
    assert controller.engine.last_processed_at == new[-1].closed_at
    for count, engine in zip(
        before, (controller.engine, *controller.shadow_engines.values()), strict=True
    ):
        assert len(engine.account.trades) == count
        assert len(engine.cycles) == 7
    controller.last_market_refresh_at = None
    controller.refresh_market_data_if_due(now=now)
    assert len(controller.engine.cycles) == 7
    assert controller.missed_execution_candles == 2


def test_restart_restores_stops_and_emergency_stop(tmp_path: Path) -> None:
    path = str(tmp_path / "state.json")
    controller = paper_app.build_default_paper_dashboard_controller(
        market_data_source="demo", state_path=path
    )
    for engine in (controller.engine, *controller.shadow_engines.values()):
        engine.restore_runtime_state(
            stop_loss=Decimal("90"),
            take_profit=Decimal("120"),
            last_processed_at=engine.last_processed_at,
        )
    controller.emergency_stop()
    restored = paper_app.build_default_paper_dashboard_controller(
        market_data_source="demo", state_path=path
    )
    assert restored.api.control_state.kill_switch_active
    for engine in (restored.engine, *restored.shadow_engines.values()):
        assert engine.runtime_state()["stop_loss"] == "90"
        assert engine.runtime_state()["take_profit"] == "120"
