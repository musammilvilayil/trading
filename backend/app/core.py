from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
import os


class Market(str, Enum):
    stocks = "stocks"
    crypto = "crypto"
    forex = "forex"
    commodities = "commodities"


class Side(str, Enum):
    buy = "buy"
    sell = "sell"


@dataclass
class Settings:
    starting_capital: float = float(os.getenv("STARTING_CAPITAL_INR", "25000"))
    live_trading_enabled: bool = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"
    market_data_mode: str = os.getenv("MARKET_DATA_MODE", "mock")


settings = Settings()


@dataclass
class Position:
    symbol: str
    market: str
    quantity: float
    average_price: float
    stop_loss: float | None = None


@dataclass
class PaperPortfolio:
    initial_capital: float = settings.starting_capital
    cash: float = settings.starting_capital
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    orders: list[dict] = field(default_factory=list)

    @property
    def invested_value(self) -> float:
        return sum(p.quantity * p.average_price for p in self.positions.values())

    @property
    def equity(self) -> float:
        return self.cash + self.invested_value


portfolio = PaperPortfolio()


class RiskRejected(ValueError):
    pass


class RiskEngine:
    """Conservative paper-trading guardrails; not a guarantee against loss."""

    max_order_fraction = 0.10
    max_exposure_fraction = 0.50
    max_daily_loss_fraction = 0.02

    def approve(self, *, side: Side, quantity: float, price: float,
                stop_loss: float | None, book: PaperPortfolio) -> None:
        if quantity <= 0 or price <= 0:
            raise RiskRejected("Quantity and price must be positive.")
        notional = quantity * price
        if notional > book.initial_capital * self.max_order_fraction:
            raise RiskRejected("Order exceeds 10% of initial paper capital.")
        if side == Side.buy and notional > book.cash:
            raise RiskRejected("Insufficient paper cash.")
        if side == Side.buy and stop_loss is None:
            raise RiskRejected("A stop-loss is required for every simulated buy.")
        if side == Side.buy and stop_loss is not None and not 0 < stop_loss < price:
            raise RiskRejected("Buy stop-loss must be positive and below entry price.")
        if side == Side.sell:
            position = book.positions.get("")
            # The caller validates the symbol-specific holding.
        if book.equity < book.initial_capital * (1 - self.max_daily_loss_fraction):
            raise RiskRejected("Paper trading drawdown guard is active.")
        if side == Side.buy and book.invested_value + notional > book.initial_capital * self.max_exposure_fraction:
            raise RiskRejected("Portfolio exposure would exceed 50% of initial capital.")


class MockMarketData:
    """Clearly labelled deterministic sample candles; never represents live quotes."""

    def candles(self, symbol: str, limit: int = 60) -> list[dict]:
        base = 100.0 + (sum(ord(c) for c in symbol) % 150)
        rows = []
        for i in range(limit):
            close = base + i * 0.12 + ((i % 7) - 3) * 0.38
            rows.append({"time": i, "open": round(close - 0.2, 4),
                         "high": round(close + 0.7, 4), "low": round(close - 0.8, 4),
                         "close": round(close, 4), "volume": 1000 + i * 11})
        return rows


class StrategyEngine:
    def analyze(self, symbol: str, market: str, candles: list[dict]) -> dict:
        closes = [float(c["close"]) for c in candles]
        if len(closes) < 20:
            raise ValueError("At least 20 candles are required.")
        fast = sum(closes[-5:]) / 5
        slow = sum(closes[-20:]) / 20
        momentum = (closes[-1] / closes[-6] - 1) * 100
        if fast > slow * 1.001 and momentum > 0.15:
            signal: Literal["buy", "sell", "hold"] = "buy"
        elif fast < slow * 0.999 and momentum < -0.15:
            signal = "sell"
        else:
            signal = "hold"
        confidence = min(0.85, max(0.50, 0.50 + abs(fast / slow - 1) * 35 + abs(momentum) / 100))
        return {
            "symbol": symbol, "market": market, "signal": signal,
            "confidence": round(confidence, 3), "last_price": closes[-1],
            "indicators": {"sma_5": round(fast, 4), "sma_20": round(slow, 4),
                           "momentum_pct": round(momentum, 3)},
            "data_mode": "mock", "generated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Illustrative signal from mock data; not a live prediction."
        }


risk_engine = RiskEngine()
market_data = MockMarketData()
strategy_engine = StrategyEngine()


def place_paper_order(symbol: str, market: str, side: Side, quantity: float,
                      price: float, stop_loss: float | None) -> dict:
    risk_engine.approve(side=side, quantity=quantity, price=price,
                        stop_loss=stop_loss, book=portfolio)
    notional = quantity * price
    if side == Side.sell:
        held = portfolio.positions.get(symbol)
        if held is None or held.quantity < quantity:
            raise RiskRejected("Insufficient position quantity to sell.")
        portfolio.cash += notional
        held.quantity -= quantity
        if held.quantity <= 1e-12:
            del portfolio.positions[symbol]
    else:
        portfolio.cash -= notional
        existing = portfolio.positions.get(symbol)
        if existing:
            total_qty = existing.quantity + quantity
            existing.average_price = ((existing.quantity * existing.average_price) + notional) / total_qty
            existing.quantity = total_qty
            existing.stop_loss = stop_loss
        else:
            portfolio.positions[symbol] = Position(symbol, market, quantity, price, stop_loss)
    order = {"id": f"PAPER-{len(portfolio.orders) + 1:05d}", "symbol": symbol,
             "market": market, "side": side.value, "quantity": quantity,
             "price": price, "notional": round(notional, 2), "status": "filled_simulated",
             "created_at": datetime.now(timezone.utc).isoformat()}
    portfolio.orders.insert(0, order)
    return order
