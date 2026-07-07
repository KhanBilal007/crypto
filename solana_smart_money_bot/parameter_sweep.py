from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from itertools import product


@dataclass
class SweepResult:
    confirmations: int
    window_min: int
    min_liq_usd: int
    max_util_pct: float
    avg_net: float
    median_net: float
    wins: int
    windows: int


def parse_float(text: str, key: str) -> float:
    m = re.search(rf"{re.escape(key)}₹(-?\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else 0.0


def parse_int(text: str, key: str) -> int:
    m = re.search(rf"{re.escape(key)}(\d+)", text)
    return int(m.group(1)) if m else 0


def run_walkforward(confirmations: int, window_min: int, min_liq: int, max_util: float) -> SweepResult:
    env = os.environ.copy()
    env["MIN_WHALE_CONFIRMATIONS"] = str(confirmations)
    env["CONFIRMATION_WINDOW_MINUTES"] = str(window_min)
    env["BT_MIN_LIQUIDITY_USD"] = str(min_liq)
    env["BT_MAX_UTIL_PCT"] = str(max_util)
    env["BT_MAX_TRADE_INR"] = "500"
    env["WF_WINDOW_DAYS"] = "30"
    env["WF_WINDOWS"] = "3"

    cmd = [sys.executable, "walkforward_backtest.py"]
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (p.stdout or "") + "\n" + (p.stderr or "")

    avg_net = parse_float(out, "avg_net=")
    median_net = parse_float(out, "median_net=")
    wins = parse_int(out, "wins=")
    windows = parse_int(out, "windows=")

    return SweepResult(
        confirmations=confirmations,
        window_min=window_min,
        min_liq_usd=min_liq,
        max_util_pct=max_util,
        avg_net=avg_net,
        median_net=median_net,
        wins=wins,
        windows=windows,
    )


def main() -> None:
    confirmations_grid = [1, 2]
    window_grid = [10, 20, 30]
    liq_grid = [0, 20000, 50000]
    util_grid = [2.0, 3.0, 5.0]

    results: list[SweepResult] = []
    combos = list(product(confirmations_grid, window_grid, liq_grid, util_grid))

    for i, (c, w, l, u) in enumerate(combos, start=1):
        print(f"[{i}/{len(combos)}] running c={c} w={w} liq={l} util={u}")
        try:
            r = run_walkforward(c, w, l, u)
            results.append(r)
        except Exception as exc:
            print(f"failed combo c={c} w={w} liq={l} util={u}: {exc}")

    results.sort(key=lambda x: (x.median_net, x.avg_net, x.wins), reverse=True)

    print("\n=== TOP 10 CONFIGS (by median net) ===")
    for r in results[:10]:
        print(
            f"c={r.confirmations} w={r.window_min} liq={r.min_liq_usd} util={r.max_util_pct} "
            f"wins={r.wins}/{r.windows} avg_net=₹{r.avg_net:.2f} median_net=₹{r.median_net:.2f}"
        )


if __name__ == "__main__":
    main()
