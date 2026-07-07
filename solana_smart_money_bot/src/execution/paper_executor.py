from __future__ import annotations

import hashlib
from datetime import datetime

from src.execution.base import BaseExecutor, ExecutionResult


class PaperExecutor(BaseExecutor):
    name = "paper"

    async def buy(self, token_mint: str, amount_sol: float) -> ExecutionResult:
        price = max(0.000001, amount_sol / 10000.0)
        token_amount = amount_sol / price
        tx_hash = hashlib.sha256(f"paper-buy-{token_mint}-{datetime.utcnow().isoformat()}".encode()).hexdigest()[:48]
        return ExecutionResult(
            success=True,
            tx_hash=tx_hash,
            price=price,
            token_amount=token_amount,
            side="buy",
            executor=self.name,
            confirmed=True,
            confirmation_status="simulated",
            message="paper buy",
        )

    async def sell(self, token_mint: str, sell_percent: float, token_amount: float) -> ExecutionResult:
        sold_amount = token_amount * (sell_percent / 100.0)
        price = max(0.000001, 0.0001)
        tx_hash = hashlib.sha256(f"paper-sell-{token_mint}-{datetime.utcnow().isoformat()}".encode()).hexdigest()[:48]
        return ExecutionResult(
            success=True,
            tx_hash=tx_hash,
            price=price,
            token_amount=sold_amount,
            side="sell",
            executor=self.name,
            confirmed=True,
            confirmation_status="simulated",
            message="paper sell",
        )
