from __future__ import annotations

from base58 import b58decode


def normalize_wallet_address(address: str) -> str:
    return address.strip()


def is_valid_solana_address(address: str) -> bool:
    candidate = normalize_wallet_address(address)
    if not candidate:
        return False

    try:
        decoded = b58decode(candidate)
    except Exception:
        return False

    return len(decoded) == 32
