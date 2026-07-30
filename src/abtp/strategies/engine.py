"""Pluggable strategy registry and evaluation engine."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from abtp.domain import AuditEvent, AuditEventType, Signal, SignalDirection
from abtp.repositories import AuditRepository, IntelligenceRepository
from abtp.strategies.base import (
    StrategyConfig,
    StrategyContext,
    StrategyEvaluation,
    StrategyPlugin,
    StrategySignalPlan,
)


@dataclass(frozen=True, slots=True)
class StrategyEngineConfig:
    """Persistence and evaluation behavior for the strategy engine."""

    persist_signals: bool = True
    audit_signals: bool = True
    include_disabled: bool = False


class StrategyRegistry:
    """In-memory plugin registry keyed by strategy name."""

    def __init__(self) -> None:
        self._strategies: dict[str, StrategyPlugin] = {}
        self._enabled_overrides: dict[str, bool] = {}

    def register(self, strategy: StrategyPlugin) -> None:
        name = strategy.config.name
        if name in self._strategies:
            raise ValueError(f"strategy already registered: {name}")
        self._strategies[name] = strategy

    def get(self, name: str) -> StrategyPlugin:
        try:
            return self._strategies[name]
        except KeyError as exc:
            raise KeyError(f"unknown strategy: {name}") from exc

    def enable(self, name: str) -> None:
        self.get(name)
        self._enabled_overrides[name] = True

    def disable(self, name: str) -> None:
        self.get(name)
        self._enabled_overrides[name] = False

    def is_enabled(self, name: str) -> bool:
        strategy = self.get(name)
        return self._enabled_overrides.get(name, strategy.config.enabled)

    def list(self) -> tuple[StrategyPlugin, ...]:
        return tuple(self._strategies[name] for name in sorted(self._strategies))

    def enabled(self) -> tuple[StrategyPlugin, ...]:
        return tuple(strategy for strategy in self.list() if self.is_enabled(strategy.config.name))


class StrategyEngine:
    """Evaluate registered strategies without creating orders or risk decisions."""

    def __init__(
        self,
        registry: StrategyRegistry,
        *,
        config: StrategyEngineConfig | None = None,
        intelligence_repository: IntelligenceRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or StrategyEngineConfig()
        self._intelligence_repository = intelligence_repository
        self._audit_repository = audit_repository

    def evaluate_all(self, context: StrategyContext) -> tuple[StrategyEvaluation, ...]:
        """Evaluate registered strategies in stable name order."""

        strategies = (
            self._registry.list() if self._config.include_disabled else self._registry.enabled()
        )
        return tuple(self.evaluate(strategy.config.name, context) for strategy in strategies)

    def evaluate(self, strategy_name: str, context: StrategyContext) -> StrategyEvaluation:
        """Evaluate a named strategy and optionally persist/audit its signal."""

        strategy = self._registry.get(strategy_name)
        if not self._registry.is_enabled(strategy_name):
            strategy = _disabled_strategy(strategy)
        evaluation = strategy.evaluate(context)
        signal_ref = self._persist_signal(evaluation)
        audit_event_id = self._append_audit(evaluation, signal_ref=signal_ref)
        return evaluation.with_persistence(signal_ref=signal_ref, audit_event_id=audit_event_id)

    def _persist_signal(self, evaluation: StrategyEvaluation) -> str | None:
        if not self._config.persist_signals or self._intelligence_repository is None:
            return None
        return self._intelligence_repository.add_signal(evaluation.signal)

    def _append_audit(
        self,
        evaluation: StrategyEvaluation,
        *,
        signal_ref: str | None,
    ) -> str | None:
        if not self._config.audit_signals or self._audit_repository is None:
            return None
        payload = dict(evaluation.audit_payload())
        payload["signal_ref"] = signal_ref or "not_persisted"
        event = AuditEvent(
            event_type=AuditEventType.SIGNAL,
            occurred_at=evaluation.generated_at,
            payload=payload,
        )
        return self._audit_repository.append(event)


def build_registry(strategies: Iterable[StrategyPlugin]) -> StrategyRegistry:
    """Build a registry from a deterministic strategy iterable."""

    registry = StrategyRegistry()
    for strategy in strategies:
        registry.register(strategy)
    return registry


class _DisabledStrategy:
    def __init__(self, strategy: StrategyPlugin) -> None:
        self._strategy = strategy

    @property
    def config(self) -> StrategyConfig:
        return self._strategy.config

    def evaluate(self, context: StrategyContext) -> StrategyEvaluation:
        config = self._strategy.config
        return StrategyEvaluation(
            strategy_name=config.name,
            strategy_version=config.version,
            enabled=False,
            signal=Signal(
                source=f"{config.name}:{config.version}",
                pair=context.features.pair,
                generated_at=context.generated_at,
                direction=SignalDirection.HOLD,
                confidence=Decimal("0"),
                inputs_ref=context.feature_snapshot_ref,
                rationale="strategy is disabled",
                prediction_ref=(
                    context.prediction.prediction_ref if context.prediction is not None else None
                ),
            ),
            plan=StrategySignalPlan(
                entry_reason="strategy is disabled",
                timeframe=context.timeframe,
                feature_snapshot_ref=context.feature_snapshot_ref,
                regime_label=context.regime.label.value if context.regime is not None else None,
                prediction_ref=(
                    context.prediction.prediction_ref if context.prediction is not None else None
                ),
            ),
            reasons=("strategy is disabled",),
            generated_at=context.generated_at,
        )


def _disabled_strategy(strategy: StrategyPlugin) -> StrategyPlugin:
    return cast(StrategyPlugin, _DisabledStrategy(strategy))


def strategy_names(registry: StrategyRegistry) -> tuple[str, ...]:
    """Return stable registered strategy names."""

    return tuple(strategy.config.name for strategy in registry.list())
