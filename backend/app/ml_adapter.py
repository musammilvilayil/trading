from __future__ import annotations

from dataclasses import asdict
from threading import Lock
from typing import Any

import pandas as pd

from trading_agent.agent import TradingAgent
from trading_agent.market import features
from trading_agent.providers import fetch_market_candles, quote_to_inr_rate
from trading_agent.config import settings
from .brokers.dhan_feed import DhanHistoricalDataProvider, DhanFeedError


_DHAN_MODEL_CACHE: dict[str, tuple[str, TradingAgent]] = {}
_DHAN_MODEL_CACHE_LOCK = Lock()


def _analyze_frame(symbol: str, market: str, raw: pd.DataFrame,
                   provider: str, provider_symbol: str,
                   equity: float, fx_rate: float,
                   cache_key: str | None = None) -> dict[str, Any]:
    featured = features(raw)
    if len(featured) < 100:
        raise ValueError("Not enough valid feature rows to train the V1 model.")
    cache_hit = False
    if cache_key:
        latest_bar = featured.index[-1].isoformat()
        with _DHAN_MODEL_CACHE_LOCK:
            cached = _DHAN_MODEL_CACHE.get(cache_key)
            if cached and cached[0] == latest_bar:
                agent, cache_hit = cached[1], True
            else:
                agent = TradingAgent()
                agent.train(featured)
                _DHAN_MODEL_CACHE[cache_key] = (latest_bar, agent)
                if len(_DHAN_MODEL_CACHE) > 30:
                    oldest_key = next(iter(_DHAN_MODEL_CACHE))
                    if oldest_key != cache_key:
                        _DHAN_MODEL_CACHE.pop(oldest_key, None)
    else:
        agent = TradingAgent()
        agent.train(featured)
    proposal = agent.propose(symbol.upper(), featured)
    return {
        "proposal": asdict(proposal),
        "training_rows": len(featured),
        "instrument": {
            "symbol": symbol.upper(), "market": market,
            "provider_symbol": provider_symbol, "quote_currency": "INR",
            "provider": provider,
        },
        "data_source": provider,
        "data_mode": "historical_research",
        "latest_signal_candle_at": featured.index[-1].isoformat(),
        "model_cache_hit": cache_hit,
        "fx_to_inr": fx_rate,
        "entry_price_inr": round(proposal.entry * fx_rate, 6),
        "paper_trading": True,
        "configured_min_confidence": settings.min_confidence,
        "disclaimer": (
            "Historical-data model output only. The model score is not a calibrated probability "
            "of profit and does not guarantee future performance."
        ),
    }


def analyze_with_preserved_ml(symbol: str, market: str, equity: float) -> dict[str, Any]:
    """Yahoo Finance research path retained for manual analysis and backtesting."""
    instrument, raw = fetch_market_candles(symbol, market, period="60d", interval="5m")
    fx_rate = quote_to_inr_rate(instrument.quote_currency)
    return _analyze_frame(
        symbol, market, raw, instrument.provider, instrument.provider_symbol,
        equity, fx_rate,
    )


def analyze_with_dhan_history(symbol: str, market: str, equity: float,
                              security_id: str, exchange_segment: str) -> dict[str, Any]:
    """Dhan-native historical model path for autonomous NSE/BSE cash-equity mode."""
    if market != "stocks":
        raise ValueError("Dhan historical model path supports cash equities only.")
    provider = DhanHistoricalDataProvider()
    try:
        raw = provider.fetch_intraday(
            security_id=security_id, exchange_segment=exchange_segment,
            interval="5", lookback_days=60,
        )
    except DhanFeedError as exc:
        raise ValueError(str(exc)) from exc
    return _analyze_frame(
        symbol, market, raw, "DhanHQ v2 Historical API",
        f"{exchange_segment}:{security_id}", equity, 1.0,
        cache_key=f"{exchange_segment}:{security_id}",
    )
