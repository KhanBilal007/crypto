"""Renderable dashboard view for the Stage 071 paper command center."""

from __future__ import annotations

from dataclasses import dataclass

from abtp.paper import PaperCommandRecommendation


@dataclass(frozen=True, slots=True)
class PaperCommandCenterDashboardView:
    """Compact operator-facing paper command view."""

    recommendation: PaperCommandRecommendation

    def render_text(self) -> str:
        """Render deterministic plain text for tests and future UI work."""

        account = self.recommendation.checklist.account
        lines = [
            "[Paper Command Center]",
            f"Action: {self.recommendation.label.value}",
            f"Ready for paper review: {self.recommendation.paper_trade_ready}",
            f"Explanation: {self.recommendation.explanation}",
            f"Confidence: {self.recommendation.confidence_score}",
            f"Support: {self.recommendation.support_score}",
            f"Risk: {self.recommendation.risk_score} ({self.recommendation.risk_level})",
            f"Max paper position: {self.recommendation.max_paper_position_size}",
            f"Stop loss required: {self.recommendation.stop_loss_required}",
            f"Stop loss price: {self.recommendation.checklist.stop_loss_price or 'missing'}",
            f"Holding period: {self.recommendation.holding_period}",
            f"Cash: {account.cash}",
            f"Equity: {account.equity}",
            f"Open paper positions: {account.open_positions}",
            f"Drawdown: {account.drawdown_pct}",
            f"Blocked reasons: {_reasons(self.recommendation.blocked_reasons)}",
            f"Audit ref: {self.recommendation.audit_ref}",
        ]
        return "\n".join(lines)


def build_paper_command_center_dashboard(
    recommendation: PaperCommandRecommendation,
) -> PaperCommandCenterDashboardView:
    """Build a renderable paper command-center dashboard view."""

    return PaperCommandCenterDashboardView(recommendation)


def render_paper_command_center(recommendation: PaperCommandRecommendation) -> str:
    """Render the command center as deterministic text."""

    return build_paper_command_center_dashboard(recommendation).render_text()


def _reasons(reasons: tuple[str, ...]) -> str:
    return "none" if not reasons else "; ".join(reasons)
