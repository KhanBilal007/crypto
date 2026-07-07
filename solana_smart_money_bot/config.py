from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    HELIUS_API_KEY: str = ""
    HELIUS_RPC_URL: str = ""
    JUPITER_BASE_URL: str = "https://api.jup.ag"
    MONITOR_MODE: Literal["polling", "websocket"] = "polling"
    ENABLE_DASHBOARD: bool = True
    ENABLE_TELEGRAM_SERVICE: bool = True
    DASHBOARD_HOST: str = "127.0.0.1"
    DASHBOARD_PORT: int = 8090

    BIRDEYE_API_KEY: str = ""

    EXECUTION_MODE: Literal["paper", "trojan", "jupiter_live"] = "paper"
    LIVE_TRADING_ENABLED: bool = False
    MANUAL_APPROVAL_REQUIRED: bool = True
    EMERGENCY_STOP: bool = False
    SHADOW_MODE: bool = False
    FORWARD_TESTING_MODE: bool = True

    # Legacy compatibility knobs. These are synchronized from EXECUTION_MODE at startup.
    PAPER_TRADING: bool = True
    EXECUTOR: Literal["paper", "jupiter", "trojan"] = "paper"

    PRIVATE_KEY: str = ""

    EXTERNAL_EXECUTION_ENABLED: bool = False
    COMMAND_BRIDGE_URL: str = ""
    COMMAND_BRIDGE_TOKEN: str = ""
    COMMAND_RELAY_MAX_RETRIES: int = 3
    TROJAN_BUY_TEMPLATE: str = "/buy {token_mint} {amount_sol}"
    TROJAN_SELL_TEMPLATE: str = "/sell {token_mint} {sell_percent}"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    SOL_INR_PRICE: float = 12000.0

    STARTING_CAPITAL_INR: float = 100000.0
    MAX_TRADE_SIZE_INR: float = 300.0
    MAX_TRADE_INR: float = 300.0
    MIN_TRADE_INR: float = 300.0
    MAX_CONFIDENCE_TRADE_INR: float = 300.0
    MAX_OPEN_POSITIONS: int = 1
    MAX_WALLET_EXPOSURE_INR: float = 5000.0
    DAILY_LOSS_LIMIT_INR: float = 500.0
    MAX_TRADES_PER_DAY: int = 5
    MAX_LOSS_STREAK: int = 2
    STOP_LOSS_PERCENT: float = 10.0
    TAKE_PROFIT_PERCENT: float = 25.0
    TAKE_PROFIT_PERCENT_2: float = 50.0
    TP1_SELL_PERCENT: float = 50.0
    TP2_SELL_PERCENT: float = 25.0
    TRAILING_STOP_PERCENT: float = 12.0
    MIN_WHALE_CONFIRMATIONS: int = 2
    CONFIRMATION_WINDOW_MINUTES: int = 10
    MIN_LIQUIDITY_USD: float = 10000.0
    MIN_TOKEN_AGE_MINUTES: float = 30.0
    REQUIRE_MINT_AUTHORITY_DISABLED: bool = True
    REQUIRE_FREEZE_AUTHORITY_DISABLED: bool = True
    MAX_TOP_HOLDER_PERCENT: float = 25.0
    MAX_TOP_10_HOLDER_PERCENT: float = 70.0
    MIN_TOKEN_RISK_SCORE: float = 70.0
    MIN_COMBINED_WALLET_SCORE: float = 75.0
    MAX_SLIPPAGE_BPS: int = 300
    MAX_PRICE_IMPACT_BPS: int = 500
    SLIPPAGE_BPS: int = 300
    PRIORITY_FEE_LEVEL: Literal["low", "medium", "high"] = "medium"
    TX_CONFIRMATION_TIMEOUT_SECONDS: int = 60
    TX_CONFIRMATION_POLL_INTERVAL_SECONDS: int = 3
    MAX_EXECUTION_RETRIES: int = 2

    MAX_TRACKED_WALLETS: int = 10
    RECENT_PERFORMANCE_DAYS: int = 30
    OUTCOME_EMA_ALPHA: float = 0.35
    REPLACE_DISABLED_WALLETS: bool = True
    CANDIDATE_WALLETS: str = ""

    WALLET_TRADE_COOLDOWN_MINUTES: int = 5
    TOKEN_TRADE_COOLDOWN_MINUTES: int = 10

    # New live guards
    MAX_SIGNAL_AGE_SECONDS: int = 90
    MAX_NEW_TRADES_PER_HOUR: int = 6
    MAX_NEW_TRADES_PER_DAY: int = 20
    MAX_CONSECUTIVE_LOSSES: int = 4

    WALLET_POLL_SECONDS: int = 8
    POSITION_POLL_SECONDS: int = 7

    WHALE_WALLETS: str = Field(default="")

    BASE_DIR: Path = Path(__file__).resolve().parent
    DB_PATH: Path = BASE_DIR / "data" / "bot.db"
    CONTROL_STATE_PATH: Path = BASE_DIR / "data" / "operator_controls.json"

    @model_validator(mode="after")
    def _validate_live_mode(self) -> "Settings":
        mode = self.EXECUTION_MODE

        if mode == "paper":
            self.PAPER_TRADING = True
            self.EXECUTOR = "paper"
        elif mode == "trojan":
            self.PAPER_TRADING = False
            self.EXECUTOR = "trojan"
        elif mode == "jupiter_live":
            self.PAPER_TRADING = False
            self.EXECUTOR = "jupiter"
        else:  # pragma: no cover - defensive fallback
            raise ValueError(f"Unsupported EXECUTION_MODE={mode}")

        if self.SLIPPAGE_BPS > self.MAX_SLIPPAGE_BPS:
            raise ValueError("SLIPPAGE_BPS cannot exceed MAX_SLIPPAGE_BPS")

        self.MAX_TRADE_INR = float(self.MAX_TRADE_SIZE_INR)
        self.MAX_CONFIDENCE_TRADE_INR = min(float(self.MAX_CONFIDENCE_TRADE_INR), float(self.MAX_TRADE_SIZE_INR))

        if mode != "paper":
            if not self.LIVE_TRADING_ENABLED:
                raise ValueError(
                    f"EXECUTION_MODE={mode} requires LIVE_TRADING_ENABLED=true before the bot will start live trading"
                )
            if self.EMERGENCY_STOP:
                raise ValueError("EMERGENCY_STOP=true blocks live execution")
            if not self.PRIVATE_KEY.strip():
                raise ValueError("Live execution requires PRIVATE_KEY to be configured")

        if mode == "jupiter_live" and not self.LIVE_TRADING_ENABLED:
            raise ValueError("EXECUTION_MODE=jupiter_live requires LIVE_TRADING_ENABLED=true")

        if mode == "trojan" and self.LIVE_TRADING_ENABLED and (not self.EXTERNAL_EXECUTION_ENABLED or not self.COMMAND_BRIDGE_URL.strip()):
            raise ValueError("EXECUTION_MODE=trojan requires EXTERNAL_EXECUTION_ENABLED=true and COMMAND_BRIDGE_URL")

        return self


settings = Settings()
