"""Paper runner session configuration for Stage 072."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from abtp.config import TradingMode


@dataclass(frozen=True, slots=True)
class PaperTradingSessionConfig:
    """Fail-closed session-level paper runner controls."""

    session_id: str
    trading_mode: TradingMode = TradingMode.PAPER
    safe_mode: bool = True
    paper_starting_equity: Decimal = Decimal("10000")
    require_command_buy_review: bool = True
    require_stop_loss: bool = True
    require_risk_approval: bool = True
    allow_live_credentials: bool = False
    source_refs: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id is required")
        object.__setattr__(self, "trading_mode", TradingMode(self.trading_mode))
        if self.paper_starting_equity <= Decimal("0"):
            raise ValueError("paper_starting_equity must be positive")
        object.__setattr__(self, "source_refs", dict(self.source_refs))

    @property
    def paper_mode_only(self) -> bool:
        return (
            self.trading_mode is TradingMode.PAPER
            and self.safe_mode
            and not self.allow_live_credentials
        )

    def fail_closed_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.trading_mode is not TradingMode.PAPER:
            reasons.append("paper runner requires paper trading mode")
        if not self.safe_mode:
            reasons.append("paper runner requires safe mode")
        if self.allow_live_credentials:
            reasons.append("paper runner forbids live credentials")
        return tuple(reasons)
