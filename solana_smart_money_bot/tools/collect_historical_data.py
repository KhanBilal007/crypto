from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest_7d import Backtester  # noqa: E402
from config import settings  # noqa: E402
from src.database import SessionLocal, init_db  # noqa: E402
from src.models import Wallet  # noqa: E402
from src.historical_cache import cache_token_snapshot  # noqa: E402
from src.token_data import TokenDataService  # noqa: E402
from src.tx_parser import TxParser  # noqa: E402
from src.wallet_validation import is_valid_solana_address  # noqa: E402


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def main() -> int:
    init_db()
    parser = argparse.ArgumentParser(description="Collect historical wallet txs and token snapshots into local cache.")
    parser.add_argument("--days", type=int, default=30, help="How many days of wallet history to collect")
    parser.add_argument("--wallet-source", choices=["env", "db_active", "db_all", "combined"], default="db_active")
    parser.add_argument("--max-wallets", type=int, default=settings.MAX_TRACKED_WALLETS)
    args = parser.parse_args()

    backtester = Backtester()
    token_service = TokenDataService()
    tx_parser = TxParser()
    since = _utcnow() - timedelta(days=args.days)

    if args.wallet_source != "env":
        import os
        os.environ["BACKTEST_WALLET_SOURCE"] = args.wallet_source

    import os
    os.environ["BACKTEST_USE_CACHE"] = "false"

    wallets = backtester._tracked_wallets()[: args.max_wallets]
    if not wallets:
        with SessionLocal() as db:
            wallets = [w.wallet_address for w in db.query(Wallet).filter(Wallet.status == "active").order_by(Wallet.score.desc()).limit(args.max_wallets).all()]

    wallets = [w for w in wallets if is_valid_solana_address(w)]

    print("Historical data collection")
    print(f"* days: {args.days}")
    print(f"* wallets: {len(wallets)}")
    print(f"* since_utc: {since.isoformat()}")

    total_raw = 0
    total_parsed = 0
    token_mints: set[str] = set()
    source_counter = Counter()

    for wallet in wallets:
        txs = await backtester._fetch_wallet_txs(wallet, since)
        total_raw += len(txs)
        for tx in txs:
            parsed = tx_parser.parse_buy_signal(wallet, tx)
            if parsed:
                total_parsed += 1
                token_mints.add(parsed.token_mint)
        print(f"- wallet={wallet[:6]}... raw_txs={len(txs)} parsed_buys={sum(1 for tx in txs if tx_parser.parse_buy_signal(wallet, tx))}")

    print(f"* total raw txs: {total_raw}")
    print(f"* parsed buy signals: {total_parsed}")
    print(f"* unique tokens: {len(token_mints)}")

    for token_mint in sorted(token_mints):
        snapshot = await token_service.fetch_token_snapshot(token_mint)
        cache_token_snapshot(token_mint, "merged", snapshot)
        for src in snapshot.get("market_sources", []):
            source_counter[src] += 1

    print(f"* cached token snapshots: {len(token_mints)}")
    print(f"* market sources used: {dict(source_counter)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
