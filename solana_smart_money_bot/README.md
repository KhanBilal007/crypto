# Solana Smart Money Bot (MVP)

Risk-controlled Solana smart-money bot for personal automation experiments.

## Safety First
- Paper trading is enabled by default.
- No private key is hardcoded.
- Keep `.env` private.
- This is not financial advice.
- Do not use for market manipulation.
- Live execution is blocked unless `EXECUTION_MODE` is explicitly set to a live mode and `LIVE_TRADING_ENABLED=true`.
- Manual approval is enabled by default for live execution.
- Emergency stop and sell-all controls are available in the dashboard and Telegram admin commands.

## Current Data Mode
- Whale transaction feed: live polling from Helius Enhanced Transactions API.
- Token market/liquidity: live from DexScreener.
- Mint/freeze + holder concentration proxy: live from Helius RPC.
- Execution: paper by default, with optional external-bot command relay.

## Install
```bash
cd /Users/idriskhan/Documents/crypto/solana_smart_money_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Required `.env` for Live Signals
```bash
HELIUS_API_KEY=...
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=...
WHALE_WALLETS=wallet1,wallet2,wallet3
EXECUTION_MODE=paper
LIVE_TRADING_ENABLED=false
MANUAL_APPROVAL_REQUIRED=true
PRIVATE_KEY=
```

## Run
```bash
python main.py
```

## Executor Modes
- Paper (safe default):
```bash
EXECUTION_MODE=paper
LIVE_TRADING_ENABLED=false
```
- Jupiter quote skeleton:
```bash
EXECUTION_MODE=jupiter_live
LIVE_TRADING_ENABLED=false
```
- Trojan/existing bot command mode:
```bash
EXECUTION_MODE=trojan
LIVE_TRADING_ENABLED=false
```

## Fast Existing-Bot Routing (Trojan Adapter)
This project can relay generated buy/sell commands to your own command bridge (for Telegram automation/userbot flow).

Set:
```bash
EXTERNAL_EXECUTION_ENABLED=true
COMMAND_BRIDGE_URL=https://your-bridge-endpoint
COMMAND_BRIDGE_TOKEN=optional_token
TROJAN_BUY_TEMPLATE=/buy {token_mint} {amount_sol}
TROJAN_SELL_TEMPLATE=/sell {token_mint} {sell_percent}
```

The bot emits commands like:
- `/buy <token_mint> <amount_sol>`
- `/sell <token_mint> <sell_percent>`

## Strategy Defaults
- Starting capital: ₹10,000
- Max trade: ₹500
- Min trade: ₹300
- Max open positions: 2
- Daily loss limit: ₹1,000
- Stop loss: 10%
- Take profit: 25%
- Confirmations: 2 wallets within 10 minutes

## Important Notes
- Telegram bot-to-bot delivery can be limited by Telegram platform rules, so use your own bridge/userbot automation path for reliable routing.
- Live Jupiter execution is gated and only enabled when the live flags and wallet config are present.
- Trailing stop remains supported in the position loop.

## Disclaimer
Use only with funds you can afford to lose. Low-cap tokens are high risk.

## Ops Report
Run this anytime to view MVP health metrics:
```bash
python ops_report.py
```

Shows:
- active/standby/disabled wallets
- wallet score threshold pressure
- 24h signal and trade activity
- open positions and daily PnL vs daily loss limit
- current monitor/executor config snapshot

## Admin Control Center
Open:
- `http://localhost:8080/admin`

Use it to:
- review pending live-trade intents
- approve or reject a specific intent
- toggle emergency stop
- request or clear sell-all

## Testing and Rollout
### Test now
Run in paper mode first:
```bash
python -m unittest discover -s tests -v
python main.py
```

What to verify in paper mode:
- the bot starts with `EXECUTION_MODE=paper`
- pending trades appear when manual approval is required
- the admin page shows the pending queue
- approving a pending trade moves it into execution
- emergency stop blocks new buy intents
- sell-all closes open positions

### Test later, only when ready for real money
Use a fresh hot wallet, not your main wallet, and keep size tiny.
Do not test live until all of these are true:
- `EXECUTION_MODE=jupiter_live`
- `LIVE_TRADING_ENABLED=true`
- `PRIVATE_KEY` is set to the fresh hot wallet only
- `MANUAL_APPROVAL_REQUIRED=true`
- `EMERGENCY_STOP=false`
- live funding limit and trade limits are set conservatively

Recommended live smoke test sequence:
1. Start in paper mode and confirm the admin panel works.
2. Switch to live mode in a staging environment first.
3. Approve one tiny test trade manually.
4. Confirm the transaction appears in the wallet and the audit log.
5. Trigger a sell-all on a tiny position and confirm exit handling.



## Dashboard
Run local dashboard:
```bash
uvicorn dashboard:app --host 0.0.0.0 --port 8080 --reload
```
Open:
- `http://localhost:8080/`
- `http://localhost:8080/api/metrics`

## Telegram Bot
1. Set `TELEGRAM_BOT_TOKEN` in `.env`.
2. Run command bot:
```bash
python telegram_bot.py
```
Supported commands:
- `/status`
- `/wallets`
- `/positions`
- `/pending`
- `/approve <intent_id>`
- `/reject <intent_id>`
- `/emergency_on`
- `/emergency_off`
- `/sellall`

## Telegram Alerts
Set both in `.env`:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Then `main.py` sends alerts for:
- buy opened
- TP1/TP2 hits
- full exits
- daily loss halt
- pending approval alerts
- admin-control actions


## Run Everything
Run bot + dashboard + telegram command bot together:
```bash
python run_all.py
```

Notes:
- Dashboard runs on `http://localhost:8080`
- Admin panel runs on `http://localhost:8080/admin`
- Telegram service auto-starts only if `TELEGRAM_BOT_TOKEN` is set
- Crashed services auto-restart every 3 seconds


## Auto-Discover Candidate Wallets
Set `BIRDEYE_API_KEY` in `.env`, then run:
```bash
python discover_candidates.py
```

This prints a ranked wallet list and a ready-to-paste `CANDIDATE_WALLETS=...` line.
