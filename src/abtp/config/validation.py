"""Validation rules for fail-closed ABTP settings."""

from __future__ import annotations

from decimal import Decimal

from abtp.config.settings import AppSettings, TradingMode


class ConfigurationError(ValueError):
    """Raised when settings are unsafe or invalid."""


def validate_settings(settings: AppSettings) -> None:
    """Validate settings and fail closed with clear non-secret messages."""

    errors: list[str] = []
    errors.extend(_risk_errors(settings))
    errors.extend(_market_errors(settings))
    errors.extend(_profile_errors(settings))

    if errors:
        raise ConfigurationError("; ".join(errors))


def _risk_errors(settings: AppSettings) -> list[str]:
    risk = settings.risk_limits
    fees = settings.fee_assumptions
    errors: list[str] = []

    if risk.max_order_notional <= Decimal("0"):
        errors.append("ABTP_MAX_ORDER_NOTIONAL must be greater than 0")
    if not Decimal("0") < risk.max_position_percent <= Decimal("1"):
        errors.append("ABTP_MAX_POSITION_PERCENT must be greater than 0 and at most 1")
    if not Decimal("0") <= risk.max_daily_loss_percent <= Decimal("1"):
        errors.append("ABTP_MAX_DAILY_LOSS_PERCENT must be between 0 and 1")
    if risk.max_open_orders <= 0:
        errors.append("ABTP_MAX_OPEN_ORDERS must be greater than 0")
    if fees.maker_fee_bps < Decimal("0"):
        errors.append("ABTP_MAKER_FEE_BPS must not be negative")
    if fees.taker_fee_bps < Decimal("0"):
        errors.append("ABTP_TAKER_FEE_BPS must not be negative")
    if not Decimal("0") <= fees.slippage_ceiling_bps <= Decimal("10000"):
        errors.append("ABTP_SLIPPAGE_CEILING_BPS must be between 0 and 10000")

    return errors


def _market_errors(settings: AppSettings) -> list[str]:
    errors: list[str] = []
    if not settings.exchange_names:
        errors.append("ABTP_EXCHANGES must include at least one exchange name")
    if not settings.asset_universe:
        errors.append("ABTP_ASSET_UNIVERSE must include at least one asset")
    if not settings.candle_intervals:
        errors.append("ABTP_CANDLE_INTERVALS must include at least one interval")
    if not settings.data_providers:
        errors.append("ABTP_DATA_PROVIDERS must include at least one provider")
    return errors


def _profile_errors(settings: AppSettings) -> list[str]:
    profile_name = str(settings.profile)
    live_profile_selected = profile_name == "live"
    live_mode_requested = settings.runtime.trading_mode is TradingMode.LIVE

    if not live_profile_selected and not live_mode_requested and not settings.live_trading_enabled:
        return []

    errors: list[str] = []
    if not live_profile_selected:
        errors.append("live mode requires ABTP_PROFILE=live")
    if not live_mode_requested:
        errors.append("live profile requires ABTP_TRADING_MODE=live or profile defaults")
    if settings.runtime.safe_mode:
        errors.append("SAFE_MODE must be false for the live profile")
    if not settings.runtime.enable_live_trading_requested:
        errors.append("ABTP_ENABLE_LIVE_TRADING must be true for the live profile")
    if not settings.live_trading_enabled:
        errors.append("ABTP_ENABLE_LIVE_TRADING must enable live profile settings")
    if not settings.runtime.manual_live_confirmation:
        errors.append("ABTP_LIVE_MANUAL_CONFIRMATION must match the documented confirmation phrase")
    if not settings.credentials.api_key.is_present:
        errors.append("ABTP_LIVE_EXCHANGE_API_KEY is required for the live profile")
    if not settings.credentials.api_secret.is_present:
        errors.append("ABTP_LIVE_EXCHANGE_API_SECRET is required for the live profile")

    return errors
