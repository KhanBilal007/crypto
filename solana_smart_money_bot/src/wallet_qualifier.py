from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from src.utils.http_client import HTTPClient
from src.wallet_validation import is_valid_solana_address

STABLE_OR_NATIVE = {
    "So11111111111111111111111111111111111111112",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfrF4H2FYKQx2S5fXqL5n6rYhD4Y3F",
}


@dataclass
class WalletQualification:
    wallet: str
    qualified: bool
    win_rate: float
    avg_roi: float
    total_round_trips: int
    score_seed: float


class WalletQualifier:
    def __init__(self) -> None:
        self.http = HTTPClient(timeout=25.0)

    async def qualify_wallet(self, wallet_address: str) -> WalletQualification:
        if not is_valid_solana_address(wallet_address):
            return WalletQualification(
                wallet=wallet_address,
                qualified=False,
                win_rate=0.0,
                avg_roi=0.0,
                total_round_trips=0,
                score_seed=0.0,
            )
        txs = await self._fetch_wallet_txs(wallet_address)
        win_rate, avg_roi, rounds = self._estimate_performance(wallet_address, txs)

        qualified = (
            rounds >= 3 and win_rate >= 45.0 and avg_roi >= -5.0
        )

        # Seed score used before bot has enough local outcomes.
        normalized_roi = max(0.0, min(100.0, avg_roi + 50.0))
        score_seed = (win_rate * 0.60) + (normalized_roi * 0.40)

        return WalletQualification(
            wallet=wallet_address,
            qualified=qualified,
            win_rate=round(win_rate, 2),
            avg_roi=round(avg_roi, 2),
            total_round_trips=rounds,
            score_seed=round(score_seed, 2),
        )

    async def _fetch_wallet_txs(self, wallet_address: str) -> list[dict[str, Any]]:
        if not settings.HELIUS_API_KEY:
            return []
        url = f"https://api-mainnet.helius-rpc.com/v0/addresses/{wallet_address}/transactions"
        params = {
            "api-key": settings.HELIUS_API_KEY,
            "limit": 100,
        }
        try:
            data = await self.http.get(url, params=params)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _estimate_performance(self, wallet_address: str, txs: list[dict[str, Any]]) -> tuple[float, float, int]:
        # Oldest first for round-trip tracking.
        txs = list(reversed(txs))

        entries: dict[str, list[float]] = {}
        rois: list[float] = []

        for tx in txs:
            if tx.get("transactionError"):
                continue
            events = tx.get("events", {}) or {}
            swap = events.get("swap", {}) or {}
            ins = swap.get("tokenInputs", []) or []
            outs = swap.get("tokenOutputs", []) or []
            if not ins or not outs:
                continue

            input_leg = self._best_leg(ins)
            output_leg = self._best_leg(outs)
            if not input_leg or not output_leg:
                continue

            in_mint, in_amt = input_leg
            out_mint, out_amt = output_leg
            if in_amt <= 0 or out_amt <= 0:
                continue

            # BUY: spend stable/native to receive alt token.
            if in_mint in STABLE_OR_NATIVE and out_mint not in STABLE_OR_NATIVE:
                entries.setdefault(out_mint, []).append(in_amt)

            # SELL: spend alt token to receive stable/native.
            elif in_mint not in STABLE_OR_NATIVE and out_mint in STABLE_OR_NATIVE:
                stack = entries.get(in_mint, [])
                if stack:
                    entry_value = stack.pop(0)
                    roi = ((out_amt - entry_value) / entry_value) * 100.0
                    rois.append(roi)

        rounds = len(rois)
        if rounds == 0:
            return 0.0, 0.0, 0

        wins = len([r for r in rois if r > 0])
        win_rate = (wins / rounds) * 100.0
        avg_roi = sum(rois) / rounds
        return win_rate, avg_roi, rounds

    @staticmethod
    def _best_leg(legs: list[dict[str, Any]]) -> tuple[str, float] | None:
        best: tuple[str, float] | None = None
        for leg in legs:
            mint = leg.get("mint")
            try:
                amount = float(leg.get("tokenAmount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            if not mint or amount <= 0:
                continue
            if best is None or amount > best[1]:
                best = (mint, amount)
        return best
