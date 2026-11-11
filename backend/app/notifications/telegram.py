from __future__ import annotations

import os


class TelegramNotConfiguredError(RuntimeError):
    pass


class TelegramDeliveryError(RuntimeError):
    pass


def telegram_status() -> dict:
    return {
        "provider": "Telegram Bot API",
        "configured": bool(
            os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            and os.getenv("TELEGRAM_CHAT_ID", "").strip()
        ),
        "automatic_scheduling_enabled": False,
    }


async def send_telegram_message(message: str) -> dict:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise TelegramNotConfiguredError(
            "Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID on the backend."
        )
    if not message.strip() or len(message) > 4000:
        raise TelegramDeliveryError("Telegram report must contain between 1 and 4000 characters.")

    import httpx

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
            )
        if response.status_code != 200:
            raise TelegramDeliveryError(
                f"Telegram returned HTTP {response.status_code}; check bot access and chat ID."
            )
        body = response.json()
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise TelegramDeliveryError("Telegram did not accept the daily report.")
        return {"sent": True, "message_id": body.get("result", {}).get("message_id")}
    except TelegramDeliveryError:
        raise
    except Exception as exc:
        raise TelegramDeliveryError("Telegram report delivery failed; check backend connectivity.") from exc
