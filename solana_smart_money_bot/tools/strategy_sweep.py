from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class SweepResult:
    label: str
    days: int
    wallet_source: str
    profile: str
    trade_picker: str
    allow_proxy_exit: bool
    trades: int
    win_rate: float
    gross_pnl: float
    net_pnl: float
    final_capital: float
    raw_output: str


_TRADES_RE = re.compile(r"Trades:\s*(\d+)")
_WIN_RATE_RE = re.compile(r"Win rate:\s*([0-9.]+)%")
_GROSS_RE = re.compile(r"Gross PnL:\s*₹(-?[0-9.,]+)")
_NET_RE = re.compile(r"Net PnL:\s*₹(-?[0-9.,]+)")
_FINAL_RE = re.compile(r"Final capital:\s*₹(-?[0-9.,]+)")


def _parse_metric(regex: re.Pattern[str], text: str, default: float = 0.0) -> float:
    match = regex.search(text)
    if not match:
        return default
    return float(match.group(1).replace(",", ""))


def _run_backtest(days: int, wallet_source: str, profile: str, trade_picker: str, allow_proxy_exit: bool) -> SweepResult:
    env = os.environ.copy()
    env.update(
        {
            "BACKTEST_DAYS": str(days),
            "BACKTEST_WALLET_SOURCE": wallet_source,
            "BACKTEST_USE_CACHE": "true",
            "BT_SIMULATION_PROFILE": profile,
            "BT_TRADE_PICKER": trade_picker,
            "BT_ALLOW_PROXY_EXIT": "true" if allow_proxy_exit else "false",
        }
    )
    proc = subprocess.run(
        [sys.executable, "backtest_7d.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    trades = int(_parse_metric(_TRADES_RE, output, 0))
    win_rate = _parse_metric(_WIN_RATE_RE, output, 0.0)
    gross_pnl = _parse_metric(_GROSS_RE, output, 0.0)
    net_pnl = _parse_metric(_NET_RE, output, 0.0)
    final_capital = _parse_metric(_FINAL_RE, output, 0.0)
    return SweepResult(
        label=f"{days}d/{wallet_source}/{profile}/{trade_picker}/proxy={'on' if allow_proxy_exit else 'off'}",
        days=days,
        wallet_source=wallet_source,
        profile=profile,
        trade_picker=trade_picker,
        allow_proxy_exit=allow_proxy_exit,
        trades=trades,
        win_rate=win_rate,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        final_capital=final_capital,
        raw_output=output,
    )


def main() -> int:
    sweeps: list[tuple[int, str, str]] = [
        (30, "db_active", "balanced"),
        (30, "db_active", "aggressive"),
        (90, "db_active", "balanced"),
        (90, "db_active", "aggressive"),
        (90, "combined", "balanced"),
        (90, "combined", "aggressive"),
    ]
    trade_pickers = ["first", "best_quality"]
    proxy_modes = [False, True]
    results = [
        _run_backtest(days, source, profile, trade_picker, allow_proxy_exit)
        for days, source, profile in sweeps
        for trade_picker in trade_pickers
        for allow_proxy_exit in proxy_modes
    ]
    best = max(results, key=lambda r: r.net_pnl)

    print("=== STRATEGY SWEEP SUMMARY ===")
    for r in results:
        print(
            f"{r.label} trades={r.trades} win_rate={r.win_rate:.2f}% "
            f"net=₹{r.net_pnl:.2f} gross=₹{r.gross_pnl:.2f} final=₹{r.final_capital:.2f}"
        )
    print(f"BEST={best.label} net=₹{best.net_pnl:.2f} trades={best.trades} win_rate={best.win_rate:.2f}%")

    report_lines = [
        "# Strategy Sweep Report",
        "",
        f"Generated from: `{Path(__file__).resolve()}`",
        "",
        "## Results",
        "",
    ]
    for r in results:
        report_lines.append(
            f"- `{r.label}`: trades={r.trades}, win_rate={r.win_rate:.2f}%, net=₹{r.net_pnl:.2f}, gross=₹{r.gross_pnl:.2f}, final=₹{r.final_capital:.2f}"
        )
    report_lines.extend(
        [
            "",
            "## Best",
            "",
            f"- `{best.label}`",
            f"- net=₹{best.net_pnl:.2f}",
            f"- trades={best.trades}",
            f"- win_rate={best.win_rate:.2f}%",
        ]
    )
    (ROOT / "STRATEGY_SWEEP_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
