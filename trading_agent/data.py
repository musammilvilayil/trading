from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
DEFAULT_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]


def normalize_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    return symbol if symbol.endswith(".NS") else f"{symbol}.NS"


def download_candles(symbol: str, period: str = "60d", interval: str = "5m") -> pd.DataFrame:
    symbol = normalize_symbol(symbol)
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    if df.empty:
        raise ValueError(f"No market data returned for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return clean_candles(df)


def clean_candles(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    out = df.copy()
    out.index = pd.to_datetime(out.index, utc=True)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out = out[REQUIRED_COLUMNS].apply(pd.to_numeric, errors="coerce").dropna()
    out = out[(out["High"] >= out["Low"]) & (out["Volume"] >= 0)]
    return out


def validate_candles(df: pd.DataFrame) -> dict[str, int | bool]:
    if df.empty:
        return {"rows": 0, "duplicates": 0, "monotonic": True, "valid": False}
    duplicates = int(df.index.duplicated().sum())
    monotonic = bool(df.index.is_monotonic_increasing)
    valid = duplicates == 0 and monotonic and all(c in df.columns for c in REQUIRED_COLUMNS)
    return {"rows": len(df), "duplicates": duplicates, "monotonic": monotonic, "valid": valid}


def save_candles(df: pd.DataFrame, symbol: str, interval: str, root: str = "data") -> Path:
    symbol = normalize_symbol(symbol).replace(".NS", "")
    path = Path(root) / "raw" / interval
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"{symbol}.csv"
    df.to_csv(file_path, index_label="timestamp")
    return file_path


def update_universe(symbols: Iterable[str] = DEFAULT_SYMBOLS, period: str = "60d", interval: str = "5m", root: str = "data") -> dict[str, str]:
    results: dict[str, str] = {}
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        try:
            df = download_candles(normalized, period=period, interval=interval)
            report = validate_candles(df)
            if not report["valid"]:
                raise ValueError(f"Validation failed: {report}")
            results[normalized] = str(save_candles(df, normalized, interval, root))
        except Exception as exc:
            results[normalized] = f"ERROR: {exc}"
    return results
