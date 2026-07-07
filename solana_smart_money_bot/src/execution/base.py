from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ExecutionResult:
    success: bool
    tx_hash: str
    price: float
    token_amount: float
    side: str = ""
    executor: str = ""
    confirmed: bool = False
    confirmation_status: str = "unknown"
    retries: int = 0
    message: str = ""
    details: dict[str, Any] | None = None


class BaseExecutor(ABC):
    name = "base"

    @abstractmethod
    async def buy(self, token_mint: str, amount_sol: float) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def sell(self, token_mint: str, sell_percent: float, token_amount: float) -> ExecutionResult:
        raise NotImplementedError

    async def quote_sell(self, token_mint: str, sell_percent: float, token_amount: float) -> dict[str, Any] | None:
        return None
