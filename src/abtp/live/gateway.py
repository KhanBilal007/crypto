"""Supervised live trading gateway with fail-closed controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from abtp.domain import OrderIntent, OrderStatus
from abtp.exchanges import ExchangeAdapter, ExchangeAdapterError, ExchangeMode, ExchangeOrder
from abtp.live.approval import LiveApprovalPolicy, LiveApprovalToken, validate_live_approval
from abtp.live.preflight import (
    LiveMarketPreflight,
    LivePreflightConfig,
    LivePreflightResult,
    run_live_preflight,
)


@dataclass(frozen=True, slots=True)
class SupervisedLiveGatewayConfig:
    """Explicit live gateway lock configuration."""

    enable_supervised_live: bool = False
    runtime_live_execution_supported: bool = False
    manual_approval_required: bool = True
    approval_policy: LiveApprovalPolicy = LiveApprovalPolicy()
    preflight_config: LivePreflightConfig = LivePreflightConfig()


@dataclass(frozen=True, slots=True)
class LiveGatewaySubmissionResult:
    """Result of one supervised live submission attempt."""

    accepted: bool
    status: OrderStatus | None
    exchange_order: ExchangeOrder | None
    preflight: LivePreflightResult | None
    trading_permitted: bool
    reason: str


class SupervisedLiveTradingGateway:
    """Submit live orders only after approval, preflight, and risk checks."""

    def __init__(
        self,
        *,
        adapter: ExchangeAdapter,
        config: SupervisedLiveGatewayConfig | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config or SupervisedLiveGatewayConfig()
        self._submissions: list[LiveGatewaySubmissionResult] = []

    @property
    def submissions(self) -> tuple[LiveGatewaySubmissionResult, ...]:
        return tuple(self._submissions)

    def submit(
        self,
        intent: OrderIntent,
        *,
        approval: LiveApprovalToken | None,
        market: LiveMarketPreflight,
        submitted_at: datetime,
    ) -> LiveGatewaySubmissionResult:
        """Attempt a supervised live submission through the adapter contract only."""

        lock_reason = self._lock_reason()
        if lock_reason is not None:
            return self._record_rejection(lock_reason, preflight=None)
        preflight = run_live_preflight(
            intent,
            market,
            config=self._config.preflight_config,
        )
        if not preflight.allowed:
            return self._record_rejection("; ".join(preflight.reasons), preflight=preflight)
        if self._config.manual_approval_required:
            approval_check = validate_live_approval(
                intent,
                approval,
                now=submitted_at,
                estimated_notional=preflight.preview.estimated_notional,
                policy=self._config.approval_policy,
            )
            if not approval_check.allowed:
                return self._record_rejection(
                    "; ".join(approval_check.reasons), preflight=preflight
                )
        try:
            exchange_order = self._adapter.submit_order(intent)
        except ExchangeAdapterError as exc:
            return self._record_rejection(str(exc), preflight=preflight)
        result = LiveGatewaySubmissionResult(
            accepted=exchange_order.status in {OrderStatus.SUBMITTED, OrderStatus.FILLED},
            status=exchange_order.status,
            exchange_order=exchange_order,
            preflight=preflight,
            trading_permitted=True,
            reason="supervised live order submitted through adapter",
        )
        self._submissions.append(result)
        return result

    def _lock_reason(self) -> str | None:
        if self._adapter.mode is not ExchangeMode.LIVE:
            return "live gateway requires a live-mode adapter"
        if not self._config.enable_supervised_live:
            return "supervised live gateway is disabled"
        if not self._config.runtime_live_execution_supported:
            return "runtime live execution support is disabled"
        return None

    def _record_rejection(
        self,
        reason: str,
        *,
        preflight: LivePreflightResult | None,
    ) -> LiveGatewaySubmissionResult:
        result = LiveGatewaySubmissionResult(
            accepted=False,
            status=None,
            exchange_order=None,
            preflight=preflight,
            trading_permitted=False,
            reason=reason,
        )
        self._submissions.append(result)
        return result
