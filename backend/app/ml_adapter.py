from __future__ import annotations

from dataclasses import asdict
from typing import Any

from trading_agent.agent import TradingAgent
from trading_agent.market import fetch_intraday, features
from trading_agent.risk import RiskEngine
from trading_agent.config import settings


def analyze_with_preserved_ml(symbol: str, equity: float) -> dict[str, Any]:
    """Train/evaluate the preserved V1 classifier on recent historical candles.

    Yahoo Finance availability and latency vary. This endpoint proposes only;
    it never submits orders to a broker.
    """
    raw = fetch_intraday(symbol, period="60d", interval="5m")
    featured = features(raw)
    if len(featured) < 100:
        raise ValueError("Not enough valid feature rows to train the V1 model.")
    agent = TradingAgent()
    agent.train(featured)
    proposal = agent.propose(symbol, featured)
    approved = RiskEngine().approve(proposal, equity)
    return {
        "proposal": asdict(proposal),
        "risk_approved_paper_order": asdict(approved) if approved else None,
        "training_rows": len(featured),
        "data_source": "Yahoo Finance via yfinance",
        "data_mode": "historical_research",
        "paper_trading": True,
        "configured_min_confidence": settings.min_confidence,
        "disclaimer": "Historical-data model output only. Not a live quote or investment recommendation."
    }
