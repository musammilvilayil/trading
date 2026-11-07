from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import yfinance as yf

MarketName = Literal["stocks", "crypto", "forex", "commodities"]


@dataclass(frozen=True)
class Instrument:
    symbol: str
    market: MarketName
    provider_symbol: str
    quote_currency: str
    provider: str = "Yahoo Finance"


def resolve_instrument(symbol: str, market: str) -> Instrument:
    market = market.lower()
    if market not in {"stocks", "crypto", "forex", "commodities"}:
        raise ValueError("Unsupported market category.")
    raw = symbol.strip().upper()
    if not raw or len(raw) > 32:
        raise ValueError("A valid instrument symbol is required.")

    if market == "stocks":
        provider_symbol = raw if "." in raw else f"{raw}.NS"
        quote = "INR" if provider_symbol.endswith((".NS", ".BO")) else "USD"
    elif market == "crypto":
        provider_symbol = raw if "-" in raw else f"{raw}-USD"
        quote = provider_symbol.rsplit("-", 1)[-1]
    elif market == "forex":
        provider_symbol = raw if raw.endswith("=X") else f"{raw}=X"
        pair = provider_symbol.replace("=X", "")
        if len(pair) != 6:
            raise ValueError("Forex symbols should be six-letter pairs, e.g. EURUSD.")
        quote = pair[-3:]
    else:
        provider_symbol = raw
        quote = "USD"
    return Instrument(raw, market, provider_symbol, quote)


def fetch_market_candles(symbol: str, market: str, period: str = "60d",
                         interval: str = "1d") -> tuple[Instrument, pd.DataFrame]:
    instrument = resolve_instrument(symbol, market)
    frame = yf.download(instrument.provider_symbol, period=period, interval=interval,
                        auto_adjust=True, progress=False, threads=False)
    if frame.empty:
        raise ValueError(f"No candles returned for {instrument.provider_symbol}.")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Provider response is missing columns: {missing}")
    frame = frame[required].apply(pd.to_numeric, errors="coerce").dropna()
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame[(frame["High"] >= frame["Low"]) & (frame["Volume"] >= 0)]
    if len(frame) < 30:
        raise ValueError("Provider returned fewer than 30 valid candles.")
    return instrument, frame


def quote_to_inr_rate(currency: str) -> float:
    """Fetch a recent provider FX close; fail closed if the conversion is unavailable."""
    currency = currency.strip().upper()
    if currency == "INR":
        return 1.0
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("Unsupported quote currency for INR conversion.")
    pair = f"{currency}INR=X"
    frame = yf.download(pair, period="5d", interval="1d", auto_adjust=True,
                        progress=False, threads=False)
    if frame.empty or "Close" not in frame.columns:
        raise ValueError(f"No INR conversion rate available for {currency}.")
    close = frame["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = pd.to_numeric(close, errors="coerce").dropna()
    if close.empty or float(close.iloc[-1]) <= 0:
        raise ValueError(f"Invalid INR conversion rate for {currency}.")
    return float(close.iloc[-1])
