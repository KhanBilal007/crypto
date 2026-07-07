from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


@dataclass
class WindowResult:
    offset_days: int
    days: int
    profile: str
    trade_picker: str
    quality_floor: float
    trades: int
    win_rate: float
    net_pnl: float
    final_capital: float
    proxy_exits: int
    proxy_exit_pct: float


_TRADES_RE = re.compile(r"Trades:\s*(\d+)")
_WIN_RATE_RE = re.compile(r"Win rate:\s*([0-9.]+)%")
_NET_RE = re.compile(r"Net PnL:\s*₹(-?[0-9.,]+)")
_FINAL_RE = re.compile(r"Final capital:\s*₹(-?[0-9.,]+)")
_PROXY_RE = re.compile(r"Proxy exits:\s*(\d+)\s+\(([0-9.]+)%\)")


def _metric(regex: re.Pattern[str], text: str, default: float = 0.0) -> float:
    match = regex.search(text)
    if not match:
        return default
    return float(match.group(1).replace(",", ""))


def _run_window(days: int, offset: int, profile: str, trade_picker: str, quality_floor: float, wallet_source: str) -> WindowResult:
    env = os.environ.copy()
    env.update(
        {
            "BACKTEST_DAYS": str(days),
            "BACKTEST_END_DAYS_AGO": str(offset),
            "BACKTEST_WALLET_SOURCE": wallet_source,
            "BACKTEST_USE_CACHE": "true",
            "BT_SIMULATION_PROFILE": profile,
            "BT_TRADE_PICKER": trade_picker,
            "BT_SIGNAL_QUALITY_FLOOR": str(quality_floor),
            "BT_ALLOW_PROXY_EXIT": "false",
            "BT_REQUIRE_REAL_EXIT": "true",
        }
    )
    proc = subprocess.run(
        [sys.executable, "backtest_7d.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    trades = int(_metric(_TRADES_RE, output, 0))
    win_rate = _metric(_WIN_RATE_RE, output, 0.0)
    net_pnl = _metric(_NET_RE, output, 0.0)
    final_capital = _metric(_FINAL_RE, output, 0.0)
    proxy_match = _PROXY_RE.search(output)
    proxy_exits = int(proxy_match.group(1)) if proxy_match else 0
    proxy_pct = float(proxy_match.group(2)) if proxy_match else 0.0
    return WindowResult(
        offset_days=offset,
        days=days,
        profile=profile,
        trade_picker=trade_picker,
        quality_floor=quality_floor,
        trades=trades,
        win_rate=win_rate,
        net_pnl=net_pnl,
        final_capital=final_capital,
        proxy_exits=proxy_exits,
        proxy_exit_pct=proxy_pct,
    )


def main() -> int:
    window_days = int(os.getenv("WF_WINDOW_DAYS", "30"))
    windows = int(os.getenv("WF_WINDOWS", "4"))
    wallet_source = os.getenv("WF_WALLET_SOURCE", "db_active")
    profiles = [p.strip().lower() for p in os.getenv("WF_PROFILES", "balanced,aggressive").split(",") if p.strip()]
    trade_pickers = [p.strip().lower() for p in os.getenv("WF_TRADE_PICKERS", "first,best_quality").split(",") if p.strip()]
    quality_floors = [float(v) for v in os.getenv("WF_QUALITY_FLOORS", "0,20,35").split(",") if v.strip()]

    results: list[WindowResult] = []
    for profile in profiles:
        for trade_picker in trade_pickers:
            for quality_floor in quality_floors:
                for i in range(windows):
                    offset = i * window_days
                    results.append(_run_window(window_days, offset, profile, trade_picker, quality_floor, wallet_source))

    groups: dict[tuple[str, str, float], list[WindowResult]] = {}
    for result in results:
        groups.setdefault((result.profile, result.trade_picker, result.quality_floor), []).append(result)

    stable: list[tuple[tuple[str, str, float], list[WindowResult]]] = []
    for key, rows in groups.items():
        if rows and all(r.net_pnl > 0 for r in rows):
            stable.append((key, rows))

    best_key: tuple[str, str, float] | None = None
    best_avg = float("-inf")
    for key, rows in groups.items():
        avg = sum(r.net_pnl for r in rows) / len(rows) if rows else float("-inf")
        if avg > best_avg:
            best_avg = avg
            best_key = key

    print("=== WALK-FORWARD STABILITY SUMMARY ===")
    for key, rows in groups.items():
        profile, trade_picker, quality_floor = key
        avg = sum(r.net_pnl for r in rows) / len(rows) if rows else 0.0
        win_count = len([r for r in rows if r.net_pnl > 0])
        proxy_avg = sum(r.proxy_exit_pct for r in rows) / len(rows) if rows else 0.0
        print(
            f"profile={profile} picker={trade_picker} quality_floor={quality_floor:.0f} "
            f"windows={len(rows)} wins={win_count} avg_net=₹{avg:.2f} avg_proxy_exit_pct={proxy_avg:.2f}"
        )
        for row in rows:
            print(
                f"  offset={row.offset_days}d trades={row.trades} win_rate={row.win_rate:.2f}% "
                f"net=₹{row.net_pnl:.2f} final=₹{row.final_capital:.2f} proxy_exits={row.proxy_exits}"
            )

    print("\n=== STABLE CONFIGS ===")
    if stable:
        for key, rows in stable:
            profile, trade_picker, quality_floor = key
            print(
                f"profile={profile} picker={trade_picker} quality_floor={quality_floor:.0f} "
                f"all_windows_profitable=true avg_net=₹{(sum(r.net_pnl for r in rows) / len(rows)):.2f}"
            )
    else:
        print("No configuration stayed profitable across all windows.")

    if best_key is not None:
        print(f"\nBEST_AVG_CONFIG=profile={best_key[0]} picker={best_key[1]} quality_floor={best_key[2]:.0f} avg_net=₹{best_avg:.2f}")

    report_lines = [
        "# Walk-Forward Stability Report",
        "",
        f"Generated from: `{Path(__file__).resolve()}`",
        "",
        "## Results",
        "",
    ]
    for result in results:
        report_lines.append(
            "- "
            + f"profile={result.profile}, picker={result.trade_picker}, quality_floor={result.quality_floor:.0f}, "
            + f"offset={result.offset_days}d, trades={result.trades}, win_rate={result.win_rate:.2f}%, "
            + f"net=₹{result.net_pnl:.2f}, final=₹{result.final_capital:.2f}, proxy_exits={result.proxy_exits}"
        )
    report_lines.extend(
        [
            "",
            "## Stable Configs",
            "",
        ]
    )
    if stable:
        for key, rows in stable:
            profile, trade_picker, quality_floor = key
            report_lines.append(
                f"- profile={profile}, picker={trade_picker}, quality_floor={quality_floor:.0f}, avg_net=₹{(sum(r.net_pnl for r in rows) / len(rows)):.2f}"
            )
    else:
        report_lines.append("- None")
    if best_key is not None:
        report_lines.extend(
            [
                "",
                "## Best Average",
                "",
                f"- profile={best_key[0]}",
                f"- picker={best_key[1]}",
                f"- quality_floor={best_key[2]:.0f}",
                f"- avg_net=₹{best_avg:.2f}",
            ]
        )
    (ROOT / "WALKFORWARD_STABILITY_REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
