"""Isolated Binance Spot Testnet API. Production hosts are not configurable."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID

from abtp.data import normalize_timestamp
from abtp.domain import OrderIntent, OrderSide, OrderType
from abtp.exchanges.errors import ExchangeAdapterError

TESTNET_ORIGIN = "https://testnet.binance.vision"
MAX_TESTNET_NOTIONAL = Decimal("25")
TERMINAL_STATUSES = frozenset({"FILLED", "CANCELED", "EXPIRED", "REJECTED", "EXPIRED_IN_MATCH"})
KNOWN_STATUSES = TERMINAL_STATUSES | {"NEW", "PARTIALLY_FILLED", "PENDING_NEW", "PENDING_CANCEL"}


class TestnetError(ExchangeAdapterError):
    """Sanitized API failure. Unknown outcomes must be reconciled, not retried."""

    def __init__(self, message: str, *, outcome_unknown: bool = False) -> None:
        super().__init__(message)
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class TestnetCredentials:
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.api_key.strip() or not self.api_secret.strip():
            raise ValueError("both Spot Testnet credentials are required")
        if any(ord(char) < 33 or ord(char) > 126 for char in self.api_key + self.api_secret):
            raise ValueError("invalid Spot Testnet credential format")

    @classmethod
    def from_environment(cls) -> TestnetCredentials:
        return cls(
            os.environ.get("ABTP_BINANCE_TESTNET_API_KEY", ""),
            os.environ.get("ABTP_BINANCE_TESTNET_API_SECRET", ""),
        )


@dataclass(frozen=True, slots=True)
class TestnetHTTPResponse:
    status: int
    headers: Mapping[str, str]
    payload: Any


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _transport(request: Request) -> TestnetHTTPResponse:
    # Never forward credentials to redirects or an environment-configured HTTP proxy.
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise TestnetError("testnet response exceeds size limit", outcome_unknown=True)
            return TestnetHTTPResponse(response.status, dict(response.headers), json.loads(raw))
    except HTTPError as error:
        with error:
            return TestnetHTTPResponse(error.code, dict(error.headers), None)
    except (URLError, TimeoutError, OSError, ValueError):
        raise TestnetError("testnet connection or response failure", outcome_unknown=True) from None


def _object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TestnetError("malformed testnet object", outcome_unknown=True)
    return value


def _array(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TestnetError("malformed testnet list", outcome_unknown=True)
    return value


def _decimal(value: Any, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except ArithmeticError:
        raise TestnetError("malformed testnet numeric value", outcome_unknown=True) from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise TestnetError("invalid testnet numeric value", outcome_unknown=True)
    return result


def client_order_id(intent_id: UUID, prefix: str = "a") -> str:
    if prefix not in {"a", "p", "t", "s"}:
        raise ValueError("unsupported testnet client ID prefix")
    return prefix + intent_id.hex


@dataclass(frozen=True, slots=True)
class TestnetSymbolRules:
    symbol: str
    base_asset: str
    quote_asset: str
    order_types: frozenset[str]
    oco_allowed: bool
    filters: tuple[Mapping[str, Any], ...]

    def validate(self, *, quantity: Decimal, price: Decimal, order_type: str) -> None:
        _decimal(quantity, positive=True)
        _decimal(price, positive=True)
        if order_type not in self.order_types:
            raise ValueError("order type is not supported by the testnet symbol")
        kinds = {str(item.get("filterType")) for item in self.filters}
        if not {"LOT_SIZE", "PRICE_FILTER"} <= kinds or not kinds & {"MIN_NOTIONAL", "NOTIONAL"}:
            raise ValueError("required exchange filters are missing")
        for item in self.filters:
            kind = item.get("filterType")
            if kind == "LOT_SIZE" or (kind == "MARKET_LOT_SIZE" and order_type == "MARKET"):
                _check_increment(quantity, item, "minQty", "maxQty", "stepSize")
            elif kind == "PRICE_FILTER" and order_type != "MARKET":
                _check_increment(price, item, "minPrice", "maxPrice", "tickSize")
            elif kind in {"MIN_NOTIONAL", "NOTIONAL"}:
                notional = quantity * price
                applies_min = order_type != "MARKET" or item.get(
                    "applyToMarket", item.get("applyMinToMarket", False)
                )
                if applies_min and notional < _decimal(item.get("minNotional")):
                    raise ValueError("order is below exchange minimum notional")
                if kind == "NOTIONAL" and (
                    order_type != "MARKET" or item.get("applyMaxToMarket", False)
                ):
                    maximum = _decimal(item.get("maxNotional"))
                    if maximum and notional > maximum:
                        raise ValueError("order exceeds exchange maximum notional")


def _check_increment(
    value: Decimal, item: Mapping[str, Any], low: str, high: str, step: str
) -> None:
    minimum, maximum, increment = (_decimal(item.get(key)) for key in (low, high, step))
    if (minimum and value < minimum) or (maximum and value > maximum):
        raise ValueError("order violates exchange quantity/price range")
    if increment and value % increment:
        raise ValueError("order violates exchange quantity/price increment")


@dataclass(frozen=True, slots=True)
class TestnetAccount:
    checked_at: datetime
    can_trade: bool
    balances: Mapping[str, tuple[Decimal, Decimal]]
    taker_fee_rate: Decimal

    def free(self, asset: str) -> Decimal:
        return self.balances.get(asset, (Decimal(0), Decimal(0)))[0]


@dataclass(frozen=True, slots=True)
class TestnetOrder:
    order_id: str
    client_id: str
    symbol: str
    side: str
    status: str
    quantity: Decimal
    filled_quantity: Decimal
    quote_quantity: Decimal
    commissions: Mapping[str, Decimal]
    commissions_complete: bool
    order_type: str
    price: Decimal
    stop_price: Decimal

    @classmethod
    def parse(
        cls, payload: Any, *, symbol: str, expected_client_id: str | None = None
    ) -> TestnetOrder:
        item = _object(payload)
        if item.get("symbol") != symbol or not item.get("orderId"):
            raise TestnetError("testnet order identity mismatch", outcome_unknown=True)
        identifier = str(item.get("clientOrderId", ""))
        if not identifier or (expected_client_id and identifier != expected_client_id):
            raise TestnetError("testnet client order identity mismatch", outcome_unknown=True)
        status = str(item.get("status", ""))
        side = str(item.get("side", ""))
        if status not in KNOWN_STATUSES or side not in {"BUY", "SELL"}:
            raise TestnetError("unknown testnet order status or side", outcome_unknown=True)
        quantity = _decimal(item.get("origQty"), positive=True)
        filled = _decimal(item.get("executedQty"))
        if filled > quantity:
            raise TestnetError("invalid testnet fill quantity", outcome_unknown=True)
        if status == "FILLED" and filled != quantity:
            raise TestnetError("FILLED order has incomplete quantity", outcome_unknown=True)
        order_type = str(item.get("type", ""))
        if order_type not in {
            "LIMIT",
            "MARKET",
            "LIMIT_MAKER",
            "STOP_LOSS",
            "STOP_LOSS_LIMIT",
            "TAKE_PROFIT",
            "TAKE_PROFIT_LIMIT",
        }:
            raise TestnetError("unknown testnet order type", outcome_unknown=True)
        commissions: dict[str, Decimal] = {}
        fill_quantity = Decimal(0)
        for raw in _array(item.get("fills", [])):
            fill = _object(raw)
            fill_quantity += _decimal(fill.get("qty"), positive=True)
            asset = str(fill.get("commissionAsset", ""))
            if not asset:
                raise TestnetError("missing testnet commission asset", outcome_unknown=True)
            commissions[asset] = commissions.get(asset, Decimal(0)) + _decimal(
                fill.get("commission")
            )
        return cls(
            str(item["orderId"]),
            identifier,
            symbol,
            side,
            status,
            quantity,
            filled,
            _decimal(item.get("cummulativeQuoteQty")),
            commissions,
            "fills" in item and fill_quantity == filled,
            order_type,
            _decimal(item.get("price", "0")),
            _decimal(item.get("stopPrice", "0")),
        )


class BinanceSpotTestnetClient:
    """Signed virtual-fund API; cannot be pointed at Binance production."""

    def __init__(
        self,
        credentials: TestnetCredentials | None = None,
        *,
        transport: Callable[[Request], TestnetHTTPResponse] | None = None,
        clock: Callable[[], datetime] | None = None,
        allow_virtual_orders: bool = False,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or _transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._blocked_until: datetime | None = None
        self._allow_virtual_orders = allow_virtual_orders
        self._clock_offset = timedelta(0)
        self._clock_synced_at: datetime | None = None

    def _request(
        self,
        method: str,
        path: str,
        params: Mapping[str, str] | None = None,
        *,
        signed: bool = False,
    ) -> Any:
        allowed = {
            ("GET", "/api/v3/time"),
            ("GET", "/api/v3/exchangeInfo"),
            ("GET", "/api/v3/ticker/bookTicker"),
            ("GET", "/api/v3/ticker/price"),
            ("GET", "/api/v3/account"),
            ("GET", "/api/v3/openOrders"),
            ("GET", "/api/v3/order"),
            ("GET", "/api/v3/myTrades"),
            ("POST", "/api/v3/order/test"),
            ("POST", "/api/v3/order"),
            ("DELETE", "/api/v3/order"),
            ("POST", "/api/v3/orderList/oco"),
            ("GET", "/api/v3/orderList"),
            ("DELETE", "/api/v3/orderList"),
        }
        if (method, path) not in allowed:
            raise ValueError("unsupported testnet endpoint")
        if method != "GET" and path != "/api/v3/order/test" and not self._allow_virtual_orders:
            raise TestnetError(
                "matched testnet orders are disabled; explicit qualification access required"
            )
        now = normalize_timestamp(self._clock())
        if self._blocked_until is not None and now < self._blocked_until:
            raise TestnetError("testnet rate limit cooldown is active")
        values = dict(params or {})
        headers = {"Accept": "application/json", "Cache-Control": "no-cache"}
        if signed:
            if self._credentials is None:
                raise TestnetError("Spot Testnet credentials are not configured")
            if self._clock_synced_at is None or not timedelta(
                0
            ) <= now - self._clock_synced_at <= timedelta(seconds=60):
                self.require_clock_sync()
                now = normalize_timestamp(self._clock())
            values.update(
                timestamp=str(int((now + self._clock_offset).timestamp() * 1000)), recvWindow="5000"
            )
            query = urlencode(values)
            signature = hmac.new(
                self._credentials.api_secret.encode(), query.encode(), hashlib.sha256
            ).hexdigest()
            values["signature"] = signature
            headers["X-MBX-APIKEY"] = self._credentials.api_key
        encoded = urlencode(values)
        data = None
        url = TESTNET_ORIGIN + path
        if method == "GET":
            url += "?" + encoded if encoded else ""
        else:
            data = encoded.encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            response = self._transport(request)
        except Exception:
            raise TestnetError(
                "testnet request outcome unavailable", outcome_unknown=method != "GET"
            ) from None
        if response.status in {418, 429}:
            retry = next(
                (value for key, value in response.headers.items() if key.lower() == "retry-after"),
                "60",
            )
            try:
                seconds = max(60, int(retry))
            except ValueError:
                seconds = 60
            self._blocked_until = now + timedelta(seconds=min(seconds, 86400))
            raise TestnetError("testnet rate limited; automatic retries are disabled")
        if not 200 <= response.status < 300:
            raise TestnetError(
                f"testnet HTTP {response.status}; inspect sanitized qualification status",
                outcome_unknown=method != "GET",
            )
        if isinstance(response.payload, dict) and "code" in response.payload:
            raise TestnetError("testnet API rejected request", outcome_unknown=method != "GET")
        return response.payload

    def server_time(self) -> datetime:
        item = _object(self._request("GET", "/api/v3/time"))
        return datetime.fromtimestamp(int(item["serverTime"]) / 1000, UTC)

    def require_clock_sync(self) -> None:
        before = normalize_timestamp(self._clock())
        server = self.server_time()
        after = normalize_timestamp(self._clock())
        round_trip = after - before
        offset = server - (before + round_trip / 2)
        if (
            round_trip < timedelta(0)
            or round_trip > timedelta(seconds=2)
            or abs(offset) > timedelta(seconds=5)
        ):
            raise TestnetError("local/testnet clocks or request latency are outside limits")
        self._clock_offset = offset
        self._clock_synced_at = after

    def symbol_rules(self, symbol: str) -> TestnetSymbolRules:
        if symbol not in {"BTCUSDT", "ETHUSDT", "SOLUSDT"}:
            raise ValueError("unsupported testnet spot symbol")
        item = _object(self._request("GET", "/api/v3/exchangeInfo", {"symbol": symbol}))
        symbols = _array(item.get("symbols"))
        if len(symbols) != 1:
            raise TestnetError("testnet symbol metadata missing or ambiguous")
        raw = _object(symbols[0])
        if (
            raw.get("symbol") != symbol
            or raw.get("status") != "TRADING"
            or raw.get("isSpotTradingAllowed") is not True
        ):
            raise TestnetError("testnet spot symbol is not tradable")
        return TestnetSymbolRules(
            symbol,
            str(raw["baseAsset"]),
            str(raw["quoteAsset"]),
            frozenset(_array(raw.get("orderTypes"))),
            raw.get("ocoAllowed") is True,
            tuple(_object(value) for value in _array(raw.get("filters"))),
        )

    def account(self) -> TestnetAccount:
        started = normalize_timestamp(self._clock())
        raw = _object(self._request("GET", "/api/v3/account", signed=True))
        if raw.get("accountType") != "SPOT" or raw.get("permissions") != ["SPOT"]:
            raise TestnetError("testnet account is not spot-only")
        balances: dict[str, tuple[Decimal, Decimal]] = {}
        for item in _array(raw.get("balances")):
            row = _object(item)
            asset = str(row.get("asset", ""))
            if not asset or asset in balances:
                raise TestnetError("malformed testnet balance snapshot")
            balances[asset] = (_decimal(row.get("free")), _decimal(row.get("locked")))
        fees = _object(raw.get("commissionRates"))
        return TestnetAccount(
            started, raw.get("canTrade") is True, balances, _decimal(fees.get("taker"))
        )

    def book(self, symbol: str) -> tuple[Decimal, Decimal]:
        raw = _object(self._request("GET", "/api/v3/ticker/bookTicker", {"symbol": symbol}))
        if raw.get("symbol") != symbol:
            raise TestnetError("testnet book symbol mismatch")
        bid, ask = (
            _decimal(raw.get("bidPrice"), positive=True),
            _decimal(raw.get("askPrice"), positive=True),
        )
        if bid >= ask:
            raise TestnetError("testnet book is crossed")
        return bid, ask

    def open_orders(self, symbol: str) -> tuple[TestnetOrder, ...]:
        raw = self._request("GET", "/api/v3/openOrders", {"symbol": symbol}, signed=True)
        return tuple(TestnetOrder.parse(item, symbol=symbol) for item in _array(raw))

    def order(self, symbol: str, identifier: str) -> TestnetOrder:
        raw = self._request(
            "GET", "/api/v3/order", {"symbol": symbol, "origClientOrderId": identifier}, signed=True
        )
        return TestnetOrder.parse(raw, symbol=symbol, expected_client_id=identifier)

    def fills(self, symbol: str, order_id: str) -> tuple[Mapping[str, Any], ...]:
        raw = self._request(
            "GET",
            "/api/v3/myTrades",
            {"symbol": symbol, "orderId": order_id, "limit": "1000"},
            signed=True,
        )
        rows = tuple(_object(item) for item in _array(raw))
        if len(rows) >= 1000 or any(
            str(item.get("orderId")) != order_id or item.get("symbol") != symbol for item in rows
        ):
            raise TestnetError("testnet fills are incomplete or mismatched")
        return rows

    def validate_order(self, intent: OrderIntent) -> None:
        self._request("POST", "/api/v3/order/test", self.order_parameters(intent), signed=True)

    @staticmethod
    def order_parameters(intent: OrderIntent) -> dict[str, str]:
        parameters = {
            "symbol": intent.pair.base.symbol + intent.pair.quote.symbol,
            "side": intent.side.value.upper(),
            "type": intent.order_type.value.upper(),
            "quantity": format(intent.quantity, "f"),
            "newClientOrderId": client_order_id(intent.id),
            "newOrderRespType": "FULL",
        }
        if intent.order_type is OrderType.LIMIT:
            if intent.limit_price is None:
                raise ValueError("limit price is required")
            parameters.update(price=format(intent.limit_price, "f"), timeInForce="FOK")
        return parameters

    def submit_order(self, intent: OrderIntent) -> TestnetOrder:
        from abtp.risk import assert_order_intent_has_approved_risk

        assert_order_intent_has_approved_risk(intent)
        if intent.order_type is not OrderType.LIMIT or intent.limit_price is None:
            raise ValueError("testnet qualification supports bounded LIMIT FOK orders only")
        if intent.quantity * intent.limit_price > MAX_TESTNET_NOTIONAL:
            raise ValueError("testnet qualification order exceeds 25 USDT cap")
        if intent.pair.quote.symbol != "USDT":
            raise ValueError("testnet qualification requires a USDT pair")
        if intent.risk_decision is None or intent.quantity > intent.risk_decision.max_position_size:
            raise ValueError("testnet quantity exceeds approved risk size")
        parameters = self.order_parameters(intent)
        self.symbol_rules(parameters["symbol"]).validate(
            quantity=intent.quantity,
            price=intent.limit_price,
            order_type="LIMIT",
        )
        raw = self._request("POST", "/api/v3/order", parameters, signed=True)
        return TestnetOrder.parse(
            raw, symbol=parameters["symbol"], expected_client_id=parameters["newClientOrderId"]
        )

    def cancel_order(self, symbol: str, identifier: str) -> TestnetOrder:
        raw = self._request(
            "DELETE",
            "/api/v3/order",
            {"symbol": symbol, "origClientOrderId": identifier},
            signed=True,
        )
        # Binance cancellation changes clientOrderId; origClientOrderId identifies the request.
        if _object(raw).get("origClientOrderId") != identifier:
            raise TestnetError("testnet cancellation identity mismatch", outcome_unknown=True)
        return TestnetOrder.parse(raw, symbol=symbol)

    def protect_position(
        self, intent: OrderIntent, *, quantity: Decimal, stop: Decimal, target: Decimal
    ) -> Mapping[str, Any]:
        if intent.side is not OrderSide.BUY:
            raise ValueError("protection requires an entry intent")
        symbol = intent.pair.base.symbol + intent.pair.quote.symbol
        rules = self.symbol_rules(symbol)
        bid, ask = self.book(symbol)
        if not rules.oco_allowed or not stop < bid < ask < target or quantity > intent.quantity:
            raise ValueError("testnet protective order bounds are invalid")
        rules.validate(quantity=quantity, price=target, order_type="LIMIT_MAKER")
        rules.validate(quantity=quantity, price=stop, order_type="STOP_LOSS")
        raw = self._request(
            "POST",
            "/api/v3/orderList/oco",
            {
                "symbol": symbol,
                "side": "SELL",
                "quantity": format(quantity, "f"),
                "listClientOrderId": client_order_id(intent.id, "p"),
                "aboveType": "LIMIT_MAKER",
                "abovePrice": format(target, "f"),
                "aboveClientOrderId": client_order_id(intent.id, "t"),
                "belowType": "STOP_LOSS",
                "belowStopPrice": format(stop, "f"),
                "belowClientOrderId": client_order_id(intent.id, "s"),
            },
            signed=True,
        )
        return _object(raw)

    def order_list(self, identifier: str) -> Mapping[str, Any]:
        raw = _object(
            self._request(
                "GET", "/api/v3/orderList", {"origClientOrderId": identifier}, signed=True
            )
        )
        if raw.get("listClientOrderId") != identifier:
            raise TestnetError("testnet protection identity mismatch", outcome_unknown=True)
        return raw

    def cancel_order_list(self, symbol: str, identifier: str) -> Mapping[str, Any]:
        raw = self._request(
            "DELETE",
            "/api/v3/orderList",
            {"symbol": symbol, "listClientOrderId": identifier},
            signed=True,
        )
        return _object(raw)
