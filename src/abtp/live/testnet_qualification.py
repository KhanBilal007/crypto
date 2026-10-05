"""Read-only/test-order qualification, separate from the paper strategy feed."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

from abtp.domain import Asset, AssetPair, OrderIntent, OrderSide, OrderType, Signal, SignalDirection
from abtp.exchanges.binance_testnet import (
    MAX_TESTNET_NOTIONAL,
    TESTNET_ORIGIN,
    BinanceSpotTestnetClient,
    TestnetCredentials,
    TestnetError,
)


@dataclass(frozen=True, slots=True)
class QualificationCheck:
    name: str
    passed: bool
    detail: str


def qualify_testnet(
    client: BinanceSpotTestnetClient, *, symbol: str = "BTCUSDT", authenticated: bool = False
) -> dict[str, Any]:
    """Check real testnet responses without placing or cancelling a matched order."""
    checks: list[QualificationCheck] = []
    try:
        client.require_clock_sync()
        checks.append(
            QualificationCheck("clock_and_connectivity", True, "verified against testnet time")
        )
        rules = client.symbol_rules(symbol)
        bid, ask = client.book(symbol)
        checks.append(
            QualificationCheck(
                "exchange_filters_and_book", True, "current testnet metadata and bid/ask received"
            )
        )
        if authenticated:
            account = client.account()
            orders = client.open_orders(symbol)
            if not account.can_trade:
                raise TestnetError("testnet account trading is disabled")
            if orders:
                raise TestnetError("existing testnet orders require review before qualification")
            checks.append(
                QualificationCheck(
                    "signed_account_and_orders",
                    True,
                    "authenticated spot snapshot; no open symbol orders",
                )
            )
            lot = next(item for item in rules.filters if item["filterType"] == "LOT_SIZE")
            step = Decimal(str(lot["stepSize"]))
            price_filter = next(
                item for item in rules.filters if item["filterType"] == "PRICE_FILTER"
            )
            tick = Decimal(str(price_filter["tickSize"]))
            if step <= 0 or tick <= 0:
                raise TestnetError("positive quantity/price increments are required")
            price = (bid / tick).to_integral_value(rounding=ROUND_DOWN) * tick
            budget = min(
                Decimal("20"),
                MAX_TESTNET_NOTIONAL,
                account.free(rules.quote_asset) / (1 + account.taker_fee_rate),
            )
            quantity = (budget / price / step).to_integral_value(rounding=ROUND_DOWN) * step
            rules.validate(quantity=quantity, price=price, order_type="LIMIT")
            pair = AssetPair(Asset(rules.base_asset), Asset(rules.quote_asset))
            now = datetime.now(UTC)
            intent = OrderIntent(
                pair=pair,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                limit_price=price,
                created_at=now,
                signal=Signal(
                    source="testnet-validation-only",
                    pair=pair,
                    generated_at=now,
                    direction=SignalDirection.BUY,
                    confidence=Decimal("0"),
                    inputs_ref="binance-testnet:book",
                    rationale="signature/filter validation; no matched order",
                ),
            )
            client.validate_order(intent)
            checks.append(
                QualificationCheck(
                    "signed_order_validation",
                    True,
                    "order/test accepted; no order was sent to matching",
                )
            )
    except (TestnetError, ValueError, ArithmeticError, KeyError, StopIteration) as exc:
        detail = (
            str(exc)
            if isinstance(exc, (TestnetError, ValueError))
            else "invalid or incomplete qualification evidence"
        )
        checks.append(QualificationCheck("qualification", False, detail))
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": "binance_spot_testnet",
        "endpoint": TESTNET_ORIGIN,
        "symbol": symbol,
        "authenticated_checks_requested": authenticated,
        "checks": [
            {"name": item.name, "passed": item.passed, "detail": item.detail} for item in checks
        ],
        "checks_passed": bool(checks) and all(item.passed for item in checks),
        "matched_orders_created": 0,
        "real_money_enabled": False,
        "live_ready": False,
        "remaining": [
            *([] if authenticated else ["authenticated account and order/test checks"]),
            "virtual-fund fill/cancel/protection/restart lifecycle evidence",
            "verified production key permissions and secure deployment",
            "corrected real-market forward paper evidence and operator review",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Binance Spot Testnet qualification; no matched orders"
    )
    parser.add_argument("--authenticated", action="store_true")
    parser.add_argument("--symbol", choices=("BTCUSDT", "ETHUSDT", "SOLUSDT"), default="BTCUSDT")
    args = parser.parse_args(argv)
    try:
        credentials = TestnetCredentials.from_environment() if args.authenticated else None
    except ValueError:
        print(
            json.dumps(
                {
                    "live_ready": False,
                    "real_money_enabled": False,
                    "error": "testnet credentials missing or invalid; "
                    "configure the TESTNET environment variables",
                }
            )
        )
        return 2
    result = qualify_testnet(
        BinanceSpotTestnetClient(credentials), symbol=args.symbol, authenticated=args.authenticated
    )
    print(json.dumps(result, indent=2))
    return 0 if result["checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
