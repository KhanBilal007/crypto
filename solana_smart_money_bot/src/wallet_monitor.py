from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from config import settings
from src.utils.http_client import HTTPClient


class WalletMonitor:
    """Wallet monitor with websocket + polling fallback."""

    def __init__(self, mode: str = "polling") -> None:
        self.mode = mode
        self.http = HTTPClient(timeout=20.0)
        self.last_seen_signature: dict[str, str] = {}
        self._bootstrapped_wallets: set[str] = set()
        self.last_poll_at: dict[str, datetime] = {}
        self.last_poll_result: dict[str, str] = {}
        self.last_poll_tx_count: dict[str, int] = {}

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _helius_base_url() -> str:
        return "https://api-mainnet.helius-rpc.com"

    @staticmethod
    def _helius_ws_url() -> str:
        return f"wss://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY}"

    async def poll_wallet(self, wallet_address: str) -> list[dict[str, Any]]:
        if self.mode == "websocket":
            try:
                return await self._poll_wallet_via_ws(wallet_address)
            except Exception as exc:
                logger.error(f"WebSocket path failed wallet={wallet_address}; fallback polling error={exc}")

        return await self._poll_wallet_via_http(wallet_address)

    async def _poll_wallet_via_ws(self, wallet_address: str) -> list[dict[str, Any]]:
        # MVP websocket mode: quick subscribe/read cycle per wallet.
        # This keeps interface real-time compatible without full daemon management.
        try:
            import websockets
        except Exception:
            logger.warning("websockets package missing; websocket mode unavailable")
            return []

        if not settings.HELIUS_API_KEY:
            logger.warning("HELIUS_API_KEY is missing; wallet monitor cannot fetch live data")
            return []

        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": [{"mentions": [wallet_address]}, {"commitment": "confirmed"}],
        }

        signatures: list[str] = []
        async with websockets.connect(self._helius_ws_url(), ping_interval=30) as ws:
            await ws.send(json.dumps(req))
            # Read for a short burst to keep loop responsive.
            for _ in range(2):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.2)
                except asyncio.TimeoutError:
                    break
                payload = json.loads(msg)
                value = ((((payload.get("params") or {}).get("result") or {}).get("value")) or {})
                sig = value.get("signature")
                err = value.get("err")
                if sig and err is None:
                    signatures.append(sig)

        if not signatures:
            return []

        # Use enhanced parser endpoint for detailed data from signatures.
        url = f"{self._helius_base_url()}/v0/transactions"
        resp = await self.http.post(url + f"?api-key={settings.HELIUS_API_KEY}", json={"transactions": signatures[-50:]})
        return resp if isinstance(resp, list) else []

    async def _poll_wallet_via_http(self, wallet_address: str) -> list[dict[str, Any]]:
        if not settings.HELIUS_API_KEY:
            logger.warning("HELIUS_API_KEY is missing; wallet monitor cannot fetch live data")
            self.last_poll_result[wallet_address] = "missing_api_key"
            self.last_poll_at[wallet_address] = self._utcnow()
            return []

        params: dict[str, Any] = {"api-key": settings.HELIUS_API_KEY, "limit": 25}
        if wallet_address in self.last_seen_signature:
            params["until"] = self.last_seen_signature[wallet_address]

        url = f"{self._helius_base_url()}/v0/addresses/{wallet_address}/transactions"

        try:
            txs = await self.http.get(url, params=params)
        except Exception as exc:
            logger.error(f"Helius fetch failed wallet={wallet_address} error={exc}")
            self.last_poll_result[wallet_address] = "error"
            self.last_poll_at[wallet_address] = self._utcnow()
            return []

        if not isinstance(txs, list) or not txs:
            logger.info(f"Helius returned no transactions wallet={wallet_address}")
            self.last_poll_result[wallet_address] = "empty"
            self.last_poll_at[wallet_address] = self._utcnow()
            self.last_poll_tx_count[wallet_address] = 0
            return []

        if wallet_address not in self._bootstrapped_wallets:
            newest_sig = txs[0].get("signature")
            if newest_sig:
                self.last_seen_signature[wallet_address] = newest_sig
            self._bootstrapped_wallets.add(wallet_address)
            self.last_poll_result[wallet_address] = "bootstrap"
            self.last_poll_at[wallet_address] = self._utcnow()
            self.last_poll_tx_count[wallet_address] = len(txs)
            logger.info(
                f"Bootstrap complete for wallet={wallet_address}; skipping historical tx backfill "
                f"fetched={len(txs)}"
            )
            return []

        txs_sorted = list(reversed(txs))
        newest_sig = txs[0].get("signature")
        if newest_sig:
            self.last_seen_signature[wallet_address] = newest_sig

        self.last_poll_result[wallet_address] = "fetched"
        self.last_poll_at[wallet_address] = self._utcnow()
        self.last_poll_tx_count[wallet_address] = len(txs_sorted)
        logger.info(f"Fetched {len(txs_sorted)} live txs for wallet={wallet_address}")
        return txs_sorted

    async def monitor_delay(self) -> None:
        await asyncio.sleep(settings.WALLET_POLL_SECONDS)
