from __future__ import annotations

import asyncio
import json
import os
import re
import struct
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode


SEGMENT_NAMES = {
    0: "IDX_I", 1: "NSE_EQ", 2: "NSE_FNO", 3: "NSE_CURRENCY",
    4: "BSE_EQ", 5: "MCX_COMM", 7: "BSE_CURRENCY", 8: "BSE_FNO",
}
SEGMENT_IDS = {value: key for key, value in SEGMENT_NAMES.items()}
REQUEST_CODES = {"ticker": 15, "quote": 17, "full": 21}


class DhanFeedError(RuntimeError):
    pass


def dhan_feed_configured() -> bool:
    return bool(os.getenv("DHAN_CLIENT_ID", "").strip() and
                os.getenv("DHAN_ACCESS_TOKEN", "").strip())


def parse_dhan_packet(packet: bytes) -> dict[str, Any]:
    """Parse documented DhanHQ v2 little-endian market-feed packets."""
    if len(packet) < 8:
        raise DhanFeedError("Dhan packet is shorter than the 8-byte header.")
    code = packet[0]
    message_length = struct.unpack_from("<H", packet, 1)[0]
    segment_id = packet[3]
    security_id = struct.unpack_from("<I", packet, 4)[0]
    result: dict[str, Any] = {
        "response_code": code,
        "message_length": message_length,
        "exchange_segment_id": segment_id,
        "exchange_segment": SEGMENT_NAMES.get(segment_id, f"UNKNOWN_{segment_id}"),
        "security_id": str(security_id),
    }

    if code in (2, 4, 8):
        required = {2: 16, 4: 50, 8: 162}[code]
        if len(packet) < required:
            raise DhanFeedError(f"Dhan packet type {code} is truncated.")
        result["last_price"] = float(struct.unpack_from("<f", packet, 8)[0])
        if code == 2:
            result["last_trade_time"] = struct.unpack_from("<i", packet, 12)[0]
        else:
            result["last_trade_quantity"] = struct.unpack_from("<h", packet, 12)[0]
            result["last_trade_time"] = struct.unpack_from("<i", packet, 14)[0]
            result["average_trade_price"] = float(struct.unpack_from("<f", packet, 18)[0])
            result["volume"] = struct.unpack_from("<i", packet, 22)[0]
            result["total_sell_quantity"] = struct.unpack_from("<i", packet, 26)[0]
            result["total_buy_quantity"] = struct.unpack_from("<i", packet, 30)[0]
            if code == 4:
                result.update({
                    "day_open": float(struct.unpack_from("<f", packet, 34)[0]),
                    "day_close": float(struct.unpack_from("<f", packet, 38)[0]),
                    "day_high": float(struct.unpack_from("<f", packet, 42)[0]),
                    "day_low": float(struct.unpack_from("<f", packet, 46)[0]),
                })
            else:
                result.update({
                    "open_interest": struct.unpack_from("<i", packet, 34)[0],
                    "open_interest_high": struct.unpack_from("<i", packet, 38)[0],
                    "open_interest_low": struct.unpack_from("<i", packet, 42)[0],
                    "day_open": float(struct.unpack_from("<f", packet, 46)[0]),
                    "day_close": float(struct.unpack_from("<f", packet, 50)[0]),
                    "day_high": float(struct.unpack_from("<f", packet, 54)[0]),
                    "day_low": float(struct.unpack_from("<f", packet, 58)[0]),
                })
        if result.get("last_price", 0) <= 0:
            raise DhanFeedError("Dhan returned a non-positive last traded price.")

    elif code == 5:
        if len(packet) < 12:
            raise DhanFeedError("Dhan OI packet is truncated.")
        result["open_interest"] = struct.unpack_from("<i", packet, 8)[0]
    elif code == 6:
        if len(packet) < 16:
            raise DhanFeedError("Dhan previous-close packet is truncated.")
        result["previous_close"] = float(struct.unpack_from("<f", packet, 8)[0])
        result["previous_open_interest"] = struct.unpack_from("<i", packet, 12)[0]
    elif code == 50:
        result["disconnect_code"] = struct.unpack_from("<h", packet, 8)[0] if len(packet) >= 10 else None
    else:
        result["unhandled"] = True

    timestamp = result.get("last_trade_time")
    if timestamp:
        result["exchange_time"] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return result


class DhanMarketFeed:
    def __init__(self):
        self.client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
        self.access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()

    def _url(self) -> str:
        if not self.client_id or not self.access_token:
            raise DhanFeedError("Configure DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN on the backend.")
        query = urlencode({
            "version": "2", "token": self.access_token,
            "clientId": self.client_id, "authType": "2",
        })
        return f"wss://api-feed.dhan.co?{query}"

    @staticmethod
    def _subscription_messages(instruments: list[dict[str, str]], mode: str):
        if mode not in REQUEST_CODES:
            raise DhanFeedError("Feed mode must be ticker, quote or full.")
        if not instruments or len(instruments) > 5000:
            raise DhanFeedError("Subscribe between 1 and 5000 instruments.")
        request_code = REQUEST_CODES[mode]
        for start in range(0, len(instruments), 100):
            batch = instruments[start:start + 100]
            yield {
                "RequestCode": request_code,
                "InstrumentCount": len(batch),
                "InstrumentList": [
                    {"ExchangeSegment": item["exchange_segment"],
                     "SecurityId": str(item["security_id"])}
                    for item in batch
                ],
            }

    async def stream(self, instruments: list[dict[str, str]], mode: str = "quote"):
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:
            raise DhanFeedError("Install the websockets package to enable Dhan live market data.") from exc

        async with connect(self._url(), ping_interval=20, ping_timeout=20,
                           open_timeout=12, close_timeout=5, max_size=1_048_576) as socket:
            for message in self._subscription_messages(instruments, mode):
                await socket.send(json.dumps(message))
            async for message in socket:
                if isinstance(message, str):
                    try:
                        body = json.loads(message)
                    except json.JSONDecodeError:
                        body = {"message": "Non-JSON text message received from Dhan."}
                    if body.get("type") == "error" or body.get("status") == "failure":
                        raise DhanFeedError("Dhan feed reported an error; check token, data subscription and instrument IDs.")
                    continue
                yield parse_dhan_packet(message)


class DhanFeedService:
    """Reconnectable live-feed consumer. It never sends broker orders."""

    def __init__(self, on_tick: Callable[[dict[str, Any]], Awaitable[None]] | None = None):
        self.client = DhanMarketFeed()
        self.on_tick = on_tick
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._instruments: list[dict[str, str]] = []
        self._mode = "quote"
        self._lookup: dict[tuple[str, str], dict[str, str]] = {}
        self._latest: dict[str, dict[str, Any]] = {}
        self._state: dict[str, Any] = {
            "running": False, "connected": False, "received_ticks": 0,
            "last_tick_at": None, "last_error": None,
        }

    def latest_tick(self, symbol: str, market: str = "stocks") -> dict[str, Any] | None:
        return self._latest.get(f"{market}:{symbol.strip().upper()}")

    def status(self) -> dict[str, Any]:
        return {
            **self._state,
            "configured": dhan_feed_configured(),
            "provider": "DhanHQ v2",
            "mode": self._mode,
            "instrument_count": len(self._instruments),
            "latest_ticks": list(self._latest.values())[-20:],
            "live_order_execution_enabled": False,
        }

    async def start(self, instruments: list[dict[str, str]], mode: str = "quote"):
        if not dhan_feed_configured():
            raise DhanFeedError("Dhan credentials are not configured on the backend.")
        # Validate and normalize all instrument identifiers before opening a socket.
        normalized = []
        for item in instruments:
            segment = str(item.get("exchange_segment", "")).upper()
            if segment not in SEGMENT_IDS:
                raise DhanFeedError(f"Unsupported Dhan exchange segment: {segment}")
            security_id = str(item.get("security_id", "")).strip()
            symbol = str(item.get("symbol", "")).strip().upper()
            if not security_id.isdigit() or not symbol:
                raise DhanFeedError("Each instrument needs a numeric security_id and a symbol.")
            normalized.append({
                "exchange_segment": segment, "security_id": security_id,
                "symbol": symbol, "market": str(item.get("market", "stocks")),
            })
        if not 1 <= len(normalized) <= 5000:
            raise DhanFeedError("Provide between 1 and 5000 instruments.")
        if mode not in REQUEST_CODES:
            raise DhanFeedError("Feed mode must be ticker, quote or full.")
        if self._task and not self._task.done():
            raise DhanFeedError("Dhan market feed is already running; stop it before restarting.")
        self._instruments = normalized
        self._mode = mode
        self._lookup = {
            (item["exchange_segment"], item["security_id"]): item for item in normalized
        }
        self._stop = asyncio.Event()
        self._state.update({"running": True, "connected": False, "last_error": None})
        self._task = asyncio.create_task(self._run())
        return self.status()

    async def stop(self):
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._state.update({"running": False, "connected": False})
        return self.status()

    async def _run(self):
        delay = 1
        try:
            while not self._stop.is_set():
                try:
                    async for packet in self.client.stream(self._instruments, self._mode):
                        if self._stop.is_set():
                            break
                        if packet.get("response_code") == 50:
                            raise DhanFeedError("Dhan market feed disconnected.")
                        if "last_price" not in packet:
                            continue
                        instrument = self._lookup.get((
                            packet["exchange_segment"], packet["security_id"]
                        ))
                        if not instrument:
                            continue
                        tick = {
                            **packet,
                            "symbol": instrument["symbol"],
                            "market": instrument["market"],
                            "received_at": datetime.now(timezone.utc).isoformat(),
                        }
                        key = f"{instrument['market']}:{instrument['symbol']}"
                        self._latest[key] = tick
                        delay = 1
                        self._state.update({
                            "connected": True,
                            "received_ticks": self._state["received_ticks"] + 1,
                            "last_tick_at": tick["received_at"],
                            "last_error": None,
                        })
                        if self.on_tick:
                            await self.on_tick(tick)
                    if self._stop.is_set():
                        break
                    raise DhanFeedError("Dhan market feed stream ended unexpectedly.")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._state["connected"] = False
                    safe_error = str(exc)
                    for secret in (self.client.access_token, self.client.client_id):
                        if secret:
                            safe_error = safe_error.replace(secret, "[redacted]")
                    safe_error = re.sub(r"(?i)(token=)[^&\\s]+", r"\\1[redacted]", safe_error)
                    if not isinstance(exc, DhanFeedError):
                        safe_error = (
                            f"{type(exc).__name__}: Dhan feed connection failed; "
                            "check credentials, data subscription, instrument IDs and network."
                        )
                    self._state["last_error"] = safe_error[:300]
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30)
        finally:
            self._state["running"] = False
            self._state["connected"] = False
