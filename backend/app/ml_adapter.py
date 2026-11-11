from __future__ import annotations

from dataclasses import asdict
from typing import Any

from trading_agent.agent import TradingAgent
from trading_agent.market import features
from trading_agent.providers import fetch_market_candles, quote_to_inr_rate
from trading_agent.config import settings


def analyze_with_preserved_ml(symbol: str, market: str, equity: float) -> dict[str, Any]:
    """Train the preserved V1 classifier on recent provider history; proposal only."""
    instrument, raw = fetch_market_candles(symbol, market, period="60d", interval="5m")
    featured = features(raw)
    if len(featured) < 100:
        raise ValueError("Not enough valid feature rows to train the V1 model.")
    agent = TradingAgent()
    agent.train(featured)
    proposal = agent.propose(instrument.provider_symbol, featured)
    fx_rate = quote_to_inr_rate(instrument.quote_currency)
    return {
        "proposal": asdict(proposal),
        "training_rows": len(featured),
        "instrument": asdict(instrument),
        "data_source": instrument.provider,
        "data_mode": "historical_research",
        "fx_to_inr": fx_rate,
        "entry_price_inr": round(proposal.entry * fx_rate, 6),
        "paper_trading": True,
        "configured_min_confidence": settings.min_confidence,
        "disclaimer": "Historical-data model output only. FX uses a recent provider close; not a live quote or investment recommendation."
    }
