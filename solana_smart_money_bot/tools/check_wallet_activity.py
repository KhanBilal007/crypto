from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings
from src.database import SessionLocal
from src.models import Token, Wallet
from src.wallet_activity_state import save_wallet_activity_snapshot
from src.signal_coverage import infer_zero_signals_cause, shorten_address, summarize_wallet_transactions
from src.token_data import TokenDataService
from src.tx_parser import TxParser
from src.trade_safety import evaluate_buy_gate
from src.wallet_validation import is_valid_solana_address


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _fetch_recent_transactions(client: httpx.AsyncClient, wallet_address: str, limit: int = 50) -> tuple[int, list[dict], str]:
    url = f"https://api-mainnet.helius-rpc.com/v0/addresses/{wallet_address}/transactions"
    params = {"api-key": settings.HELIUS_API_KEY, "limit": limit}
    try:
        resp = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        return 0, [], f"api_error:{exc}"

    if resp.status_code == 429:
        return resp.status_code, [], "rate_limit"
    if resp.status_code >= 400:
        return resp.status_code, [], f"api_error:{resp.status_code}"

    try:
        data = resp.json()
    except Exception as exc:
        return resp.status_code, [], f"api_error:{exc}"

    if not isinstance(data, list):
        return resp.status_code, [], "empty"
    return resp.status_code, data, ""


async def main() -> int:
    parser = TxParser()
    token_data_service = TokenDataService()

    with SessionLocal() as db:
        wallets = db.query(Wallet).all()
        active_wallets = [w for w in wallets if w.status == "active"]
        standby_wallets = [w for w in wallets if w.status == "standby"]
        disabled_wallets = [w for w in wallets if w.status == "disabled"]

        print("Wallet activity diagnostic:")
        print(f"* total wallets: {len(wallets)}")
        print(f"* active wallets: {len(active_wallets)}")
        print(f"* standby wallets: {len(standby_wallets)}")
        print(f"* disabled wallets: {len(disabled_wallets)}")
        print(f"* helius configured: {bool(settings.HELIUS_API_KEY)}")
        print(f"* helius rpc configured: {bool(settings.HELIUS_RPC_URL)}")
        print(f"* monitor mode: {settings.MONITOR_MODE}")
        print(f"* forward testing mode: {settings.FORWARD_TESTING_MODE}")

        invalid_wallets = [w.wallet_address for w in wallets if not is_valid_solana_address(w.wallet_address)]
        if invalid_wallets:
            print(f"* invalid wallets in db: {len(invalid_wallets)}")
            for address in invalid_wallets[:5]:
                print(f"  - {shorten_address(address)}")
        else:
            print("* invalid wallets in db: 0")

    per_wallet_reason_counts = Counter()
    api_errors = 0
    rate_limit_errors = 0
    total_recent_transactions = 0
    wallets_with_recent_transactions = 0
    wallets_with_zero_recent_transactions = 0
    possible_buy_like_transactions = 0
    parser_ready_transactions = 0
    parsed_signals: list[dict] = []
    wallet_rows: list[dict] = []

    async with httpx.AsyncClient(timeout=30) as client:
        with SessionLocal() as db:
            active_wallets = db.query(Wallet).filter(Wallet.status == "active").order_by(Wallet.score.desc()).all()
            if not active_wallets:
                print("* active wallet list is empty")

            for wallet in active_wallets:
                status_code, txs, error = await _fetch_recent_transactions(client, wallet.wallet_address)
                if error == "rate_limit":
                    rate_limit_errors += 1
                elif error.startswith("api_error"):
                    api_errors += 1

                summary = summarize_wallet_transactions(wallet.wallet_address, txs, parser)
                total_recent_transactions += summary["raw_tx_fetched"]
                possible_buy_like_transactions += summary["buy_like_transactions"]
                parser_ready_transactions += summary["buy_signals"]
                per_wallet_reason_counts.update(summary["reason_counts"])

                if summary["raw_tx_fetched"] > 0:
                    wallets_with_recent_transactions += 1
                else:
                    wallets_with_zero_recent_transactions += 1

                latest_ts = summary["latest_timestamp"] or "n/a"
                print(
                    f"- {shorten_address(wallet.wallet_address)} "
                    f"score={wallet.score:.2f} status={wallet.status} "
                    f"last_seen={latest_ts} "
                    f"recent_txs={summary['raw_tx_fetched']} "
                    f"parser_hits={summary['buy_signals']} "
                    f"buy_like={summary['buy_like_transactions']} "
                    f"status_code={status_code}"
                )

                for signal in summary["parsed_signals"]:
                    parsed_signals.append(
                        {
                            "wallet": wallet.wallet_address,
                            "token_mint": signal.token_mint,
                            "tx_hash": signal.tx_hash,
                            "sol_amount": signal.sol_amount,
                        }
                    )
                wallet_rows.append(
                    {
                        "wallet": wallet.wallet_address,
                        "short_wallet": shorten_address(wallet.wallet_address),
                        "score": round(wallet.score, 2),
                        "status": wallet.status,
                        "last_seen": latest_ts,
                        "recent_txs": summary["raw_tx_fetched"],
                        "parser_hits": summary["buy_signals"],
                        "buy_like": summary["buy_like_transactions"],
                    }
                )

    rejection_breakdown = dict(sorted(per_wallet_reason_counts.items(), key=lambda item: item[0]))
    filter_rejections = 0
    gate_rejection_breakdown = Counter()
    if parsed_signals:
        with SessionLocal() as db:
            for signal in parsed_signals:
                token_snapshot = await token_data_service.fetch_token_snapshot(signal["token_mint"])
                token_model = Token(
                    token_mint=signal["token_mint"],
                    liquidity_usd=float(token_snapshot["liquidity_usd"]),
                    token_age_minutes=float(token_snapshot["token_age_minutes"]),
                    holder_count=int(token_snapshot["holder_count"]),
                    top_holder_percent=float(token_snapshot["top_holder_percent"]),
                    top_10_holder_percent=float(token_snapshot["top_10_holder_percent"]),
                    mint_revoked=bool(token_snapshot["mint_revoked"]),
                    freeze_revoked=bool(token_snapshot["freeze_revoked"]),
                )
                gate_result = evaluate_buy_gate(
                    db,
                    token_model,
                    trade_amount_inr=settings.MIN_TRADE_INR,
                    combined_wallet_score=75.0,
                )
                if not gate_result.allowed:
                    filter_rejections += 1
                    gate_rejection_breakdown[gate_result.reason] += 1

    print(f"* wallets with recent transactions: {wallets_with_recent_transactions}")
    print(f"* wallets with zero recent transactions: {wallets_with_zero_recent_transactions}")
    print(f"* total recent transactions fetched: {total_recent_transactions}")
    print(f"* possible buy-like transactions: {possible_buy_like_transactions}")
    print(f"* parser-ready transactions: {parser_ready_transactions}")
    print(f"* api errors: {api_errors}")
    print(f"* rate limit errors: {rate_limit_errors}")
    print(f"* parser rejection breakdown: {json.dumps(rejection_breakdown, sort_keys=True)}")
    if gate_rejection_breakdown:
        print(f"* gate rejection breakdown: {json.dumps(dict(sorted(gate_rejection_breakdown.items())), sort_keys=True)}")

    report = {
        "generated_at_utc": _utcnow().isoformat(timespec="seconds"),
        "source": "diagnostic",
        "total_active_wallets": len(active_wallets),
        "total_recent_transactions": total_recent_transactions,
        "parser_succeeded": parser_ready_transactions,
        "buy_like_transactions": possible_buy_like_transactions,
        "api_errors": api_errors,
        "filter_rejections": filter_rejections,
        "forward_signals": 0,
        "wallets_with_recent_transactions": wallets_with_recent_transactions,
        "wallets_with_zero_recent_transactions": wallets_with_zero_recent_transactions,
        "parser_attempted": total_recent_transactions,
        "parser_failed": total_recent_transactions - parser_ready_transactions,
        "buy_signals": parser_ready_transactions,
        "rate_limit_errors": rate_limit_errors,
        "rejection_breakdown": rejection_breakdown,
        "wallets": wallet_rows[:10],
    }
    zero_cause = infer_zero_signals_cause(report)
    print(f"ZERO_SIGNALS_CAUSE={zero_cause}")
    report["zero_signals_cause"] = zero_cause
    save_wallet_activity_snapshot(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
