"""Swing-oriented paper strategies for 1-2 month shadow testing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from abtp.ai.regime import MarketRegimeLabel
from abtp.domain import Signal, SignalDirection
from abtp.strategies.base import (
    StrategyConfig,
    StrategyContext,
    StrategyEvaluation,
    StrategySignalPlan,
)

SWING_STRATEGY_VERSION = "stage-072.v1"


@dataclass(frozen=True, slots=True)
class SwingStrategyConfig(StrategyConfig):
    """Shared risk and signal thresholds for BTC spot swing strategies."""

    min_volume_ratio: Decimal = Decimal("1.0")
    max_spread_bps: Decimal = Decimal("25")
    atr_stop_multiplier: Decimal = Decimal("2")
    reward_risk_ratio: Decimal = Decimal("2")
    sell_confidence: Decimal = Decimal("0.55")
    buy_confidence: Decimal = Decimal("0.60")

    def __post_init__(self) -> None:
        StrategyConfig.__post_init__(self)
        for value, field_name in (
            (self.min_volume_ratio, "min_volume_ratio"),
            (self.max_spread_bps, "max_spread_bps"),
            (self.atr_stop_multiplier, "atr_stop_multiplier"),
            (self.reward_risk_ratio, "reward_risk_ratio"),
            (self.sell_confidence, "sell_confidence"),
            (self.buy_confidence, "buy_confidence"),
        ):
            if value <= Decimal("0"):
                raise ValueError(f"{field_name} must be positive")
        if self.sell_confidence > Decimal("1") or self.buy_confidence > Decimal("1"):
            raise ValueError("confidence thresholds must be at most 1")


class TrendPullbackStrategy:
    """Buy pullbacks inside an uptrend; sell when trend confirmation breaks."""

    def __init__(self, config: SwingStrategyConfig | None = None) -> None:
        self._config = config or SwingStrategyConfig(
            name="trend_pullback_v1",
            version=SWING_STRATEGY_VERSION,
            supported_timeframes=("1h", "4h", "1d"),
            description="1-2 month swing strategy: uptrend pullback entries with ATR exits",
        )

    @property
    def config(self) -> SwingStrategyConfig:
        return self._config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        common = _common_rejections(self.config, context)
        if common:
            return _evaluation(self.config, context, SignalDirection.HOLD, Decimal("0"), common)
        values = context.features.values
        close = values["market.close"]
        ema_9 = values.get("indicator.ema_9")
        ema_21 = values.get("indicator.ema_21")
        rsi = values.get("indicator.rsi.rsi", Decimal("50"))
        pullback_pct = values.get("market.pullback_from_high_pct", Decimal("0"))
        exposure = values.get("portfolio.exposure_base", Decimal("0"))
        if exposure > Decimal("0") and (ema_9 is None or ema_21 is None or close < ema_21):
            return _evaluation(
                self.config,
                context,
                SignalDirection.SELL,
                self.config.sell_confidence,
                ("trend confirmation broke below EMA 21",),
            )
        if not (ema_9 is not None and ema_21 is not None and close > ema_21 and ema_9 > ema_21):
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("EMA trend stack is not bullish",),
            )
        if not Decimal("0.006") <= pullback_pct <= Decimal("0.055"):
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("pullback is not in the planned swing-entry zone",),
            )
        if not Decimal("42") <= rsi <= Decimal("62"):
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("RSI is not in pullback recovery range",),
            )
        return _buy_with_atr(
            self.config,
            context,
            ("uptrend pullback, RSI recovery, volume, spread, and risk inputs passed",),
        )


class BreakoutStrategy:
    """Buy confirmed resistance breakouts; sell failed breakouts."""

    def __init__(self, config: SwingStrategyConfig | None = None) -> None:
        self._config = config or SwingStrategyConfig(
            name="breakout_v1",
            version=SWING_STRATEGY_VERSION,
            supported_timeframes=("1h", "4h", "1d"),
            description="1-2 month swing strategy: resistance breakout with volume confirmation",
            min_volume_ratio=Decimal("1.20"),
        )

    @property
    def config(self) -> SwingStrategyConfig:
        return self._config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        common = _common_rejections(self.config, context)
        if common:
            return _evaluation(self.config, context, SignalDirection.HOLD, Decimal("0"), common)
        values = context.features.values
        close = values["market.close"]
        resistance = values.get("market.resistance_20")
        support = values.get("market.support_20")
        exposure = values.get("portfolio.exposure_base", Decimal("0"))
        if exposure > Decimal("0") and support is not None and close < support:
            return _evaluation(
                self.config,
                context,
                SignalDirection.SELL,
                self.config.sell_confidence,
                ("breakout failed below support",),
            )
        if resistance is None or close <= resistance * Decimal("1.001"):
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("price has not broken resistance with confirmation",),
            )
        if values.get("market.volume_ratio", Decimal("0")) < self.config.min_volume_ratio:
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("breakout volume confirmation is below threshold",),
            )
        return _buy_with_atr(
            self.config,
            context,
            ("resistance breakout with volume, spread, and risk inputs passed",),
        )


class SupportResistanceReboundStrategy:
    """Buy support rebounds in range markets; sell near resistance or support failure."""

    def __init__(self, config: SwingStrategyConfig | None = None) -> None:
        self._config = config or SwingStrategyConfig(
            name="support_resistance_rebound_v1",
            version=SWING_STRATEGY_VERSION,
            supported_timeframes=("1h", "4h", "1d"),
            description="1-2 month swing strategy: range support rebound and resistance exits",
            min_volume_ratio=Decimal("0.85"),
        )

    @property
    def config(self) -> SwingStrategyConfig:
        return self._config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        common = _common_rejections(self.config, context)
        if common:
            return _evaluation(self.config, context, SignalDirection.HOLD, Decimal("0"), common)
        values = context.features.values
        close = values["market.close"]
        support = values.get("market.support_20")
        resistance = values.get("market.resistance_20")
        rsi = values.get("indicator.rsi.rsi", Decimal("50"))
        exposure = values.get("portfolio.exposure_base", Decimal("0"))
        if support is None or resistance is None or resistance <= support:
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("support and resistance levels are not ready",),
            )
        near_support = close <= support * Decimal("1.015")
        near_resistance = close >= resistance * Decimal("0.985")
        if exposure > Decimal("0") and (near_resistance or close < support * Decimal("0.99")):
            return _evaluation(
                self.config,
                context,
                SignalDirection.SELL,
                self.config.sell_confidence,
                ("range exit: resistance reached or support failed",),
            )
        if not near_support:
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("price is not close enough to support",),
            )
        if not Decimal("35") <= rsi <= Decimal("55"):
            return _evaluation(
                self.config,
                context,
                SignalDirection.HOLD,
                Decimal("0"),
                ("RSI is not in support rebound range",),
            )
        return _buy_with_atr(
            self.config,
            context,
            ("support rebound with range, RSI, volume, spread, and risk inputs passed",),
        )


def _common_rejections(
    config: SwingStrategyConfig,
    context: StrategyContext,
) -> tuple[str, ...]:
    values = context.features.values
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("strategy is disabled")
    if context.timeframe not in config.supported_timeframes:
        reasons.append("timeframe is not supported")
    if context.features.pair.base.symbol != "BTC":
        reasons.append("only BTC spot base asset is supported")
    if not context.features.quality.is_trusted:
        reasons.append("feature snapshot quality is not trusted")
    if values.get("liquidity.spread_bps", Decimal("999999")) > config.max_spread_bps:
        reasons.append("spread exceeds ceiling")
    if values.get("market.volume_ratio", Decimal("0")) < config.min_volume_ratio:
        reasons.append("volume confirmation is below threshold")
    if values.get("indicator.atr.atr_pct", Decimal("0")) <= Decimal("0"):
        reasons.append("ATR stop distance is required")
    if context.regime is not None and context.regime.label is MarketRegimeLabel.TREND_DOWN:
        reasons.append("downtrend regime blocks long swing entries")
    return tuple(dict.fromkeys(reasons))


def _buy_with_atr(
    config: SwingStrategyConfig,
    context: StrategyContext,
    reasons: tuple[str, ...],
) -> StrategyEvaluation:
    close = context.features.values["market.close"]
    atr_pct = context.features.values["indicator.atr.atr_pct"]
    stop = close - close * atr_pct * config.atr_stop_multiplier
    target = close + (close - stop) * config.reward_risk_ratio
    if stop <= Decimal("0"):
        return _evaluation(
            config,
            context,
            SignalDirection.HOLD,
            Decimal("0"),
            ("required stop-loss suggestion is invalid",),
        )
    return _evaluation(
        config,
        context,
        SignalDirection.BUY,
        config.buy_confidence,
        reasons,
        stop=stop,
        target=target,
    )


def _evaluation(
    config: SwingStrategyConfig,
    context: StrategyContext,
    direction: SignalDirection,
    confidence: Decimal,
    reasons: tuple[str, ...],
    *,
    stop: Decimal | None = None,
    target: Decimal | None = None,
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
            direction=direction,
            confidence=confidence,
            inputs_ref=context.feature_snapshot_ref,
            rationale=reason,
            prediction_ref=None,
        ),
        plan=StrategySignalPlan(
            entry_reason=reason,
            timeframe=context.timeframe,
            feature_snapshot_ref=context.feature_snapshot_ref,
            stop_suggestion=stop,
            target_suggestion=target,
            regime_label=context.regime.label.value if context.regime is not None else None,
            prediction_ref=None,
        ),
        reasons=reasons,
        generated_at=context.generated_at,
    )
