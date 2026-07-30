"""Minimum-risk BTC spot strategy V1.

This strategy emits non-executable ``Signal`` objects only. It does not size
positions, approve risk, create order intents, call exchanges, or execute
trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from abtp.ai.regime import MarketRegimeLabel
from abtp.data import normalize_timestamp
from abtp.domain import Signal, SignalDirection
from abtp.strategies.base import (
    StrategyConfig,
    StrategyContext,
    StrategyEvaluation,
    StrategySignalPlan,
)

MIN_RISK_SPOT_STRATEGY_NAME = "min_risk_spot_v1"
MIN_RISK_SPOT_STRATEGY_VERSION = "stage-021.v1"


@dataclass(frozen=True, slots=True)
class MinRiskSpotRuntimeState:
    """Fixture-driven runtime constraints until portfolio modules exist."""

    open_base_position: Decimal = Decimal("0")
    last_loss_at: datetime | None = None
    cooldown_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.open_base_position < Decimal("0"):
            raise ValueError("open_base_position cannot be negative")
        if self.last_loss_at is not None:
            object.__setattr__(self, "last_loss_at", normalize_timestamp(self.last_loss_at))
        if self.cooldown_until is not None:
            object.__setattr__(self, "cooldown_until", normalize_timestamp(self.cooldown_until))


@dataclass(frozen=True, slots=True)
class MinRiskSpotStrategyConfig(StrategyConfig):
    """Conservative BTC spot strategy thresholds."""

    allowed_base_asset: str = "BTC"
    min_trend_return_3: Decimal = Decimal("0.010")
    min_rsi: Decimal = Decimal("52")
    max_rsi: Decimal = Decimal("68")
    min_volume_ratio: Decimal = Decimal("0.90")
    max_spread_bps: Decimal = Decimal("50")
    max_atr_pct: Decimal = Decimal("0.040")
    atr_stop_multiplier: Decimal = Decimal("2")
    reward_risk_ratio: Decimal = Decimal("2")
    min_prediction_confidence: Decimal = Decimal("0.35")
    min_probability_up: Decimal = Decimal("0.55")
    cooldown_after_loss: timedelta = timedelta(hours=6)

    def __post_init__(self) -> None:
        StrategyConfig.__post_init__(self)
        if self.allowed_base_asset.upper() != "BTC":
            raise ValueError("Stage 021 only supports BTC spot")
        for value, field_name in (
            (self.min_trend_return_3, "min_trend_return_3"),
            (self.min_volume_ratio, "min_volume_ratio"),
            (self.max_spread_bps, "max_spread_bps"),
            (self.max_atr_pct, "max_atr_pct"),
            (self.atr_stop_multiplier, "atr_stop_multiplier"),
            (self.reward_risk_ratio, "reward_risk_ratio"),
            (self.min_prediction_confidence, "min_prediction_confidence"),
            (self.min_probability_up, "min_probability_up"),
        ):
            if value <= Decimal("0"):
                raise ValueError(f"{field_name} must be positive")
        if self.min_rsi < Decimal("0") or self.max_rsi > Decimal("100"):
            raise ValueError("RSI bounds must be within 0-100")
        if self.min_rsi >= self.max_rsi:
            raise ValueError("min_rsi must be below max_rsi")
        if self.reward_risk_ratio < Decimal("1"):
            raise ValueError("reward_risk_ratio must be at least 1")
        if self.cooldown_after_loss <= timedelta(0):
            raise ValueError("cooldown_after_loss must be positive")


class MinRiskSpotStrategyV1:
    """Conservative long-only BTC spot strategy focused on capital preservation."""

    def __init__(
        self,
        config: MinRiskSpotStrategyConfig | None = None,
        *,
        runtime_state: MinRiskSpotRuntimeState | None = None,
    ) -> None:
        self._config = config or default_min_risk_spot_config()
        self._runtime_state = runtime_state or MinRiskSpotRuntimeState()

    @property
    def config(self) -> MinRiskSpotStrategyConfig:
        return self._config

    @property
    def runtime_state(self) -> MinRiskSpotRuntimeState:
        return self._runtime_state

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        reasons = _rejection_reasons(
            config=self.config,
            state=self.runtime_state,
            context=context,
        )
        if reasons:
            return _hold_evaluation(self.config, context, reasons)

        close = context.features.values["market.close"]
        atr_pct = context.features.values["indicator.atr.atr_pct"]
        stop = close - (close * atr_pct * self.config.atr_stop_multiplier)
        target = close + ((close - stop) * self.config.reward_risk_ratio)
        if stop <= Decimal("0"):
            return _hold_evaluation(
                self.config,
                context,
                ("required stop-loss suggestion is invalid",),
            )
        if (target - close) / (close - stop) < self.config.reward_risk_ratio:
            return _hold_evaluation(
                self.config,
                context,
                ("minimum reward-to-risk threshold is not met",),
            )
        return _buy_evaluation(
            config=self.config,
            context=context,
            stop=stop,
            target=target,
            reasons=(
                "BTC spot trend, momentum, volume, spread, regime, and optional AI checks passed",
            ),
        )


def default_min_risk_spot_config() -> MinRiskSpotStrategyConfig:
    """Return the default Stage 021 strategy configuration."""

    return MinRiskSpotStrategyConfig(
        name=MIN_RISK_SPOT_STRATEGY_NAME,
        version=MIN_RISK_SPOT_STRATEGY_VERSION,
        enabled=True,
        supported_timeframes=("15m", "1h", "4h", "1d"),
        description="conservative long-only BTC spot strategy",
    )


def _rejection_reasons(
    *,
    config: MinRiskSpotStrategyConfig,
    state: MinRiskSpotRuntimeState,
    context: StrategyContext,
) -> tuple[str, ...]:
    reasons: list[str] = []
    values = context.features.values
    if not config.enabled:
        reasons.append("strategy is disabled")
    if context.timeframe not in config.supported_timeframes:
        reasons.append("timeframe is not supported")
    if context.features.pair.base.symbol != config.allowed_base_asset:
        reasons.append("only BTC spot base asset is supported")
    if not context.features.quality.is_trusted:
        reasons.append("feature snapshot quality is not trusted")
    if state.open_base_position > Decimal("0"):
        reasons.append("existing BTC position blocks averaging down")
    if _cooldown_active(config, state, context.generated_at):
        reasons.append("loss cooldown is active")
    if context.regime is None:
        reasons.append("regime context is required")
    elif context.regime.label not in {
        MarketRegimeLabel.TREND_UP,
        MarketRegimeLabel.RANGE_BOUND,
    }:
        reasons.append("regime is not acceptable for new long entries")
    elif context.regime.risk_adjustment.block_new_entries:
        reasons.append("regime risk context blocks new entries")
    if values.get("market.return_3", Decimal("0")) < config.min_trend_return_3:
        reasons.append("trend confirmation is below threshold")
    rsi = values.get("indicator.rsi.rsi")
    if rsi is None or not config.min_rsi <= rsi <= config.max_rsi:
        reasons.append("RSI momentum filter is not in conservative range")
    if values.get("market.volume_ratio", Decimal("0")) < config.min_volume_ratio:
        reasons.append("volume confirmation is below threshold")
    if values.get("liquidity.spread_bps", Decimal("999999")) > config.max_spread_bps:
        reasons.append("spread exceeds ceiling")
    atr_pct = values.get("indicator.atr.atr_pct")
    if atr_pct is None or atr_pct <= Decimal("0"):
        reasons.append("ATR stop distance is required")
    elif atr_pct > config.max_atr_pct:
        reasons.append("ATR volatility exceeds conservative limit")
    if context.prediction is not None:
        if not context.prediction.actionable:
            reasons.append("AI prediction is not actionable")
        if context.prediction.confidence < config.min_prediction_confidence:
            reasons.append("AI confidence is below optional confirmation threshold")
        if context.prediction.probability_up < config.min_probability_up:
            reasons.append("AI upward probability is below optional confirmation threshold")
    return tuple(dict.fromkeys(reasons))


def _cooldown_active(
    config: MinRiskSpotStrategyConfig,
    state: MinRiskSpotRuntimeState,
    generated_at: datetime,
) -> bool:
    checked_at = normalize_timestamp(generated_at)
    if state.cooldown_until is not None and checked_at < state.cooldown_until:
        return True
    if state.last_loss_at is None:
        return False
    return checked_at < state.last_loss_at + config.cooldown_after_loss


def _hold_evaluation(
    config: MinRiskSpotStrategyConfig,
    context: StrategyContext,
    reasons: tuple[str, ...],
) -> StrategyEvaluation:
    reason = reasons[0]
    return StrategyEvaluation(
        strategy_name=config.name,
        strategy_version=config.version,
        enabled=config.enabled,
        signal=Signal(
            source=f"{config.name}:{config.version}",
            pair=context.features.pair,
            generated_at=context.generated_at,
            direction=SignalDirection.HOLD,
            confidence=Decimal("0"),
            inputs_ref=context.feature_snapshot_ref,
            rationale=reason,
            prediction_ref=_prediction_ref(context),
        ),
        plan=StrategySignalPlan(
            entry_reason=reason,
            timeframe=context.timeframe,
            feature_snapshot_ref=context.feature_snapshot_ref,
            regime_label=context.regime.label.value if context.regime is not None else None,
            prediction_ref=_prediction_ref(context),
        ),
        reasons=reasons,
        generated_at=context.generated_at,
    )


def _buy_evaluation(
    *,
    config: MinRiskSpotStrategyConfig,
    context: StrategyContext,
    stop: Decimal,
    target: Decimal,
    reasons: tuple[str, ...],
) -> StrategyEvaluation:
    prediction_confidence = (
        context.prediction.confidence if context.prediction is not None else Decimal("0.50")
    )
    return StrategyEvaluation(
        strategy_name=config.name,
        strategy_version=config.version,
        enabled=config.enabled,
        signal=Signal(
            source=f"{config.name}:{config.version}",
            pair=context.features.pair,
            generated_at=context.generated_at,
            direction=SignalDirection.BUY,
            confidence=prediction_confidence,
            inputs_ref=context.feature_snapshot_ref,
            rationale=reasons[0],
            prediction_ref=_prediction_ref(context),
        ),
        plan=StrategySignalPlan(
            entry_reason=reasons[0],
            timeframe=context.timeframe,
            feature_snapshot_ref=context.feature_snapshot_ref,
            stop_suggestion=stop,
            target_suggestion=target,
            regime_label=context.regime.label.value if context.regime is not None else None,
            prediction_ref=_prediction_ref(context),
        ),
        reasons=reasons,
        generated_at=context.generated_at,
    )


def _prediction_ref(context: StrategyContext) -> str | None:
    if context.prediction is None:
        return None
    return context.prediction.prediction_ref or context.prediction.prediction.features_ref
