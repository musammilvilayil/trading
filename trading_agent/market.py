from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf


def fetch_intraday(symbol: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No market data returned for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna().copy()


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Build causal OHLCV features; VWAP resets at each UTC trading date."""
    x = df.copy().sort_index()
    if not isinstance(x.index, pd.DatetimeIndex):
        raise ValueError("OHLCV data must have a DatetimeIndex.")
    if x.index.tz is None:
        x.index = x.index.tz_localize("UTC")
    else:
        x.index = x.index.tz_convert("UTC")

    close = x["Close"].astype(float)
    x["ret1"] = close.pct_change()
    x["ema9"] = close.ewm(span=9, adjust=False).mean()
    x["ema21"] = close.ewm(span=21, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    x["rsi14"] = 100 - 100 / (1 + gain / loss)

    true_range = pd.concat(
        [
            x["High"].astype(float) - x["Low"].astype(float),
            (x["High"].astype(float) - close.shift()).abs(),
            (x["Low"].astype(float) - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    x["atr14"] = true_range.rolling(14).mean()

    typical = (x["High"].astype(float) + x["Low"].astype(float) + close) / 3
    volume = x["Volume"].astype(float).clip(lower=0)
    session_key = x.index.normalize()
    cumulative_pv = (typical * volume).groupby(session_key).cumsum()
    cumulative_volume = volume.groupby(session_key).cumsum().replace(0, np.nan)
    x["vwap"] = cumulative_pv / cumulative_volume

    rolling_volume_mean = volume.rolling(20).mean()
    rolling_volume_std = volume.rolling(20).std().replace(0, np.nan)
    x["volume_z"] = (volume - rolling_volume_mean) / rolling_volume_std

    next_close = close.shift(-1)
    x["target"] = (next_close > close).where(next_close.notna()).astype(float)
    return x.replace([np.inf, -np.inf], np.nan).dropna()


FEATURE_COLUMNS = ["ret1", "ema9", "ema21", "rsi14", "atr14", "vwap", "volume_z"]
