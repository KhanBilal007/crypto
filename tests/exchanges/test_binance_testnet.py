from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest

from abtp.domain import (
    Asset,
    AssetPair,
    OrderIntent,
    OrderSide,
    OrderType,
    RiskCheck,
    RiskDecision,
    RiskDecisionStatus,
    Signal,
    SignalDirection,
)
from abtp.exchanges.binance_testnet import (
    TESTNET_ORIGIN,
    BinanceSpotTestnetClient,
    client_order_id,
)
from abtp.exchanges.binance_testnet import (
    TestnetCredentials as Credentials,
)
from abtp.exchanges.binance_testnet import (
    TestnetError as APIError,
)
from abtp.exchanges.binance_testnet import (
    TestnetHTTPResponse as Response,
)
from abtp.exchanges.binance_testnet import (
    TestnetOrder as Order,
)
from abtp.live.testnet_qualification import main, qualify_testnet

NOW = datetime(2026, 10, 5, tzinfo=UTC)


def symbol_info() -> dict[str, Any]:
    return {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "status": "TRADING",
                "isSpotTradingAllowed": True,
                "ocoAllowed": True,
                "orderTypes": ["LIMIT", "MARKET", "LIMIT_MAKER", "STOP_LOSS"],
                "filters": [
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.00001",
                        "maxQty": "10",
                        "stepSize": "0.00001",
                    },
                    {
                        "filterType": "MARKET_LOT_SIZE",
                        "minQty": "0",
                        "maxQty": "5",
                        "stepSize": "0",
                    },
                    {
                        "filterType": "PRICE_FILTER",
                        "minPrice": "0.01",
                        "maxPrice": "1000000",
                        "tickSize": "0.01",
                    },
                    {
                        "filterType": "NOTIONAL",
                        "minNotional": "5",
                        "maxNotional": "1000000",
                        "applyMinToMarket": True,
                        "applyMaxToMarket": True,
                    },
                ],
            }
        ]
    }


def account_payload() -> dict[str, Any]:
    return {
        "accountType": "SPOT",
        "permissions": ["SPOT"],
        "canTrade": True,
        "balances": [
            {"asset": "USDT", "free": "1000", "locked": "0"},
            {"asset": "BTC", "free": "1", "locked": "0"},
        ],
        "commissionRates": {"taker": "0.001"},
    }


def intent() -> OrderIntent:
    pair = AssetPair(Asset("BTC"), Asset("USDT"))
    proposed = OrderIntent(
        pair=pair,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.0002"),
        limit_price=Decimal("100000"),
        created_at=NOW,
        signal=Signal(
            source="test",
            pair=pair,
            generated_at=NOW,
            direction=SignalDirection.BUY,
            confidence=Decimal("0.8"),
            inputs_ref="fixture",
            rationale="fixture",
        ),
    )
    return replace(
        proposed,
        risk_decision=RiskDecision(
            order_intent_id=proposed.id,
            status=RiskDecisionStatus.APPROVED,
            checks=(RiskCheck("fixture", True, "fixture"),),
            evaluated_at=NOW,
            policy_version="fixture",
            rationale="fixture",
            max_position_size=Decimal("0.001"),
        ),
    )


def order_payload(proposed: OrderIntent, *, status: str = "FILLED") -> dict[str, Any]:
    return {
        "symbol": "BTCUSDT",
        "orderId": 123,
        "clientOrderId": client_order_id(proposed.id),
        "status": status,
        "side": "BUY",
        "type": "LIMIT",
        "price": "100000",
        "origQty": str(proposed.quantity),
        "executedQty": str(proposed.quantity),
        "cummulativeQuoteQty": "20",
        "fills": [
            {
                "qty": str(proposed.quantity),
                "price": "100000",
                "commissionAsset": "BTC",
                "commission": "0.0000002",
            }
        ],
    }


class FakeHTTP:
    def __init__(self) -> None:
        self.calls: list[Request] = []
        self.responses: dict[tuple[str, str], Any] = {
            ("GET", "/api/v3/time"): {"serverTime": int(NOW.timestamp() * 1000)},
            ("GET", "/api/v3/exchangeInfo"): symbol_info(),
            ("GET", "/api/v3/ticker/bookTicker"): {
                "symbol": "BTCUSDT",
                "bidPrice": "99999",
                "askPrice": "100001",
            },
            ("GET", "/api/v3/account"): account_payload(),
            ("GET", "/api/v3/openOrders"): [],
            ("POST", "/api/v3/order/test"): {},
        }

    def __call__(self, request: Request) -> Response:
        self.calls.append(request)
        payload = self.responses[(request.get_method(), urlsplit(request.full_url).path)]
        if isinstance(payload, Exception):
            raise payload
        if callable(payload):
            payload = payload(request)
        return payload if isinstance(payload, Response) else Response(200, {}, payload)


def client(http: FakeHTTP, *, allow: bool = False) -> BinanceSpotTestnetClient:
    return BinanceSpotTestnetClient(
        Credentials("unit-test-key", "unit-test-secret"),
        transport=http,
        clock=lambda: NOW,
        allow_virtual_orders=allow,
    )


def test_signed_requests_use_testnet_only_and_correct_hmac() -> None:
    http = FakeHTTP()
    api = client(http)
    account = api.account()
    assert account.free("USDT") == Decimal("1000")
    assert account.checked_at == NOW
    request = http.calls[-1]
    assert request.full_url.startswith(TESTNET_ORIGIN + "/api/v3/account?")
    encoded, signature = urlsplit(request.full_url).query.rsplit("&signature=", 1)
    assert signature == hmac.new(b"unit-test-secret", encoded.encode(), hashlib.sha256).hexdigest()
    assert parse_qs(encoded)["recvWindow"] == ["5000"]
    assert request.get_header("X-mbx-apikey") == "unit-test-key"
    assert "unit-test-secret" not in repr(Credentials("unit-test-key", "unit-test-secret"))


def test_credentials_never_fall_back_to_live_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABTP_BINANCE_TESTNET_API_KEY", raising=False)
    monkeypatch.delenv("ABTP_BINANCE_TESTNET_API_SECRET", raising=False)
    monkeypatch.setenv("ABTP_LIVE_EXCHANGE_API_KEY", "must-not-be-used")
    monkeypatch.setenv("ABTP_LIVE_EXCHANGE_API_SECRET", "must-not-be-used")
    with pytest.raises(ValueError, match="credentials are required"):
        Credentials.from_environment()
    assert main(["--authenticated"]) == 2


def test_qualification_uses_test_order_endpoint_and_never_matches_an_order() -> None:
    http = FakeHTTP()
    report = qualify_testnet(client(http), authenticated=True)
    assert report["checks_passed"]
    assert not report["live_ready"] and not report["real_money_enabled"]
    assert report["matched_orders_created"] == 0
    writes = [request for request in http.calls if request.get_method() != "GET"]
    assert len(writes) == 1
    assert urlsplit(writes[0].full_url).path == "/api/v3/order/test"
    assert b"timeInForce=FOK" in (writes[0].data or b"")


def test_public_qualification_does_not_access_account() -> None:
    http = FakeHTTP()
    api = BinanceSpotTestnetClient(transport=http, clock=lambda: NOW)
    report = qualify_testnet(api)
    assert report["checks_passed"] and not report["authenticated_checks_requested"]
    assert all("X-mbx-apikey" not in request.headers for request in http.calls)
    assert all(request.get_method() == "GET" for request in http.calls)


@pytest.mark.parametrize(
    "quantity,price",
    [
        ("0.000001", "100000"),
        ("0.000015", "100000"),
        ("0.00001", "100000"),
        ("0.0002", "100000.001"),
        ("NaN", "100000"),
        ("0.0002", "Infinity"),
    ],
)
def test_exchange_filters_reject_invalid_values(quantity: str, price: str) -> None:
    rules = client(FakeHTTP()).symbol_rules("BTCUSDT")
    with pytest.raises((ValueError, APIError)):
        rules.validate(quantity=Decimal(quantity), price=Decimal(price), order_type="LIMIT")


def test_matched_orders_are_disabled_by_default() -> None:
    http = FakeHTTP()
    with pytest.raises(APIError, match="matched testnet orders are disabled"):
        client(http).submit_order(intent())
    assert all(request.get_method() == "GET" for request in http.calls)


def test_virtual_order_is_bounded_and_has_stable_identity() -> None:
    http = FakeHTTP()
    proposed = intent()
    http.responses[("POST", "/api/v3/order")] = order_payload(proposed)
    result = client(http, allow=True).submit_order(proposed)
    assert result.filled_quantity == proposed.quantity
    assert result.commissions["BTC"] == Decimal("0.0000002")
    assert result.commissions_complete
    assert result.client_id == client_order_id(proposed.id)
    request = http.calls[-1]
    assert len(result.client_id) <= 36
    assert parse_qs((request.data or b"").decode())["newClientOrderId"] == [result.client_id]
    with pytest.raises(ValueError, match="25 USDT cap"):
        client(http, allow=True).submit_order(replace(proposed, quantity=Decimal("0.001")))


@pytest.mark.parametrize("status", ["PARTIALLY_FILLED", "CANCELED", "EXPIRED"])
def test_partial_and_terminal_statuses_are_not_falsely_called_filled(status: str) -> None:
    proposed = intent()
    payload = order_payload(proposed, status=status)
    payload["executedQty"] = "0.0001"
    payload.pop("fills")
    result = Order.parse(payload, symbol="BTCUSDT")
    assert result.status == status
    assert result.filled_quantity == Decimal("0.0001")
    assert not result.commissions_complete


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("unit-test-secret"),
        Response(500, {}, {"secret": "unit-test-secret"}),
        Response(302, {"Location": "https://other.invalid"}, {}),
    ],
)
def test_ambiguous_writes_are_not_retried_or_exposed(failure: Any) -> None:
    http = FakeHTTP()
    http.responses[("POST", "/api/v3/order")] = failure
    with pytest.raises(APIError) as caught:
        client(http, allow=True).submit_order(intent())
    assert caught.value.outcome_unknown
    assert "unit-test-secret" not in str(caught.value)
    assert len([call for call in http.calls if call.get_method() == "POST"]) == 1


def test_rate_limit_obeys_retry_after_without_retry() -> None:
    http = FakeHTTP()
    http.responses[("GET", "/api/v3/account")] = Response(429, {"Retry-After": "120"}, {})
    api = client(http)
    with pytest.raises(APIError, match="rate limited"):
        api.account()
    with pytest.raises(APIError, match="cooldown"):
        api.account()
    assert len(http.calls) == 2


def test_clock_skew_blocks_qualification() -> None:
    http = FakeHTTP()
    http.responses[("GET", "/api/v3/time")] = {
        "serverTime": int((NOW + timedelta(seconds=10)).timestamp() * 1000)
    }
    assert not qualify_testnet(client(http), authenticated=True)["checks_passed"]
    assert len(http.calls) == 1


def test_protective_oco_has_stable_ids_and_market_stop_leg() -> None:
    http = FakeHTTP()
    proposed = intent()
    http.responses[("POST", "/api/v3/orderList/oco")] = {
        "listClientOrderId": client_order_id(proposed.id, "p"),
        "listOrderStatus": "EXECUTING",
    }
    client(http, allow=True).protect_position(
        proposed, quantity=proposed.quantity, stop=Decimal("95000"), target=Decimal("110000")
    )
    params = parse_qs((http.calls[-1].data or b"").decode())
    assert params["belowType"] == ["STOP_LOSS"]
    assert params["side"] == ["SELL"]
    assert params["listClientOrderId"] == [client_order_id(proposed.id, "p")]
    with pytest.raises(ValueError, match="bounds"):
        client(http, allow=True).protect_position(
            proposed, quantity=proposed.quantity, stop=Decimal("110000"), target=Decimal("95000")
        )


def test_unknown_or_mismatched_order_response_is_rejected() -> None:
    proposed = intent()
    payload = order_payload(proposed)
    payload["clientOrderId"] = "someone-elses-order"
    with pytest.raises(APIError, match="identity mismatch"):
        Order.parse(payload, symbol="BTCUSDT", expected_client_id=client_order_id(proposed.id))


def test_small_clock_offset_is_corrected_in_signed_requests() -> None:
    http = FakeHTTP()
    http.responses[("GET", "/api/v3/time")] = {
        "serverTime": int((NOW - timedelta(seconds=2)).timestamp() * 1000)
    }
    client(http).account()
    query = parse_qs(urlsplit(http.calls[-1].full_url).query)
    assert query["timestamp"] == [str(int((NOW - timedelta(seconds=2)).timestamp() * 1000))]


def test_reconciliation_recovers_fees_from_trade_history_without_writing() -> None:
    from abtp.live.testnet_reconciliation import reconcile_testnet_order

    http = FakeHTTP()
    proposed = intent()
    payload = order_payload(proposed)
    payload.pop("fills")
    http.responses[("GET", "/api/v3/order")] = payload
    http.responses[("GET", "/api/v3/myTrades")] = [
        {
            "symbol": "BTCUSDT",
            "orderId": 123,
            "id": 1,
            "isBuyer": True,
            "qty": "0.0002",
            "quoteQty": "20",
            "commission": "0.0000002",
            "commissionAsset": "BTC",
        }
    ]
    report = reconcile_testnet_order(client(http), proposed, require_protection=False)
    assert report["matched"] and not report["blocks_continuation"]
    assert report["commissions_by_asset"] == {"BTC": "2E-7"}
    assert Decimal(report["net_base_after_entry_fees"]) == Decimal("0.0001998")
    assert not report["ledger_halt_cleared"] and not report["live_ready"]
    assert all(call.get_method() == "GET" for call in http.calls)
    http.responses[("GET", "/api/v3/myTrades")] = []
    blocked = reconcile_testnet_order(client(http), proposed, require_protection=False)
    assert not blocked["matched"] and blocked["blocks_continuation"]


def test_reconciliation_confirms_actual_stop_and_target_legs() -> None:
    from abtp.live.testnet_reconciliation import reconcile_testnet_order

    http = FakeHTTP()
    proposed = intent()
    entry = order_payload(proposed)
    http.responses[("GET", "/api/v3/myTrades")] = [
        {
            "symbol": "BTCUSDT",
            "orderId": 123,
            "id": 1,
            "isBuyer": True,
            "qty": "0.0002",
            "quoteQty": "20",
            "commission": "0",
            "commissionAsset": "BTC",
        }
    ]
    target = {
        **entry,
        "orderId": 124,
        "clientOrderId": client_order_id(proposed.id, "t"),
        "side": "SELL",
        "type": "LIMIT_MAKER",
        "price": "110000",
        "status": "NEW",
        "executedQty": "0",
        "cummulativeQuoteQty": "0",
        "fills": [],
    }
    stop = {
        **target,
        "orderId": 125,
        "clientOrderId": client_order_id(proposed.id, "s"),
        "type": "STOP_LOSS",
        "price": "0",
        "stopPrice": "95000",
    }

    def lookup(request: Request) -> dict[str, Any]:
        identifier = parse_qs(urlsplit(request.full_url).query)["origClientOrderId"][0]
        return {
            entry["clientOrderId"]: entry,
            target["clientOrderId"]: target,
            stop["clientOrderId"]: stop,
        }[identifier]

    http.responses[("GET", "/api/v3/order")] = lookup
    http.responses[("GET", "/api/v3/orderList")] = {
        "listClientOrderId": client_order_id(proposed.id, "p"),
        "symbol": "BTCUSDT",
        "contingencyType": "OCO",
        "listOrderStatus": "EXECUTING",
        "orders": [
            {"orderId": 124, "clientOrderId": target["clientOrderId"]},
            {"orderId": 125, "clientOrderId": stop["clientOrderId"]},
        ],
    }
    result = reconcile_testnet_order(client(http), proposed)
    assert result["matched"] and result["protection"] == "exchange_oco_active"
    stop["type"] = "LIMIT"
    blocked = reconcile_testnet_order(client(http), proposed)
    assert blocked["blocks_continuation"]
    assert any("stop/target" in reason for reason in blocked["reasons"])
