from __future__ import annotations

from loguru import logger

from src.utils.http_client import HTTPClient


class PriceMonitor:
    """Live token price monitor via DexScreener with fallback."""

    def __init__(self) -> None:
        self.http = HTTPClient(timeout=15.0)

    async def get_price(self, token_mint: str, fallback_price: float) -> float:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
        try:
            data = await self.http.get(url)
            pairs = data.get("pairs", []) if isinstance(data, dict) else []
            if not pairs:
                logger.warning(f"No DexScreener pairs for token={token_mint}, using fallback")
                return fallback_price

            best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
            price_usd = float(best.get("priceUsd") or 0)
            if price_usd <= 0:
                return fallback_price

            logger.info(f"Live price token={token_mint} usd={price_usd:.8f}")
            return price_usd
        except Exception as exc:
            logger.error(f"Price fetch failed token={token_mint} error={exc}; using fallback")
            return fallback_price
