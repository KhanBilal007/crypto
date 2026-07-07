from __future__ import annotations

import asyncio
from collections import Counter

from config import settings
from src.utils.http_client import HTTPClient


# Diverse liquid Solana tokens to find cross-token profitable traders.
TOKEN_MINTS = [
    "So11111111111111111111111111111111111111112",  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",   # JUP
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6k6QvF2G6w6T4RBw",  # BONK
]


async def fetch_top_traders(http: HTTPClient, token_mint: str) -> list[str]:
    url = "https://public-api.birdeye.so/defi/v2/tokens/top_traders"
    headers = {
        "X-API-KEY": settings.BIRDEYE_API_KEY,
        "x-chain": "solana",
    }
    params = {
        "address": token_mint,
        "time_frame": "30d",
        "sort_by": "total_pnl",
        "sort_type": "desc",
        "offset": 0,
        "limit": 10,
    }

    data = await http.get(url, params=params, headers=headers)
    rows = ((data.get("data") or {}).get("items") or []) if isinstance(data, dict) else []

    wallets: list[str] = []
    for row in rows:
        owner = row.get("owner") or row.get("wallet") or row.get("address")
        if owner:
            wallets.append(owner)
    return wallets


async def main() -> None:
    if not settings.BIRDEYE_API_KEY:
        raise RuntimeError("Set BIRDEYE_API_KEY in .env first")

    http = HTTPClient(timeout=20.0)
    try:
        all_wallets: list[str] = []
        for mint in TOKEN_MINTS:
            try:
                wallets = await fetch_top_traders(http, mint)
                all_wallets.extend(wallets)
                print(f"Fetched {len(wallets)} candidates from token={mint}")
            except Exception as exc:
                print(f"Skipping token={mint} due error: {exc}")

        if not all_wallets:
            print("No wallets discovered")
            return

        counts = Counter(all_wallets)
        ranked = [w for w, _ in counts.most_common(30)]
        top = ranked[:20]

        print("\nTop discovered candidate wallets:")
        for w in top:
            print(w)

        print("\nPaste this into .env:")
        print("CANDIDATE_WALLETS=" + ",".join(top))
    finally:
        await http.close()


if __name__ == "__main__":
    asyncio.run(main())
