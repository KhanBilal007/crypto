from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.tx_parser import ParsedSignal, TxParser


SUPPORTED_DEX_SOURCES = {
    "JUPITER",
    "ORCA",
    "PUMP_AMM",
    "RAYDIUM",
    "UNKNOWN",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def shorten_address(address: str, head: int = 6, tail: int = 4) -> str:
    if len(address) <= head + tail + 3:
        return address
    return f"{address[:head]}...{address[-tail:]}"


@dataclass
class TxCoverageResult:
    signature: str
    category: str
    reason: str
    buy_like: bool
    parsed_signal: ParsedSignal | None
    timestamp: datetime | None
    token_mint: str = ""


def _wallet_account_entry(wallet_address: str, tx: dict[str, Any]) -> dict[str, Any]:
    for account in tx.get("accountData") or []:
        if account.get("account") == wallet_address:
            return account
    return {}


def _wallet_in_transfer_flow(wallet_address: str, tx: dict[str, Any]) -> bool:
    for transfer in tx.get("tokenTransfers") or []:
        if transfer.get("toUserAccount") == wallet_address or transfer.get("fromUserAccount") == wallet_address:
            return True
    for transfer in tx.get("nativeTransfers") or []:
        if transfer.get("toUserAccount") == wallet_address or transfer.get("fromUserAccount") == wallet_address:
            return True
    return False


def _wallet_token_changes(wallet_address: str, tx: dict[str, Any]) -> list[dict[str, Any]]:
    account = _wallet_account_entry(wallet_address, tx)
    changes = account.get("tokenBalanceChanges") or []
    if changes:
        return list(changes)

    flattened: list[dict[str, Any]] = []
    for account_entry in tx.get("accountData") or []:
        for change in account_entry.get("tokenBalanceChanges") or []:
            if change.get("userAccount") == wallet_address:
                flattened.append(change)
    return flattened


def _net_native_change(wallet_address: str, tx: dict[str, Any]) -> float:
    account = _wallet_account_entry(wallet_address, tx)
    try:
        return float(account.get("nativeBalanceChange") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _has_buy_like_flow(wallet_address: str, tx: dict[str, Any]) -> bool:
    native_change = _net_native_change(wallet_address, tx)
    token_changes = _wallet_token_changes(wallet_address, tx)
    has_positive_token = False
    for change in token_changes:
        mint = change.get("mint")
        if mint == "So11111111111111111111111111111111111111112":
            continue
        try:
            amount = float(change.get("rawTokenAmount", {}).get("tokenAmount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount > 0:
            has_positive_token = True
            break
    return native_change < 0 and has_positive_token


def classify_transaction(wallet_address: str, tx: dict[str, Any], parser: TxParser | None = None) -> TxCoverageResult:
    signature = str(tx.get("signature") or tx.get("tx_hash") or "")
    timestamp = tx.get("timestamp")
    parsed_signal = parser.parse_buy_signal(wallet_address, tx) if parser is not None else None
    if isinstance(timestamp, (int, float)):
        parsed_timestamp = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
    elif isinstance(timestamp, str):
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            parsed_timestamp = None
    else:
        parsed_timestamp = None

    if tx.get("transactionError"):
        return TxCoverageResult(
            signature=signature,
            category="parser_error",
            reason="transaction_error",
            buy_like=False,
            parsed_signal=None,
            timestamp=parsed_timestamp,
        )

    if parsed_signal is not None:
        return TxCoverageResult(
            signature=signature,
            category="parsed_buy_signal",
            reason="parsed_buy_signal",
            buy_like=True,
            parsed_signal=parsed_signal,
            timestamp=parsed_timestamp,
            token_mint=parsed_signal.token_mint,
        )

    tx_type = str(tx.get("type") or "").upper()
    source = str(tx.get("source") or "").upper()
    wallet_involved = _wallet_in_transfer_flow(wallet_address, tx) or bool(_wallet_account_entry(wallet_address, tx))
    buy_like = _has_buy_like_flow(wallet_address, tx)
    wallet_native = _net_native_change(wallet_address, tx)

    if tx_type in {"TRANSFER", "SOL_TRANSFER", "TRANSFER_CHECKED"}:
        category = "ignored_transfer_only"
        reason = "transfer_only"
    elif tx_type and tx_type != "SWAP":
        category = "ignored_not_swap"
        reason = "not_a_swap"
    elif source and source not in SUPPORTED_DEX_SOURCES:
        category = "ignored_unsupported_dex_program"
        reason = "unsupported_dex_program"
    elif buy_like:
        category = "parser_not_detecting_buys"
        reason = "buy_like_transaction_not_parsed"
    elif wallet_native > 0:
        category = "ignored_sell"
        reason = "sell"
    elif wallet_involved:
        category = "ignored_missing_token_mint"
        reason = "missing_token_mint"
    else:
        category = "ignored_transfer_only"
        reason = "transfer_only"

    return TxCoverageResult(
        signature=signature,
        category=category,
        reason=reason,
        buy_like=buy_like,
        parsed_signal=None,
        timestamp=parsed_timestamp,
    )


def summarize_wallet_transactions(wallet_address: str, txs: list[dict[str, Any]], parser: TxParser | None = None) -> dict[str, Any]:
    parser = parser or TxParser()
    counts = Counter()
    latest_ts: datetime | None = None
    parsed_signals: list[ParsedSignal] = []
    for tx in txs:
        counts["raw_tx_fetched"] += 1
        classification = classify_transaction(wallet_address, tx, parser)
        counts[f"reason:{classification.category}"] += 1
        if classification.parsed_signal is not None:
            counts["parser_attempted"] += 1
            counts["parser_succeeded"] += 1
            counts["buy_signals"] += 1
            parsed_signals.append(classification.parsed_signal)
        else:
            counts["parser_attempted"] += 1
            counts["parser_failed"] += 1
            if classification.buy_like:
                counts["buy_like_transactions"] += 1
        if classification.timestamp and (latest_ts is None or classification.timestamp > latest_ts):
            latest_ts = classification.timestamp

    return {
        "wallet_address": wallet_address,
        "raw_tx_fetched": counts["raw_tx_fetched"],
        "parser_attempted": counts["parser_attempted"],
        "parser_succeeded": counts["parser_succeeded"],
        "parser_failed": counts["parser_failed"],
        "buy_like_transactions": counts["buy_like_transactions"],
        "buy_signals": counts["buy_signals"],
        "reason_counts": {k.replace("reason:", ""): v for k, v in counts.items() if k.startswith("reason:")},
        "latest_timestamp": latest_ts.isoformat() if latest_ts else "",
        "parsed_signals": parsed_signals,
    }


def infer_zero_signals_cause(report: dict[str, Any]) -> str:
    if report.get("total_active_wallets", 0) <= 0:
        return "wallet_list_empty_or_invalid"
    if report.get("api_errors", 0) > 0 and report.get("total_recent_transactions", 0) == 0:
        return "helius_api_issue"
    if report.get("total_recent_transactions", 0) == 0:
        return "no_wallet_activity"
    if report.get("forward_signals", 0) > 0:
        return "unknown"
    if report.get("parser_succeeded", 0) > 0:
        return "insufficient_runtime_window"
    if report.get("buy_like_transactions", 0) > 0:
        return "parser_not_detecting_buys"
    if report.get("filter_rejections", 0) > 0:
        return "filters_too_strict"
    return "unknown"
