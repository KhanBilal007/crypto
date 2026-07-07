from __future__ import annotations

import base64
import json
from typing import Any

from loguru import logger
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Processed
from solana.rpc.core import TransactionExpiredBlockheightExceededError, UnconfirmedTxError
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from config import settings
from src.execution.base import BaseExecutor, ExecutionResult
from src.utils.http_client import HTTPClient


class JupiterExecutor(BaseExecutor):
    name = "jupiter"
    SOL_MINT = "So11111111111111111111111111111111111111112"

    def __init__(self) -> None:
        self.http = HTTPClient()

    @staticmethod
    def _rpc_url() -> str:
        if settings.HELIUS_RPC_URL.strip():
            return settings.HELIUS_RPC_URL.strip()
        if settings.HELIUS_API_KEY.strip():
            return f"https://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY.strip()}"
        return "https://api.mainnet-beta.solana.com"

    @staticmethod
    def _load_keypair() -> Keypair:
        private_key = settings.PRIVATE_KEY.strip()
        if not private_key:
            raise RuntimeError("PRIVATE_KEY is required for Jupiter live execution")
        if private_key.startswith("["):
            raw = json.loads(private_key)
            return Keypair.from_bytes(bytes(raw))
        try:
            return Keypair.from_base58_string(private_key)
        except Exception:
            raw = json.loads(private_key)
            return Keypair.from_bytes(bytes(raw))

    async def _quote(self, input_mint: str, output_mint: str, amount: int) -> dict:
        url = f"{settings.JUPITER_BASE_URL}/swap/v1/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": settings.SLIPPAGE_BPS,
        }
        return await self.http.get(url, params=params)

    async def quote_sell(self, token_mint: str, sell_percent: float, token_amount: float) -> dict[str, Any] | None:
        if sell_percent <= 0 or token_amount <= 0:
            return None
        decimals = await self._token_decimals(token_mint)
        sell_token_amount = token_amount * (sell_percent / 100.0)
        base_units = int(sell_token_amount * (10**decimals))
        if base_units <= 0:
            return None
        return await self._quote(token_mint, self.SOL_MINT, base_units)

    async def _swap(self, quote: dict[str, Any], signer: Keypair) -> dict[str, Any]:
        payload = {
            "quoteResponse": quote,
            "userPublicKey": str(signer.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "useSharedAccounts": True,
            "asLegacyTransaction": False,
            "skipUserAccountsRpcCalls": True,
        }
        if settings.PRIORITY_FEE_LEVEL == "high":
            payload["prioritizationFeeLamports"] = 50_000
        elif settings.PRIORITY_FEE_LEVEL == "medium":
            payload["prioritizationFeeLamports"] = 10_000
        else:
            payload["prioritizationFeeLamports"] = 0

        url = f"{settings.JUPITER_BASE_URL}/swap/v1/swap"
        swap_resp = await self.http.post(url, json=payload)
        return swap_resp

    @staticmethod
    def _tx_signature(tx: VersionedTransaction) -> Signature:
        sigs = list(tx.signatures)
        if not sigs:
            raise RuntimeError("Swap transaction has no signatures")
        return sigs[0]

    @staticmethod
    async def _confirm_signature(signature: Signature, *, last_valid_block_height: int | None = None) -> Any:
        async with AsyncClient(JupiterExecutor._rpc_url()) as client:
            return await client.confirm_transaction(
                signature,
                commitment=Confirmed,
                sleep_seconds=float(settings.TX_CONFIRMATION_POLL_INTERVAL_SECONDS),
                last_valid_block_height=last_valid_block_height,
            )

    async def _send_signed_transaction(self, signed_tx: VersionedTransaction, *, last_valid_block_height: int | None = None) -> tuple[Signature, Any]:
        async with AsyncClient(self._rpc_url()) as client:
            opts = TxOpts(
                skip_confirmation=True,
                skip_preflight=False,
                preflight_commitment=Processed,
                max_retries=settings.MAX_EXECUTION_RETRIES,
                last_valid_block_height=last_valid_block_height,
            )
            resp = await client.send_raw_transaction(bytes(signed_tx), opts=opts)
            signature = resp.value
            if isinstance(signature, str):
                signature = Signature.from_string(signature)
            return signature, resp

    async def _execute_live_swap(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        side: str,
        human_amount: float,
    ) -> ExecutionResult:
        signer = self._load_keypair()
        last_error: str = "unknown"

        for attempt in range(1, max(1, settings.MAX_EXECUTION_RETRIES) + 1):
            quote = await self._quote(input_mint, output_mint, amount)
            if not quote or quote.get("priceImpactPct") is None:
                last_error = "Jupiter quote failed"
                continue

            price_impact_pct = float(quote.get("priceImpactPct") or 0.0)
            if price_impact_pct * 10_000 > settings.MAX_PRICE_IMPACT_BPS:
                last_error = "Price impact too high"
                continue

            swap_resp = await self._swap(quote, signer)
            swap_tx_b64 = swap_resp.get("swapTransaction")
            if not swap_tx_b64:
                last_error = "Jupiter swap transaction was not returned"
                continue

            raw_tx = VersionedTransaction.from_bytes(base64.b64decode(swap_tx_b64))
            signed_tx = VersionedTransaction.populate(raw_tx.message, [signer.sign_message(bytes(raw_tx.message))])
            sent_sig, send_meta = await self._send_signed_transaction(
                signed_tx,
                last_valid_block_height=swap_resp.get("lastValidBlockHeight"),
            )
            confirmation_status = "confirmed"
            confirm_meta: Any = None
            try:
                confirm_meta = await self._confirm_signature(
                    sent_sig,
                    last_valid_block_height=swap_resp.get("lastValidBlockHeight"),
                )
            except UnconfirmedTxError as exc:
                confirmation_status = "timeout"
                last_error = f"Confirmation timed out: {exc}"
            except TransactionExpiredBlockheightExceededError as exc:
                confirmation_status = "expired"
                last_error = f"Transaction expired before confirmation: {exc}"
            except Exception as exc:
                confirmation_status = "unknown"
                last_error = f"Confirmation failed: {exc}"

            status_obj = None
            try:
                value = getattr(confirm_meta, "value", None)
                if isinstance(value, list) and value:
                    status_obj = value[0]
                elif value is not None:
                    status_obj = value
            except Exception:
                status_obj = None

            if confirmation_status == "confirmed":
                confirmed = bool(status_obj is not None and getattr(status_obj, "err", None) is None)
                if not confirmed:
                    confirmation_status = "confirmation_failed"
            else:
                confirmed = False

            out_amount_raw = float(quote.get("outAmount", 0.0) or 0.0)
            human_token_amount = human_amount if side == "sell" else 0.0
            if side == "buy" and out_amount_raw > 0:
                output_decimals = await self._token_decimals(output_mint)
                human_token_amount = out_amount_raw / (10**output_decimals) if output_decimals >= 0 else out_amount_raw
            if side == "buy":
                price = (float(amount) / 1_000_000_000.0 / human_token_amount) if human_token_amount else 0.0
            else:
                price = (out_amount_raw / 1_000_000_000.0 / human_token_amount) if human_token_amount else 0.0
            return ExecutionResult(
                success=confirmed,
                tx_hash=str(sent_sig),
                price=price,
                token_amount=human_token_amount,
                side=side,
                executor=self.name,
                confirmed=confirmed,
                confirmation_status=confirmation_status,
                retries=attempt - 1,
                message="Live Jupiter swap executed" if confirmed else last_error,
                details={
                    "quote": quote,
                    "swap_response": swap_resp,
                    "send_response": str(send_meta),
                    "confirm_response": str(confirm_meta) if confirm_meta is not None else "",
                    "human_amount": human_amount,
                    "status": str(status_obj) if status_obj is not None else "",
                },
            )

        return ExecutionResult(
            success=False,
            tx_hash="",
            price=0.0,
            token_amount=0.0,
            side=side,
            executor=self.name,
            confirmed=False,
            confirmation_status="failed",
            retries=max(0, settings.MAX_EXECUTION_RETRIES),
            message=last_error,
            details={"input_mint": input_mint, "output_mint": output_mint, "amount": amount},
        )

    async def _token_decimals(self, token_mint: str) -> int:
        rpc_url = self._rpc_url()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getParsedAccountInfo",
            "params": [token_mint, {"encoding": "jsonParsed"}],
        }
        resp = await self.http.post(rpc_url, json=payload)
        info = (((resp.get("result") or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get("info", {})
        return int(info.get("decimals") or 0)

    async def buy(self, token_mint: str, amount_sol: float) -> ExecutionResult:
        # Native SOL mint for Jupiter
        sol_mint = self.SOL_MINT
        lamports = int(amount_sol * 1_000_000_000)

        if settings.EXECUTION_MODE != "jupiter_live":
            quote = await self._quote(sol_mint, token_mint, lamports)
            out_amount = float(quote.get("outAmount", 0.0))
            price = (amount_sol / out_amount) if out_amount else 0.0
            logger.warning("JupiterExecutor in safe mode: no real tx will be sent")
            return ExecutionResult(
                success=True,
                tx_hash="JUPITER_PAPER_TX",
                price=price,
                token_amount=out_amount,
                side="buy",
                executor=self.name,
                confirmed=True,
                confirmation_status="quote_only",
                message="Quote-only mode",
            )

        return await self._execute_live_swap(
            input_mint=sol_mint,
            output_mint=token_mint,
            amount=lamports,
            side="buy",
            human_amount=amount_sol,
        )

    async def sell(self, token_mint: str, sell_percent: float, token_amount: float) -> ExecutionResult:
        if settings.EXECUTION_MODE != "jupiter_live":
            return ExecutionResult(
                success=True,
                tx_hash="JUPITER_PAPER_SELL_TX",
                price=0.0,
                token_amount=token_amount * (sell_percent / 100.0),
                side="sell",
                executor=self.name,
                confirmed=True,
                confirmation_status="quote_only",
                message="Quote-only sell mode",
            )

        sell_token_amount = token_amount * (sell_percent / 100.0)
        decimals = await self._token_decimals(token_mint)
        base_units = int(sell_token_amount * (10**decimals))
        sol_mint = self.SOL_MINT
        return await self._execute_live_swap(
            input_mint=token_mint,
            output_mint=sol_mint,
            amount=base_units,
            side="sell",
            human_amount=sell_token_amount,
        )
