from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

from loguru import logger

from config import settings
from src.execution.base import BaseExecutor, ExecutionResult
from src.utils.http_client import HTTPClient


class TrojanExecutor(BaseExecutor):
    name = "trojan"

    def __init__(self) -> None:
        self.http = HTTPClient(timeout=10.0)
        self._sent_command_ids: set[str] = set()

    async def _relay_command(self, command: str, side: str, token_mint: str) -> bool:
        if not settings.EXTERNAL_EXECUTION_ENABLED:
            logger.info("External execution disabled; command logged only")
            return False

        if not settings.COMMAND_BRIDGE_URL:
            logger.warning("COMMAND_BRIDGE_URL missing; cannot relay command")
            return False

        command_id = hashlib.sha256(f"{side}:{token_mint}:{command}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:32]
        if command_id in self._sent_command_ids:
            logger.info(f"Skipping duplicate command_id={command_id}")
            return

        payload = {
            "command_id": command_id,
            "timestamp": datetime.utcnow().isoformat(),
            "executor": self.name,
            "side": side,
            "token_mint": token_mint,
            "command": command,
            "priority_fee_level": settings.PRIORITY_FEE_LEVEL,
            "slippage_bps": settings.SLIPPAGE_BPS,
        }
        headers = {"Authorization": f"Bearer {settings.COMMAND_BRIDGE_TOKEN}"} if settings.COMMAND_BRIDGE_TOKEN else {}

        delay = 0.3
        max_attempts = max(1, settings.COMMAND_RELAY_MAX_RETRIES)
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.http.post(settings.COMMAND_BRIDGE_URL, json=payload, headers=headers)
                ack = bool(response.get("ack", True)) if isinstance(response, dict) else True
                if ack:
                    self._sent_command_ids.add(command_id)
                    logger.info(f"Relayed command_id={command_id} side={side} token={token_mint} attempt={attempt}")
                    return True
                logger.warning(f"Bridge returned non-ack for command_id={command_id} attempt={attempt}")
            except Exception as exc:
                logger.error(f"Command relay failed command_id={command_id} attempt={attempt} error={exc}")

            if attempt < max_attempts:
                await asyncio.sleep(delay)
                delay *= 2
        return False

    async def buy(self, token_mint: str, amount_sol: float) -> ExecutionResult:
        command = settings.TROJAN_BUY_TEMPLATE.format(token_mint=token_mint, amount_sol=amount_sol)
        logger.info(f"Trojan command: {command}")
        relayed = await self._relay_command(command, "buy", token_mint)

        tx_hash = hashlib.sha256(f"trojan-buy-{datetime.utcnow().isoformat()}".encode()).hexdigest()[:48]
        return ExecutionResult(
            success=relayed or not settings.EXTERNAL_EXECUTION_ENABLED,
            tx_hash=tx_hash,
            price=0.0,
            token_amount=0.0,
            side="buy",
            executor=self.name,
            confirmed=relayed,
            confirmation_status="bridge_ack" if relayed else "not_relayed",
            message=command,
            details={"relayed": relayed},
        )

    async def sell(self, token_mint: str, sell_percent: float, token_amount: float) -> ExecutionResult:
        command = settings.TROJAN_SELL_TEMPLATE.format(token_mint=token_mint, sell_percent=sell_percent)
        logger.info(f"Trojan command: {command}")
        relayed = await self._relay_command(command, "sell", token_mint)

        tx_hash = hashlib.sha256(f"trojan-sell-{datetime.utcnow().isoformat()}".encode()).hexdigest()[:48]
        return ExecutionResult(
            success=relayed or not settings.EXTERNAL_EXECUTION_ENABLED,
            tx_hash=tx_hash,
            price=0.0,
            token_amount=0.0,
            side="sell",
            executor=self.name,
            confirmed=relayed,
            confirmation_status="bridge_ack" if relayed else "not_relayed",
            message=command,
            details={"relayed": relayed},
        )
