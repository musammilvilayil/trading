from __future__ import annotations
import numpy as np
import pandas as pd
import yfinance as yf


def fetch_intraday(symbol: str, period: str = '5d', interval: str = '5m') -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f'No market data returned for {symbol}')
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna().copy()


def features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    close = x['Close']
    x['ret1'] = close.pct_change()
    x['ema9'] = close.ewm(span=9, adjust=False).mean()
    x['ema21'] = close.ewm(span=21, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    rs = gain / loss
    x['rsi14'] = 100 - 100 / (1 + rs)
    tr = pd.concat([(x['High']-x['Low']), (x['High']-close.shift()).abs(), (x['Low']-close.shift()).abs()], axis=1).max(axis=1)
    x['atr14'] = tr.rolling(14).mean()
    typical = (x['High'] + x['Low'] + close) / 3
    x['vwap'] = (typical * x['Volume']).cumsum() / x['Volume'].cumsum().replace(0, np.nan)
    x['volume_z'] = (x['Volume'] - x['Volume'].rolling(20).mean()) / x['Volume'].rolling(20).std()
    x['target'] = (close.shift(-1) > close).astype(int)
    return x.replace([np.inf, -np.inf], np.nan).dropna()


FEATURE_COLUMNS = ['ret1', 'ema9', 'ema21', 'rsi14', 'atr14', 'vwap', 'volume_z']
