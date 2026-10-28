"""Optional Telegram alerts (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def notify(text: str) -> None:
    log.info(text)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        import requests

        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text[:4000]}, timeout=10)
    except Exception as exc:  # alerts must never break trading
        log.warning("telegram notify failed: %s", exc)
