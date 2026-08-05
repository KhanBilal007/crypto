# Configuration

Stage 006 adds typed configuration for ABTP environment profiles. Configuration
is environment-driven, deterministic in tests, and fail-closed for unsafe live
settings.

## Profiles

Supported profiles:

- `research`: non-trading analysis and local research data.
- `backtest`: deterministic historical replay.
- `paper`: simulated trading path with no live execution.
- `live`: real venue intent profile, validation only in this stage.

The default profile is `paper`. `ABTP_TRADING_MODE=live` does not implicitly
select the live profile; live requires `ABTP_PROFILE=live`.

## Live Controls

The live profile is invalid unless all required controls are present:

- `ABTP_PROFILE=live`
- `SAFE_MODE=false`
- `ABTP_ENABLE_LIVE_TRADING=true`
- `ABTP_LIVE_MANUAL_CONFIRMATION=I_UNDERSTAND_ABTP_LIVE_RISK`
- `ABTP_LIVE_EXCHANGE_API_KEY` is present
- `ABTP_LIVE_EXCHANGE_API_SECRET` is present

Even when a live profile validates, Stage 006 still reports
`RuntimeSettings.can_execute_live == False` because live order execution is not
implemented or enabled in this stage.

## Secrets

Configuration code must never print, log, or store secret values in plaintext.
Secrets are represented by `SecretRef` objects that contain only:

- the environment variable name
- whether a non-empty value was present
- a masked display value

Exchange adapters introduced in later stages may read their own credentials
from environment variables, but unit tests must remain credential-free.

## Market Inputs

The following settings define the initial Bitcoin-centered configuration
vocabulary without introducing trading parameters:

- `ABTP_EXCHANGES`
- `ABTP_ASSET_UNIVERSE`
- `ABTP_CANDLE_INTERVALS`
- `ABTP_DATA_PROVIDERS`
- `ABTP_DATABASE_URL`
- `ABTP_MAKER_FEE_BPS`
- `ABTP_TAKER_FEE_BPS`
- `ABTP_SLIPPAGE_CEILING_BPS`

Defaults focus on spot markets and the `BTC/USDT` asset universe with `1m`,
`5m`, `15m`, `1h`, `4h`, and `1d` candle intervals. Leverage, margin, futures,
and options remain disabled until a later explicit stage.

`ABTP_DATABASE_URL` defaults to a local SQLite database:
`sqlite:///./abtp.sqlite3`.

## Risk Limits

Configured risk limits are validated before settings are accepted:

- `ABTP_MAX_ORDER_NOTIONAL` must be greater than 0.
- `ABTP_MAX_POSITION_PERCENT` must be greater than 0 and at most 1.
- `ABTP_MAX_DAILY_LOSS_PERCENT` must be between 0 and 1.
- `ABTP_MAX_OPEN_ORDERS` must be greater than 0.
- Fee assumptions cannot be negative.
- `ABTP_SLIPPAGE_CEILING_BPS` must be between 0 and 10000.

All future order paths must still pass through the Risk Management Engine. These
configuration checks are not a substitute for order-level risk decisions.

## Programmatic Use

```python
from abtp.config import load_settings

settings = load_settings()
```

Tests should pass an explicit mapping:

```python
settings = load_settings({"ABTP_PROFILE": "paper"})
```

Passing a mapping keeps tests deterministic and independent of local shell
configuration.
