from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from config import settings
from src.historical_cache import cache_token_snapshot, load_latest_token_snapshot
from src.exit_rules import OhlcvCandle
from src.utils.http_client import HTTPClient


class TokenDataService:
    def __init__(self) -> None:
        self.http = HTTPClient(timeout=20.0)

    async def fetch_token_snapshot(self, token_mint: str) -> dict[str, Any]:
        cached = load_latest_token_snapshot(token_mint)
        if cached and cached.get("observed_at"):
            try:
                observed = datetime.fromisoformat(str(cached["observed_at"]))
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - observed).total_seconds() < 900:
                    return cached
            except Exception:
                pass

        market = await self._fetch_market_sources(token_mint)
        controls = await self._fetch_chain_controls(token_mint)

        snapshot = {
            "token_mint": token_mint,
            "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "liquidity_usd": market["liquidity_usd"],
            "price_usd": market["price_usd"],
            "token_age_minutes": market["token_age_minutes"],
            "holder_count": controls["holder_count"],
            "top_holder_percent": controls["top_holder_percent"],
            "top_10_holder_percent": controls["top_10_holder_percent"],
            "mint_revoked": controls["mint_revoked"],
            "freeze_revoked": controls["freeze_revoked"],
            "market_sources": market.get("market_sources", []),
        }
        try:
            cache_token_snapshot(token_mint, "merged", snapshot)
        except Exception as exc:
            logger.warning(f"Token snapshot cache write failed token={token_mint} error={exc}")
        return snapshot

    async def _fetch_market_sources(self, token_mint: str) -> dict[str, Any]:
        dexscreener = await self._fetch_dexscreener(token_mint)
        gecko = await self._fetch_geckoterminal(token_mint)

        liquidity_candidates = [x for x in [dexscreener["liquidity_usd"], gecko["liquidity_usd"]] if x > 0]
        price_candidates = [x for x in [dexscreener.get("price_usd", 0.0), gecko.get("price_usd", 0.0)] if x > 0]
        age_candidates = [x for x in [dexscreener["token_age_minutes"], gecko["token_age_minutes"]] if x > 0]

        return {
            "liquidity_usd": max(liquidity_candidates) if liquidity_candidates else 0.0,
            "price_usd": price_candidates[0] if price_candidates else 0.0,
            "token_age_minutes": min(age_candidates) if age_candidates else 0.0,
            "market_sources": [src for src in [dexscreener.get("source"), gecko.get("source")] if src],
        }

    async def _fetch_dexscreener(self, token_mint: str) -> dict[str, float | str]:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
        try:
            data = await self.http.get(url)
            pairs = data.get("pairs", []) if isinstance(data, dict) else []
            if not pairs:
                return {"liquidity_usd": 0.0, "token_age_minutes": 0.0, "price_usd": 0.0, "source": "dexscreener"}

            best = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
            liquidity_usd = float((best.get("liquidity") or {}).get("usd") or 0)
            price_usd = float(best.get("priceUsd") or best.get("price_usd") or 0.0)
            created_ms = float(best.get("pairCreatedAt") or 0)
            age_minutes = 0.0
            if created_ms > 0:
                created_dt = datetime.fromtimestamp(created_ms / 1000.0, tz=timezone.utc)
                age_minutes = max(0.0, (datetime.now(timezone.utc) - created_dt).total_seconds() / 60.0)
            return {"liquidity_usd": liquidity_usd, "token_age_minutes": age_minutes, "price_usd": price_usd, "source": "dexscreener"}
        except Exception as exc:
            logger.error(f"DexScreener fetch failed token={token_mint} error={exc}")
            return {"liquidity_usd": 0.0, "token_age_minutes": 0.0, "price_usd": 0.0, "source": "dexscreener"}

    async def _fetch_geckoterminal(self, token_mint: str) -> dict[str, float | str]:
        paths = [
            f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_mint}/pools",
            f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{token_mint}/pool",
        ]
        for url in paths:
            try:
                data = await self.http.get(url, headers={"Accept": "application/json"})
            except Exception:
                continue

            pools = data.get("data", []) if isinstance(data, dict) else []
            if isinstance(pools, dict):
                pools = [pools]
            if not pools:
                continue

            best = None
            best_liq = -1.0
            for pool in pools:
                attrs = pool.get("attributes") or {}
                try:
                    liq = float(attrs.get("reserve_in_usd") or 0.0)
                except (TypeError, ValueError):
                    liq = 0.0
                if liq > best_liq:
                    best = pool
                    best_liq = liq

            attrs = (best or {}).get("attributes") or {}
            pool_id = str((best or {}).get("id") or attrs.get("address") or attrs.get("pool_address") or "")
            if pool_id.startswith("solana_"):
                pool_id = pool_id.split("solana_", 1)[1]
            price_usd = 0.0
            for key in ("base_token_price_usd", "price_usd"):
                try:
                    price_usd = float(attrs.get(key) or 0.0)
                except (TypeError, ValueError):
                    price_usd = 0.0
                if price_usd > 0:
                    break

            age_minutes = 0.0
            created_at = attrs.get("pool_created_at") or attrs.get("created_at")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                    age_minutes = max(0.0, (datetime.now(timezone.utc) - created_dt).total_seconds() / 60.0)
                except Exception:
                    age_minutes = 0.0

            return {
                "liquidity_usd": float(attrs.get("reserve_in_usd") or 0.0),
                "token_age_minutes": age_minutes,
                "price_usd": price_usd,
                "pool_address": pool_id,
                "source": "geckoterminal",
            }

        logger.error(f"GeckoTerminal fetch failed token={token_mint} error=no_pool_data")
        return {"liquidity_usd": 0.0, "token_age_minutes": 0.0, "price_usd": 0.0, "pool_address": "", "source": "geckoterminal"}

    async def fetch_geckoterminal_historical_price(self, token_mint: str, unix_ts: int) -> float:
        market = await self._fetch_geckoterminal(token_mint)
        pool_address = str(market.get("pool_address") or "")
        if not pool_address:
            return 0.0

        url = f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}/ohlcv/day"
        params = {
            "aggregate": 1,
            "before_timestamp": int(unix_ts),
            "limit": 1,
            "currency": "usd",
        }
        try:
            data = await self.http.get(url, params=params, headers={"Accept": "application/json"})
            ohlcv = (((data.get("data") or {}).get("attributes") or {}).get("ohlcv_list") or [])
            if not ohlcv:
                return 0.0
            candle = ohlcv[0]
            if isinstance(candle, list) and len(candle) >= 5:
                price = float(candle[4] or 0.0)
                return price
            return 0.0
        except Exception as exc:
            logger.error(f"GeckoTerminal historical price fetch failed token={token_mint} error={exc}")
            return 0.0

    async def fetch_ohlcv_candles(
        self,
        token_mint: str,
        time_from: int,
        time_to: int,
        interval: str = "1m",
    ) -> list[OhlcvCandle]:
        birdeye = await self._fetch_birdeye_ohlcv(token_mint, time_from, time_to, interval)
        if birdeye:
            return birdeye

        gecko = await self._fetch_geckoterminal_ohlcv(token_mint, time_from, time_to)
        return gecko

    async def _fetch_birdeye_ohlcv(
        self,
        token_mint: str,
        time_from: int,
        time_to: int,
        interval: str,
    ) -> list[OhlcvCandle]:
        if not settings.BIRDEYE_API_KEY:
            return []
        url = "https://public-api.birdeye.so/defi/v3/ohlcv"
        params = {
            "address": token_mint,
            "type": interval,
            "time_from": int(time_from),
            "time_to": int(time_to),
            "currency": "usd",
            "ui_amount_mode": "raw",
        }
        headers = {"X-API-KEY": settings.BIRDEYE_API_KEY, "x-chain": "solana"}
        try:
            data = await self.http.get(url, params=params, headers=headers)
        except Exception as exc:
            logger.error(f"Birdeye OHLCV fetch failed token={token_mint} error={exc}")
            return []
        rows = []
        payload = data.get("data") if isinstance(data, dict) else data
        if isinstance(payload, dict):
            rows = payload.get("items") or payload.get("candles") or []
        elif isinstance(payload, list):
            rows = payload
        return self._normalize_ohlcv_rows(rows)

    async def _fetch_geckoterminal_ohlcv(
        self,
        token_mint: str,
        time_from: int,
        time_to: int,
    ) -> list[OhlcvCandle]:
        market = await self._fetch_geckoterminal(token_mint)
        pool_address = str(market.get("pool_address") or "")
        if not pool_address:
            return []

        url = f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}/ohlcv/day"
        params = {
            "aggregate": 1,
            "before_timestamp": int(time_to),
            "limit": 20,
            "currency": "usd",
        }
        try:
            data = await self.http.get(url, params=params, headers={"Accept": "application/json"})
        except Exception as exc:
            logger.error(f"GeckoTerminal OHLCV fetch failed token={token_mint} error={exc}")
            return []
        ohlcv = (((data.get("data") or {}).get("attributes") or {}).get("ohlcv_list") or [])
        candles = []
        for row in ohlcv:
            if not isinstance(row, list) or len(row) < 6:
                continue
            try:
                candles.append(
                    OhlcvCandle(
                        unix_time=int(row[0] or 0),
                        open=float(row[1] or 0.0),
                        high=float(row[2] or 0.0),
                        low=float(row[3] or 0.0),
                        close=float(row[4] or 0.0),
                        volume=float(row[5] or 0.0),
                    )
                )
            except (TypeError, ValueError):
                continue
        candles = [c for c in candles if time_from <= c.unix_time <= time_to]
        candles.sort(key=lambda c: c.unix_time)
        return candles

    @staticmethod
    def _normalize_ohlcv_rows(rows: list[Any]) -> list[OhlcvCandle]:
        candles: list[OhlcvCandle] = []
        for row in rows:
            if isinstance(row, list) and len(row) >= 6:
                try:
                    candles.append(
                        OhlcvCandle(
                            unix_time=int(row[0] or 0),
                            open=float(row[1] or 0.0),
                            high=float(row[2] or 0.0),
                            low=float(row[3] or 0.0),
                            close=float(row[4] or 0.0),
                            volume=float(row[5] or 0.0),
                        )
                    )
                except (TypeError, ValueError):
                    continue
                continue
            if isinstance(row, dict):
                try:
                    unix_time = int(row.get("unixTime") or row.get("time") or row.get("unix_time") or 0)
                    candles.append(
                        OhlcvCandle(
                            unix_time=unix_time,
                            open=float(row.get("o") or row.get("open") or 0.0),
                            high=float(row.get("h") or row.get("high") or 0.0),
                            low=float(row.get("l") or row.get("low") or 0.0),
                            close=float(row.get("c") or row.get("close") or 0.0),
                            volume=float(row.get("v") or row.get("volume") or 0.0),
                        )
                    )
                except (TypeError, ValueError):
                    continue
        candles = [c for c in candles if c.unix_time > 0 and c.close > 0]
        candles.sort(key=lambda c: c.unix_time)
        return candles

    async def _fetch_chain_controls(self, token_mint: str) -> dict[str, Any]:
        rpc_url = settings.HELIUS_RPC_URL or (
            f"https://mainnet.helius-rpc.com/?api-key={settings.HELIUS_API_KEY}" if settings.HELIUS_API_KEY else ""
        )

        if not rpc_url:
            return {
                "holder_count": 0,
                "top_holder_percent": 100.0,
                "top_10_holder_percent": 100.0,
                "mint_revoked": False,
                "freeze_revoked": False,
            }

        try:
            account_info_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [token_mint, {"encoding": "jsonParsed"}],
            }
            largest_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "getTokenLargestAccounts",
                "params": [token_mint],
            }
            supply_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "getTokenSupply",
                "params": [token_mint],
            }

            account_info = await self.http.post(rpc_url, json=account_info_payload)
            largest = await self.http.post(rpc_url, json=largest_payload)
            supply = await self.http.post(rpc_url, json=supply_payload)

            info = (((account_info.get("result") or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get(
                "info", {}
            )
            mint_authority = info.get("mintAuthority")
            freeze_authority = info.get("freezeAuthority")

            largest_values = ((largest.get("result") or {}).get("value") or [])
            supply_amount = float((((supply.get("result") or {}).get("value") or {}).get("uiAmount") or 0.0))

            top_holder_percent = 100.0
            top_10_holder_percent = 100.0
            holder_count_proxy = 0
            if largest_values:
                non_zero_accounts = [row for row in largest_values if float(row.get("uiAmount") or 0) > 0]
                holder_count_proxy = len(non_zero_accounts)
                top_balance = float(non_zero_accounts[0].get("uiAmount") or 0) if non_zero_accounts else 0.0
                if supply_amount > 0:
                    top_holder_percent = min(100.0, max(0.0, (top_balance / supply_amount) * 100.0))
                    top_10_balance = sum(float(row.get("uiAmount") or 0.0) for row in non_zero_accounts[:10])
                    top_10_holder_percent = min(100.0, max(0.0, (top_10_balance / supply_amount) * 100.0))

            return {
                "holder_count": holder_count_proxy,
                "top_holder_percent": top_holder_percent,
                "top_10_holder_percent": top_10_holder_percent,
                "mint_revoked": mint_authority is None,
                "freeze_revoked": freeze_authority is None,
            }
        except Exception as exc:
            logger.error(f"Chain control fetch failed token={token_mint} error={exc}")
            return {
                "holder_count": 0,
                "top_holder_percent": 100.0,
                "top_10_holder_percent": 100.0,
                "mint_revoked": False,
                "freeze_revoked": False,
            }
