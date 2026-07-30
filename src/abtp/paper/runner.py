"""Deterministic Stage 072 paper trading runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from abtp.paper.cycle import (
    PaperTradingCycleInput,
    PaperTradingRunnerCycleResult,
    blocked_cycle_result,
    cycle_result_from_engine,
    preflight_block_reasons,
)
from abtp.paper.engine import PaperTradingEngine
from abtp.paper.session import PaperTradingSessionConfig
from abtp.paper.summary import PaperTradingSessionSummary, summarize_paper_session

if TYPE_CHECKING:
    from datetime import datetime

    from abtp.observability.metrics import MetricsRegistry


@dataclass(slots=True)
class PaperTradingRunner:
    """Run complete simulated paper cycles through existing safety gates."""

    engine: PaperTradingEngine
    config: PaperTradingSessionConfig
    metrics: MetricsRegistry | None = None

    def run_cycle(self, cycle_input: PaperTradingCycleInput) -> PaperTradingRunnerCycleResult:
        """Run one paper cycle or record why it was skipped."""

        reasons = (*self.config.fail_closed_reasons(), *preflight_block_reasons(cycle_input))
        if reasons:
            result = blocked_cycle_result(
                cycle_input,
                reasons=tuple(dict.fromkeys(reasons)),
                generated_at=cycle_input.snapshot.received_at,
            )
            _record_blocked_metrics(self.metrics, result)
            return result
        engine_cycle = self.engine.on_market_update(cycle_input.snapshot)
        if self.config.require_risk_approval and engine_cycle.executed:
            assert engine_cycle.risk_decision_status == "approved"
        if self.metrics is not None:
            from abtp.observability.metrics import record_paper_cycle_metrics

            record_paper_cycle_metrics(self.metrics, engine_cycle)
        return cycle_result_from_engine(cycle_input, engine_cycle)

    def run_session(
        self,
        cycle_inputs: tuple[PaperTradingCycleInput, ...],
    ) -> PaperTradingSessionSummary:
        """Run a deterministic sequence of paper cycles and summarize it."""

        starting_equity = self.config.paper_starting_equity
        results = tuple(self.run_cycle(cycle_input) for cycle_input in cycle_inputs)
        if results:
            ended_at = results[-1].generated_at
            ending_equity = self.engine.account.equity(results[-1].snapshot.candle.close)
        else:
            ended_at = cycle_inputs[-1].snapshot.received_at if cycle_inputs else _fallback_time()
            ending_equity = starting_equity
        return summarize_paper_session(
            session_id=self.config.session_id,
            cycles=results,
            started_at=cycle_inputs[0].snapshot.received_at if cycle_inputs else ended_at,
            ended_at=ended_at,
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            realized_pnl=self.engine.account.state.realized_pnl,
            total_fees=self.engine.account.state.fees_paid,
        )

    def create_live_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper runner cannot create live orders")

    def submit_order(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper runner cannot submit orders directly")

    def enable_live_trading(self, *_args: object, **_kwargs: object) -> None:
        raise ValueError("paper runner cannot enable live trading")


def run_paper_session(
    *,
    engine: PaperTradingEngine,
    config: PaperTradingSessionConfig,
    cycle_inputs: tuple[PaperTradingCycleInput, ...],
    metrics: MetricsRegistry | None = None,
) -> PaperTradingSessionSummary:
    """Convenience wrapper for one deterministic paper session."""

    runner = PaperTradingRunner(engine=engine, config=config, metrics=metrics)
    return runner.run_session(cycle_inputs)


def _record_blocked_metrics(
    metrics: MetricsRegistry | None,
    result: PaperTradingRunnerCycleResult,
) -> None:
    if metrics is None:
        return
    metrics.counter(
        "abtp_paper_runner_blocked_cycle_count",
        observed_at=result.generated_at,
        labels={
            "component": "paper_runner",
            "reason": result.blocked_reasons[0] if result.blocked_reasons else "unknown",
        },
    )
    metrics.gauge(
        "abtp_paper_runner_snapshot_price",
        value=result.snapshot.candle.close,
        observed_at=result.generated_at,
        labels={"component": "paper_runner", "status": result.status.value},
    )


def _fallback_time() -> datetime:
    from datetime import UTC, datetime

    return datetime(2026, 1, 1, tzinfo=UTC)
