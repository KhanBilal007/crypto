from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


STABLE_OR_NATIVE_MINTS = {
    "So11111111111111111111111111111111111111112",  # wSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "Es9vMFrzaCERmJfrF4H2FYKQx2S5fXqL5n6rYhD4Y3F",  # USDT (legacy)
}


@dataclass
class ParsedSignal:
    wallet_address: str
    token_mint: str
    action: str
    sol_amount: float
    tx_hash: str
    timestamp: datetime


class TxParser:
    """Parses Helius enhanced transactions and extracts buy signals."""

    def parse_buy_signal(self, wallet_address: str, tx: dict[str, Any]) -> ParsedSignal | None:
        if tx.get("transactionError"):
            return None

        tx_hash = tx.get("signature") or tx.get("tx_hash")
        if not tx_hash:
            return None

        ts = tx.get("timestamp")
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)
        elif isinstance(ts, str):
            dt = datetime.fromisoformat(ts)
        else:
            dt = datetime.utcnow()

        token_mint = self._extract_bought_token(wallet_address, tx)
        if not token_mint:
            return None

        sol_spent = self._extract_sol_spent(wallet_address, tx)
        if sol_spent <= 0:
            return None

        return ParsedSignal(
            wallet_address=wallet_address,
            token_mint=token_mint,
            action="buy",
            sol_amount=sol_spent,
            tx_hash=tx_hash,
            timestamp=dt,
        )

    def _extract_bought_token(self, wallet_address: str, tx: dict[str, Any]) -> str | None:
        token_transfers = tx.get("tokenTransfers", []) or []

        # Prefer direct incoming token transfers to tracked wallet.
        candidates: list[tuple[str, float]] = []
        for t in token_transfers:
            mint = t.get("mint")
            if not mint or mint in STABLE_OR_NATIVE_MINTS:
                continue
            to_user = t.get("toUserAccount")
            if to_user != wallet_address:
                continue

            amount = t.get("tokenAmount", 0)
            try:
                amt = float(amount)
            except (TypeError, ValueError):
                amt = 0.0
            candidates.append((mint, amt))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # Some Helius swap shapes only expose the wallet-level balance changes in accountData.
        account_data = tx.get("accountData", []) or []
        account_candidates: list[tuple[str, float]] = []
        for entry in account_data:
            for change in entry.get("tokenBalanceChanges") or []:
                if change.get("userAccount") != wallet_address:
                    continue
                mint = change.get("mint")
                if not mint or mint in STABLE_OR_NATIVE_MINTS:
                    continue
                try:
                    amount = float(change.get("rawTokenAmount", {}).get("tokenAmount") or 0)
                except (TypeError, ValueError):
                    amount = 0.0
                if amount > 0:
                    account_candidates.append((mint, amount))

        if account_candidates:
            account_candidates.sort(key=lambda x: x[1], reverse=True)
            return account_candidates[0][0]

        # Fallback to swap events shape.
        events = tx.get("events", {}) or {}
        swap = events.get("swap", {}) or {}
        outputs = swap.get("tokenOutputs", []) or []
        for out in outputs:
            mint = out.get("mint")
            if mint and mint not in STABLE_OR_NATIVE_MINTS:
                return mint

        return None

    def _extract_sol_spent(self, wallet_address: str, tx: dict[str, Any]) -> float:
        native_transfers = tx.get("nativeTransfers", []) or []
        lamports_out = 0
        for nt in native_transfers:
            if nt.get("fromUserAccount") == wallet_address:
                lamports_out += int(nt.get("amount", 0) or 0)

        # Fallback for swap events with native input.
        if lamports_out == 0:
            account_data = tx.get("accountData", []) or []
            for entry in account_data:
                for change in entry.get("tokenBalanceChanges") or []:
                    if change.get("userAccount") != wallet_address:
                        continue
                    if change.get("mint") != "So11111111111111111111111111111111111111112":
                        continue
                    try:
                        token_amount = float(change.get("rawTokenAmount", {}).get("tokenAmount") or 0)
                    except (TypeError, ValueError):
                        token_amount = 0.0
                    if token_amount < 0:
                        return abs(token_amount) / 1_000_000_000

            events = tx.get("events", {}) or {}
            swap = events.get("swap", {}) or {}
            inputs = swap.get("tokenInputs", []) or []
            for inp in inputs:
                if inp.get("mint") == "So11111111111111111111111111111111111111112":
                    try:
                        return float(inp.get("tokenAmount", 0))
                    except (TypeError, ValueError):
                        return 0.0

        return lamports_out / 1_000_000_000
