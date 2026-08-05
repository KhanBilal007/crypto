from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.domain import Asset, AssetPair
from abtp.exchanges import (
    BinanceSpotMarketDataAdapter,
    BinanceSpotMarketDataConfig,
    UnsupportedOperationError,
)


class FixtureBinanceAdapter(BinanceSpotMarketDataAdapter):
    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, object]:
        if path == "/api/v3/ticker/price":
            assert params == {"symbol": "BTCUSDT"}
            return {"symbol": "BTCUSDT", "price": "64784.79"}
        if path == "/api/v3/ticker/24hr":
            assert params == {"symbol": "BTCUSDT"}
            return {"symbol": "BTCUSDT", "priceChangePercent": "2.34"}
        if path == "/api/v3/depth":
            assert params == {"symbol": "BTCUSDT", "limit": "10"}
            return {
                "lastUpdateId": 1,
                "bids": [["64783.99", "0.18"], ["64783.98", "0.20"]],
                "asks": [["64784.00", "5.64"], ["64784.01", "0.40"]],
            }
        raise AssertionError(path)

    def _get_json_array(self, path: str, params: dict[str, str]) -> list[list[object]]:
        if path == "/api/v3/klines":
            assert params == {"symbol": "BTCUSDT", "interval": "1h", "limit": "6"}
            return [
                [
                    1785445200000,
                    "64777.38",
                    "64802.48",
                    "64700.34",
                    "64735.53",
                    "227",
                    1785448799999,
                ],
                [
                    1785448800000,
                    "64735.53",
                    "65029.29",
                    "64668.91",
                    "64851.16",
                    "482",
                    1785452399999,
                ],
                [
                    1785452400000,
                    "64851.16",
                    "65086.40",
                    "64740.00",
                    "64780.02",
                    "491",
                    1785455999999,
                ],
                [
                    1785456000000,
                    "64780.03",
                    "64901.55",
                    "64690.29",
                    "64724.91",
                    "660",
                    1785459599999,
                ],
                [
                    1785459600000,
                    "64724.92",
                    "65409.56",
                    "64724.92",
                    "65078.00",
                    "700",
                    1785463199999,
                ],
            ]
        if path == "/api/v3/aggTrades":
            assert params["symbol"] == "BTCUSDT"
            assert params["limit"] == "20"
            return [
                {"a": 11, "p": "64784.79", "q": "0.010", "T": 1785463199000, "m": False},
                {"a": 12, "p": "64784.78", "q": "0.020", "T": 1785463199500, "m": True},
            ]
        raise AssertionError(path)


def test_binance_spot_adapter_reads_public_price_book_and_candles() -> None:
    adapter = FixtureBinanceAdapter()
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    symbols = adapter.symbols()
    ticker = adapter.ticker(pair)
    change_24h = adapter.price_change_24h_pct(pair)
    book = adapter.order_book(pair)
    candles = adapter.candles(pair, "1h", 4)
    trades = adapter.trades(pair, candles[-1].closed_at.replace(minute=0), candles[-1].closed_at)

    assert {item.pair.symbol for item in symbols} == {"BTC/USDT", "ETH/USDT", "SOL/USDT"}
    assert ticker.price == Decimal("64784.79")
    assert change_24h == Decimal("2.34")
    assert book.bids[0].price == Decimal("64783.99")
    assert book.bids[1].quantity == Decimal("0.20")
    assert book.asks[0].price == Decimal("64784.00")
    assert book.asks[1].quantity == Decimal("0.40")
    assert candles[-1].close == Decimal("65078.00")
    assert candles[-1].volume == Decimal("700")
    assert len(trades) == 2
    assert trades[0].price == Decimal("64784.79")
    assert trades[0].side.value == "buy"
    assert trades[1].side.value == "sell"


def test_binance_spot_adapter_is_read_only() -> None:
    adapter = FixtureBinanceAdapter()

    with pytest.raises(UnsupportedOperationError, match="market-data-only"):
        adapter.submit_order(None)  # type: ignore[arg-type]


def test_binance_spot_market_data_config_defaults_to_public_market_data_host() -> None:
    config = BinanceSpotMarketDataConfig()

    assert config.base_url == "https://data-api.binance.vision"
