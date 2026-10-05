"""Supervised live trading gateway with fail-closed controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from sqlite3 import Error as SQLiteError

from abtp.data import normalize_timestamp
from abtp.domain import OrderIntent, OrderStatus
from abtp.exchanges import ExchangeAdapter, ExchangeMode, ExchangeOrder
from abtp.live.approval import LiveApprovalPolicy, LiveApprovalToken, validate_live_approval
from abtp.live.preflight import (
    LiveMarketPreflight,
    LivePreflightConfig,
    LivePreflightResult,
    run_live_preflight,
)
from abtp.live.submissions import LiveSubmissionConflict, LiveSubmissionLedger


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
        submission_ledger: LiveSubmissionLedger | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config or SupervisedLiveGatewayConfig()
        self._ledger = submission_ledger
        self._clock = clock or (lambda: datetime.now(UTC))
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
        if self._ledger is None:
            return self._record_rejection(
                "persistent submission ledger is required", preflight=None
            )
        now = normalize_timestamp(self._clock())
        age = now - normalize_timestamp(submitted_at)
        if (
            age > self._config.preflight_config.max_market_age
            or age < -self._config.preflight_config.max_clock_skew
        ):
            return self._record_rejection(
                "submission timestamp is stale or in the future", preflight=None
            )
        preflight, reason = self._validate(intent, approval, market, now=now)
        if reason:
            return self._record_rejection(reason, preflight=preflight)
        try:
            self._ledger.reserve(
                intent,
                approval_id=approval.approval_id if approval is not None else None,
                exchange_name=self._adapter.name,
                reserved_at=now,
            )
        except LiveSubmissionConflict as exc:
            return self._record_rejection(str(exc), preflight=preflight)
        except (SQLiteError, OSError, ValueError):
            return self._record_rejection(
                "submission ledger unavailable; no order sent", preflight=preflight
            )
        # Waiting for durable storage must not let a stale preview or approval through.
        preflight, reason = self._validate(intent, approval, market, now=self._clock())
        if reason:
            try:
                self._ledger.record_outcome(
                    intent.id,
                    exchange_order_id=None,
                    outcome="not_submitted",
                    completed_at=self._clock(),
                )
            except (SQLiteError, OSError, ValueError):
                reason += "; submission ledger unavailable; reconciliation required"
            return self._record_rejection(reason, preflight=preflight)
        try:
            exchange_order = self._adapter.submit_order(intent)
        except Exception:
            # The exchange may have accepted the order before the connection failed.
            return self._record_rejection(
                "exchange submission outcome unknown; reconciliation required; do not retry",
                preflight=preflight,
            )
        if exchange_order.intent.id != intent.id or not exchange_order.exchange_order_id:
            return self._record_rejection(
                "exchange response mismatch; reconciliation required", preflight=preflight
            )
        try:
            self._ledger.record_outcome(
                intent.id,
                exchange_order_id=exchange_order.exchange_order_id,
                outcome=exchange_order.status.value,
                completed_at=self._clock(),
            )
        except (SQLiteError, OSError, ValueError):
            return self._record_rejection(
                "exchange submission attempted but result could not be persisted; "
                "reconciliation required",
                preflight=preflight,
            )
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

    def _validate(
        self,
        intent: OrderIntent,
        approval: LiveApprovalToken | None,
        market: LiveMarketPreflight,
        *,
        now: datetime,
    ) -> tuple[LivePreflightResult, str]:
        preflight = run_live_preflight(
            intent, market, config=self._config.preflight_config, now=now
        )
        reasons = list(preflight.reasons)
        if self._ledger is not None:
            try:
                if self._ledger.halt_reason():
                    reasons.append("execution is halted; operator review is required")
            except (SQLiteError, OSError, ValueError):
                reasons.append("submission ledger unavailable; no order sent")
        if self._config.manual_approval_required or approval is not None:
            reasons.extend(
                validate_live_approval(
                    intent,
                    approval,
                    now=now,
                    estimated_notional=preflight.preview.estimated_notional,
                    policy=self._config.approval_policy,
                ).reasons
            )
        return preflight, "; ".join(reasons)

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
