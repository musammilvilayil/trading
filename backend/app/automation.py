from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable, Any

from .paper import PaperBroker, PaperTradeRejected


class PaperAutomation:
    """Opt-in autonomous paper-only worker. Process-local; stops on server restart."""

    def __init__(self, broker: PaperBroker, analyzer: Callable[..., dict[str, Any]]):
        self.broker = broker
        self.analyzer = analyzer
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._watchlist: list[dict[str, str]] = []
        self._interval = 300
        self._status: dict[str, Any] = {
            "running": False, "cycles": 0, "last_cycle_at": None,
            "last_error": None, "last_results": []
        }

    def status(self):
        return {**self._status, "watchlist": list(self._watchlist),
                "interval_seconds": self._interval,
                "execution_mode": "paper_only", "live_trading_enabled": False}

    async def start(self, watchlist: list[dict[str, str]], interval_seconds: int = 300):
        if self._task and not self._task.done():
            return self.status()
        if not watchlist or len(watchlist) > 10:
            raise ValueError("Watchlist must contain between 1 and 10 instruments.")
        if not 60 <= interval_seconds <= 3600:
            raise ValueError("Scan interval must be between 60 and 3600 seconds.")
        self._watchlist = watchlist
        self._interval = interval_seconds
        self._stop_event = asyncio.Event()
        self._status.update({"running": True, "last_error": None})
        self._task = asyncio.create_task(self._loop())
        return self.status()

    async def stop(self):
        if self._stop_event:
            self._stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=2)
            except asyncio.TimeoutError:
                self._task.cancel()
        self._status["running"] = False
        return self.status()

    async def _cycle(self):
        results = []
        for item in self._watchlist:
            symbol, market = item["symbol"], item["market"]
            try:
                equity = self.broker.portfolio()["equity"]
                report = await asyncio.to_thread(self.analyzer, symbol, market, equity)
                instrument = report["instrument"]
                if instrument["quote_currency"] != "INR":
                    results.append({"symbol": symbol, "status": "research_only",
                                    "reason": "Non-INR quote; FX-normalized paper risk sizing is not enabled."})
                    continue

                proposal = report["proposal"]
                price = float(proposal["entry"])
                tick = await asyncio.to_thread(self.broker.process_price, symbol, market, price)
                if tick.get("stop_triggered"):
                    results.append({"symbol": symbol, "status": "stop_loss_filled", "order": tick["order"]})
                    continue

                position = next((p for p in self.broker.portfolio()["positions"] if p["symbol"] == symbol.upper()), None)
                if proposal["action"] == "SELL" and position:
                    order = await asyncio.to_thread(
                        self.broker.place_order, symbol, market, "sell",
                        float(position["quantity"]), price, None, "autonomous_ml_exit"
                    )
                    results.append({"symbol": symbol, "status": "exit_filled", "order": order})
                elif proposal["action"] == "BUY" and not position and report["risk_approved_paper_order"]:
                    approved = report["risk_approved_paper_order"]
                    order = await asyncio.to_thread(
                        self.broker.place_order, symbol, market, "buy",
                        float(approved["quantity"]), float(approved["entry"]),
                        float(approved["stop"]), "autonomous_ml_entry"
                    )
                    results.append({"symbol": symbol, "status": "entry_filled", "order": order})
                else:
                    results.append({"symbol": symbol, "status": "no_action",
                                    "signal": proposal["action"], "has_position": bool(position)})
            except (PaperTradeRejected, ValueError) as exc:
                results.append({"symbol": symbol, "status": "rejected", "reason": str(exc)})
            except Exception as exc:
                results.append({"symbol": symbol, "status": "error", "reason": str(exc)})
        self._status.update({
            "cycles": self._status["cycles"] + 1,
            "last_cycle_at": datetime.now(timezone.utc).isoformat(),
            "last_results": results, "last_error": None
        })

    async def _loop(self):
        try:
            while self._stop_event and not self._stop_event.is_set():
                await self._cycle()
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status["last_error"] = str(exc)
        finally:
            self._status["running"] = False
