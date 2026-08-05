# Data Collection

Stage 010 adds a read-only historical OHLCV candle collector for Bitcoin and
configured crypto assets. The collector uses the Stage 009 exchange adapter
contract and Stage 008 market data repository. It does not implement live
streaming, indicators, AI features, strategy logic, risk decisions, order
execution, or real exchange connectors.

## Scope

The collector supports these candle intervals:

- `1m`
- `5m`
- `15m`
- `1h`
- `4h`
- `1d`

Default configuration includes `BTC` and `USDT`, so `BTC/USDT` can be
backfilled through the sandbox adapter in deterministic tests.

## Flow

```text
configured symbols + interval
  -> validate asset universe and adapter metadata
  -> plan backfill windows
  -> fetch candles through ExchangeAdapter.candles()
  -> normalize timestamps to UTC
  -> store through MarketDataRepository
  -> record data-quality flags
```

No data collection code may call a real exchange directly. Real exchange calls,
when introduced by a later stage, must remain inside exchange adapter modules.

## Idempotency

`MarketDataRepository.add_candle_if_absent()` stores candles using the unique
key `(exchange, pair, interval, opened_at)`. Repeated backfills skip existing
records and report them as duplicates instead of inserting duplicate rows.

## Data Quality Flags

The collector detects:

- missing candle gaps
- duplicate provider candles
- timestamp/order problems
- out-of-window provider data
- unsupported intervals
- symbols outside the configured asset universe
- symbols unsupported by adapter metadata

Stored candle rows include data-quality metadata with provider name, provider
timestamp, flags, and a raw provider payload snapshot where practical.

## Scheduler

`plan_backfill_windows()` creates deterministic backfill windows from start/end
timestamps, interval, and page size. It normalizes timestamps to UTC and rejects
invalid ranges or unsupported intervals.

## Minimum-Risk Controls

The historical collector is read-only. Any attempt to submit an order through a
data job raises `UnsupportedOperationError`. Trading behavior remains behind the
Risk Management Engine and exchange adapter controls introduced in earlier
stages.

