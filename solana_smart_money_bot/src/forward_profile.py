from __future__ import annotations

from typing import Any


FORWARD_TESTING_PROFILE: dict[str, Any] = {
    "MIN_WHALE_CONFIRMATIONS": 1,
    "MIN_LIQUIDITY_USD": 2000.0,
    "MIN_TOKEN_AGE_MINUTES": 5.0,
    "MIN_TOKEN_RISK_SCORE": 50.0,
    "MIN_COMBINED_WALLET_SCORE": 55.0,
    "MAX_TOP_HOLDER_PERCENT": 40.0,
    "MAX_TOP_10_HOLDER_PERCENT": 80.0,
    "MAX_OPEN_POSITIONS": 3,
    "MAX_WALLET_EXPOSURE_INR": 15000.0,
    "MAX_TRADES_PER_DAY": 10,
    "MAX_NEW_TRADES_PER_HOUR": 10,
    "MAX_NEW_TRADES_PER_DAY": 20,
}


def apply_forward_testing_profile(settings_obj: Any) -> dict[str, Any]:
    """Apply a softer discovery profile without changing live-trading safety.

    This is intended only for paper / forward testing so the bot can surface
    more candidate signals and produce enough diagnostic volume to study.
    """

    settings_obj.FORWARD_TESTING_MODE = True
    settings_obj.EXECUTION_MODE = "paper"
    settings_obj.PAPER_TRADING = True
    settings_obj.EXECUTOR = "paper"

    for key, value in FORWARD_TESTING_PROFILE.items():
        setattr(settings_obj, key, value)

    return dict(FORWARD_TESTING_PROFILE)
