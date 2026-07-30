"""Typed environment settings for ABTP profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from os import environ


class TradingMode(StrEnum):
    """Supported runtime modes."""

    RESEARCH = "research"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class SecretRef:
    """Presence-only reference to a secret stored in an environment variable."""

    env_var: str
    is_present: bool

    @property
    def masked(self) -> str:
        return "***" if self.is_present else "<missing>"


@dataclass(frozen=True, slots=True)
class CredentialRefs:
    """Separate credential references for live exchange access."""

    api_key: SecretRef = SecretRef("ABTP_LIVE_EXCHANGE_API_KEY", False)
    api_secret: SecretRef = SecretRef("ABTP_LIVE_EXCHANGE_API_SECRET", False)
    api_passphrase: SecretRef = SecretRef("ABTP_LIVE_EXCHANGE_API_PASSPHRASE", False)


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Risk limit settings parsed from environment configuration."""

    max_order_notional: Decimal
    max_position_percent: Decimal
    max_daily_loss_percent: Decimal
    max_open_orders: int


@dataclass(frozen=True, slots=True)
class FeeAssumptions:
    """Fee and slippage assumptions used before exchange-specific modules exist."""

    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    slippage_ceiling_bps: Decimal


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    """Environment-driven settings with live execution locked off until enabled later."""

    environment: str = "development"
    safe_mode: bool = True
    trading_mode: TradingMode = TradingMode.PAPER
    enable_live_trading_requested: bool = False
    log_level: str = "INFO"
    audit_event_sink: str = "stdout"
    manual_live_confirmation: bool = False

    @property
    def live_execution_supported(self) -> bool:
        """Stage 006 validates live profiles but still does not execute live orders."""

        return False

    @property
    def can_execute_live(self) -> bool:
        """Return whether runtime is allowed to execute live orders."""

        return (
            self.live_execution_supported
            and not self.safe_mode
            and self.trading_mode is TradingMode.LIVE
            and self.enable_live_trading_requested
            and self.manual_live_confirmation
        )

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, defaults: RuntimeSettings | None = None
    ) -> RuntimeSettings:
        """Build runtime settings from environment variables."""

        source = _env_source(env)
        base = cls() if defaults is None else defaults
        return cls(
            environment=source.get("ABTP_ENV", base.environment),
            safe_mode=_env_bool(source, "SAFE_MODE", default=base.safe_mode),
            trading_mode=TradingMode(source.get("ABTP_TRADING_MODE", base.trading_mode.value)),
            enable_live_trading_requested=_env_bool(
                source,
                "ABTP_ENABLE_LIVE_TRADING",
                default=base.enable_live_trading_requested,
            ),
            log_level=source.get("ABTP_LOG_LEVEL", base.log_level),
            audit_event_sink=source.get("ABTP_AUDIT_EVENT_SINK", base.audit_event_sink),
            manual_live_confirmation=_manual_live_confirmation(source),
        )


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Complete typed ABTP settings for one environment profile."""

    profile: str
    runtime: RuntimeSettings
    exchange_names: tuple[str, ...]
    asset_universe: tuple[str, ...]
    candle_intervals: tuple[str, ...]
    data_providers: tuple[str, ...]
    database_url: str
    risk_limits: RiskLimits
    fee_assumptions: FeeAssumptions
    paper_trading_enabled: bool
    live_trading_enabled: bool
    credentials: CredentialRefs = CredentialRefs()


def load_settings(env: Mapping[str, str] | None = None, *, validate: bool = True) -> AppSettings:
    """Load typed settings from environment variables."""

    from abtp.config.profiles import ProfileName, default_profile
    from abtp.config.validation import validate_settings

    source = _env_source(env)
    profile = ProfileName(source.get("ABTP_PROFILE", "paper"))
    settings = default_profile(profile)
    runtime = RuntimeSettings.from_env(source, defaults=settings.runtime)

    settings = replace(
        settings,
        runtime=runtime,
        exchange_names=_env_csv(source, "ABTP_EXCHANGES", settings.exchange_names),
        asset_universe=_env_csv(source, "ABTP_ASSET_UNIVERSE", settings.asset_universe),
        candle_intervals=_env_csv(source, "ABTP_CANDLE_INTERVALS", settings.candle_intervals),
        data_providers=_env_csv(source, "ABTP_DATA_PROVIDERS", settings.data_providers),
        database_url=source.get("ABTP_DATABASE_URL", settings.database_url),
        risk_limits=RiskLimits(
            max_order_notional=_env_decimal(
                source, "ABTP_MAX_ORDER_NOTIONAL", settings.risk_limits.max_order_notional
            ),
            max_position_percent=_env_decimal(
                source, "ABTP_MAX_POSITION_PERCENT", settings.risk_limits.max_position_percent
            ),
            max_daily_loss_percent=_env_decimal(
                source,
                "ABTP_MAX_DAILY_LOSS_PERCENT",
                settings.risk_limits.max_daily_loss_percent,
            ),
            max_open_orders=_env_int(
                source, "ABTP_MAX_OPEN_ORDERS", settings.risk_limits.max_open_orders
            ),
        ),
        fee_assumptions=FeeAssumptions(
            maker_fee_bps=_env_decimal(
                source, "ABTP_MAKER_FEE_BPS", settings.fee_assumptions.maker_fee_bps
            ),
            taker_fee_bps=_env_decimal(
                source, "ABTP_TAKER_FEE_BPS", settings.fee_assumptions.taker_fee_bps
            ),
            slippage_ceiling_bps=_env_decimal(
                source,
                "ABTP_SLIPPAGE_CEILING_BPS",
                settings.fee_assumptions.slippage_ceiling_bps,
            ),
        ),
        paper_trading_enabled=_env_bool(
            source, "ABTP_ENABLE_PAPER_TRADING", default=settings.paper_trading_enabled
        ),
        live_trading_enabled=_env_bool(
            source, "ABTP_ENABLE_LIVE_TRADING", default=settings.live_trading_enabled
        ),
        credentials=CredentialRefs(
            api_key=_secret_ref(source, "ABTP_LIVE_EXCHANGE_API_KEY"),
            api_secret=_secret_ref(source, "ABTP_LIVE_EXCHANGE_API_SECRET"),
            api_passphrase=_secret_ref(source, "ABTP_LIVE_EXCHANGE_API_PASSPHRASE"),
        ),
    )

    if validate:
        validate_settings(settings)

    return settings


def _env_source(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return environ if env is None else env


def _secret_ref(env: Mapping[str, str], name: str) -> SecretRef:
    return SecretRef(env_var=name, is_present=bool(env.get(name, "").strip()))


def _env_bool(env: Mapping[str, str], name: str, *, default: bool) -> bool:
    value = env.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(env: Mapping[str, str], name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = env.get(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_decimal(env: Mapping[str, str], name: str, default: Decimal) -> Decimal:
    value = env.get(name)
    if value is None:
        return default
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal value") from exc


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name)
    if value is None:
        return default
    return int(value)


def _manual_live_confirmation(env: Mapping[str, str]) -> bool:
    expected = "I_UNDERSTAND_ABTP_LIVE_RISK"
    return env.get("ABTP_LIVE_MANUAL_CONFIRMATION") == expected
