"""Dependency-free paper trading dashboard view models."""

from __future__ import annotations

from dataclasses import dataclass

from abtp.api import PaperStatusResponse


@dataclass(frozen=True, slots=True)
class DashboardRow:
    """One dashboard label/value row."""

    label: str
    value: str

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("dashboard row label is required")


@dataclass(frozen=True, slots=True)
class DashboardPanel:
    """Small renderable dashboard panel."""

    title: str
    rows: tuple[DashboardRow, ...]

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("dashboard panel title is required")


@dataclass(frozen=True, slots=True)
class PaperDashboardView:
    """Read-only paper dashboard view."""

    panels: tuple[DashboardPanel, ...]

    def render_text(self) -> str:
        """Render a deterministic plain-text dashboard snapshot for tests and CLI users."""

        lines: list[str] = []
        for panel in self.panels:
            lines.append(f"[{panel.title}]")
            lines.extend(f"{row.label}: {row.value}" for row in panel.rows)
        return "\n".join(lines)


def build_paper_dashboard(status: PaperStatusResponse) -> PaperDashboardView:
    """Build a read-only dashboard from the paper API response."""

    parameter_rows = tuple(
        DashboardRow(item.key, f"{item.status} ({item.value})") for item in status.parameter_health
    )
    return PaperDashboardView(
        panels=(
            DashboardPanel(
                title="Paper State",
                rows=(
                    DashboardRow("BTC price", str(status.current_btc_price or "unavailable")),
                    DashboardRow("Regime", status.active_regime),
                    DashboardRow("Signal", status.latest_signal),
                    DashboardRow("Risk", status.latest_risk_decision),
                    DashboardRow("Blocked", status.blocked_reason),
                    DashboardRow("Data", status.data_health),
                ),
            ),
            DashboardPanel(
                title="Controls",
                rows=(
                    DashboardRow("Paused", str(status.paused)),
                    DashboardRow("Kill switch", str(status.kill_switch_active)),
                ),
            ),
            DashboardPanel(
                title="Portfolio",
                rows=(
                    DashboardRow("Cash", status.portfolio.as_dict()["cash"]),
                    DashboardRow("BTC", status.portfolio.as_dict()["base_quantity"]),
                    DashboardRow("Equity", status.portfolio.as_dict()["equity"]),
                    DashboardRow("Drawdown", status.portfolio.as_dict()["drawdown_pct"]),
                    DashboardRow("Fees", status.portfolio.as_dict()["fees_paid"]),
                    DashboardRow("Trades", str(status.trades_count)),
                ),
            ),
            DashboardPanel(
                title="Parameter Health",
                rows=parameter_rows,
            ),
        )
    )


def render_paper_dashboard(status: PaperStatusResponse) -> str:
    """Render the paper dashboard as deterministic text."""

    return build_paper_dashboard(status).render_text()
