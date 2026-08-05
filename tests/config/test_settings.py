from __future__ import annotations

from decimal import Decimal

import pytest

from abtp.config import ConfigurationError, ProfileName, TradingMode, load_settings


def test_default_profile_is_paper_and_live_execution_remains_disabled() -> None:
    settings = load_settings({})

    assert settings.profile == ProfileName.PAPER
    assert settings.runtime.trading_mode is TradingMode.PAPER
    assert settings.paper_trading_enabled is True
    assert settings.runtime.can_execute_live is False


def test_profile_env_has_precedence_over_trading_mode_for_live_selection() -> None:
    with pytest.raises(ConfigurationError, match="live mode requires ABTP_PROFILE=live"):
        load_settings(
            {
                "ABTP_TRADING_MODE": "live",
                "ABTP_ENABLE_LIVE_TRADING": "true",
            }
        )


def test_live_profile_missing_secrets_fails_without_plaintext_leakage() -> None:
    secret_value = "do-not-leak-this-secret"

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(
            {
                "ABTP_PROFILE": "live",
                "SAFE_MODE": "false",
                "ABTP_ENABLE_LIVE_TRADING": "true",
                "ABTP_LIVE_MANUAL_CONFIRMATION": "I_UNDERSTAND_ABTP_LIVE_RISK",
                "ABTP_LIVE_EXCHANGE_API_KEY": secret_value,
            }
        )

    message = str(exc_info.value)
    assert "ABTP_LIVE_EXCHANGE_API_SECRET is required" in message
    assert secret_value not in message


def test_live_profile_requires_manual_confirmation_and_safe_mode_off() -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(
            {
                "ABTP_PROFILE": "live",
                "ABTP_ENABLE_LIVE_TRADING": "true",
                "ABTP_LIVE_EXCHANGE_API_KEY": "key",
                "ABTP_LIVE_EXCHANGE_API_SECRET": "secret",
            }
        )

    message = str(exc_info.value)
    assert "SAFE_MODE must be false" in message
    assert "ABTP_LIVE_MANUAL_CONFIRMATION" in message
    assert "secret" not in message


def test_valid_live_profile_validates_but_cannot_execute_live() -> None:
    settings = load_settings(
        {
            "ABTP_PROFILE": "live",
            "SAFE_MODE": "false",
            "ABTP_ENABLE_LIVE_TRADING": "true",
            "ABTP_LIVE_MANUAL_CONFIRMATION": "I_UNDERSTAND_ABTP_LIVE_RISK",
            "ABTP_LIVE_EXCHANGE_API_KEY": "key",
            "ABTP_LIVE_EXCHANGE_API_SECRET": "secret",
        }
    )

    assert settings.live_trading_enabled is True
    assert settings.credentials.api_key.masked == "***"
    assert settings.runtime.live_execution_supported is False
    assert settings.runtime.can_execute_live is False


@pytest.mark.parametrize(
    ("env_name", "value", "expected_message"),
    [
        ("ABTP_MAX_ORDER_NOTIONAL", "0", "ABTP_MAX_ORDER_NOTIONAL"),
        ("ABTP_MAX_POSITION_PERCENT", "1.5", "ABTP_MAX_POSITION_PERCENT"),
        ("ABTP_MAX_DAILY_LOSS_PERCENT", "-0.01", "ABTP_MAX_DAILY_LOSS_PERCENT"),
        ("ABTP_MAX_OPEN_ORDERS", "0", "ABTP_MAX_OPEN_ORDERS"),
        ("ABTP_SLIPPAGE_CEILING_BPS", "10001", "ABTP_SLIPPAGE_CEILING_BPS"),
    ],
)
def test_invalid_risk_values_fail_fast(env_name: str, value: str, expected_message: str) -> None:
    with pytest.raises(ConfigurationError, match=expected_message):
        load_settings({"ABTP_PROFILE": "paper", env_name: value})


def test_profile_overrides_parse_typed_values() -> None:
    settings = load_settings(
        {
            "ABTP_PROFILE": "backtest",
            "ABTP_EXCHANGES": "coinbase, kraken",
            "ABTP_ASSET_UNIVERSE": "BTC,ETH,USDT",
            "ABTP_CANDLE_INTERVALS": "1m,1h",
            "ABTP_DATA_PROVIDERS": "fixture,historical",
            "ABTP_MAX_ORDER_NOTIONAL": "250",
            "ABTP_TAKER_FEE_BPS": "12.5",
        }
    )

    assert settings.profile == ProfileName.BACKTEST
    assert settings.exchange_names == ("coinbase", "kraken")
    assert settings.asset_universe == ("BTC", "ETH", "USDT")
    assert settings.candle_intervals == ("1m", "1h")
    assert settings.data_providers == ("fixture", "historical")
    assert settings.risk_limits.max_order_notional == Decimal("250")
    assert settings.fee_assumptions.taker_fee_bps == Decimal("12.5")
