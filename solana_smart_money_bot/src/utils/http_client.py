from __future__ import annotations

import httpx


class HTTPClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        resp = await self._client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def post(self, url: str, json: dict | None = None, headers: dict | None = None) -> dict:
        resp = await self._client.post(url, json=json, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
