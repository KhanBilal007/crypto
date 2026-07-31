from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.domain import Asset, AssetPair
from abtp.exchanges import BinanceSpotMarketDataAdapter, UnsupportedOperationError


class FixtureBinanceAdapter(BinanceSpotMarketDataAdapter):
    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, str]:
        assert params == {"symbol": "BTCUSDT"}
        if path == "/api/v3/ticker/price":
            return {"symbol": "BTCUSDT", "price": "64784.79"}
        if path == "/api/v3/ticker/bookTicker":
            return {
                "symbol": "BTCUSDT",
                "bidPrice": "64783.99",
                "bidQty": "0.18",
                "askPrice": "64784.00",
                "askQty": "5.64",
            }
        raise AssertionError(path)

    def _get_json_array(self, path: str, params: dict[str, str]) -> list[list[object]]:
        assert path == "/api/v3/klines"
        assert params == {"symbol": "BTCUSDT", "interval": "1h", "limit": "6"}
        return [
            [1785445200000, "64777.38", "64802.48", "64700.34", "64735.53", "227", 1785448799999],
            [1785448800000, "64735.53", "65029.29", "64668.91", "64851.16", "482", 1785452399999],
            [1785452400000, "64851.16", "65086.40", "64740.00", "64780.02", "491", 1785455999999],
            [1785456000000, "64780.03", "64901.55", "64690.29", "64724.91", "660", 1785459599999],
            [1785459600000, "64724.92", "65409.56", "64724.92", "65078.00", "700", 1785463199999],
        ]


def test_binance_spot_adapter_reads_public_price_book_and_candles() -> None:
    adapter = FixtureBinanceAdapter()
    pair = AssetPair(Asset("BTC"), Asset("USDT"))

    ticker = adapter.ticker(pair)
    book = adapter.order_book(pair)
    candles = adapter.candles(pair, "1h", 4)

    assert ticker.price == Decimal("64784.79")
    assert book.bids[0].price == Decimal("64783.99")
    assert book.asks[0].price == Decimal("64784.00")
    assert candles[-1].close == Decimal("65078.00")
    assert candles[-1].volume == Decimal("700")


def test_binance_spot_adapter_is_read_only() -> None:
    adapter = FixtureBinanceAdapter()

    with pytest.raises(UnsupportedOperationError, match="market-data-only"):
        adapter.submit_order(None)  # type: ignore[arg-type]
