from __future__ import annotations

from loguru import logger

from config import settings
from src.utils.http_client import HTTPClient


class TelegramNotifier:
    def __init__(self) -> None:
        self.enabled = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
        self.http = HTTPClient(timeout=10.0)

    async def send(self, text: str) -> None:
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}
        try:
            await self.http.post(url, json=payload)
        except Exception as exc:
            logger.error(f"Telegram notify failed: {exc}")
