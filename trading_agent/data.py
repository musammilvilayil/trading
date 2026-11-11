from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]
DEFAULT_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]
INTERVAL_DELTAS = {"1m": "1min", "2m": "2min", "5m": "5min", "15m": "15min", "30m": "30min", "60m": "60min", "1h": "60min", "1d": "1D"}


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


def data_path(symbol: str, interval: str, root: str = "data") -> Path:
    name = normalize_symbol(symbol).replace(".NS", "")
    return Path(root) / "raw" / interval / f"{name}.csv"


def load_candles(symbol: str, interval: str = "5m", root: str = "data") -> pd.DataFrame:
    path = data_path(symbol, interval, root)
    if not path.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    df = pd.read_csv(path, index_col="timestamp", parse_dates=["timestamp"])
    return clean_candles(df)


def merge_candles(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return clean_candles(incoming)
    if incoming.empty:
        return clean_candles(existing)
    return clean_candles(pd.concat([existing, incoming]))


def detect_gaps(df: pd.DataFrame, interval: str = "5m") -> list[dict[str, str | int]]:
    """Detect unexpected gaps within each trading day; overnight/weekend gaps are ignored."""
    if df.empty or interval not in INTERVAL_DELTAS:
        return []
    expected = pd.Timedelta(INTERVAL_DELTAS[interval])
    gaps: list[dict[str, str | int]] = []
    local = df.copy()
    local.index = local.index.tz_convert("Asia/Kolkata")
    for _, day in local.groupby(local.index.date):
        diffs = day.index.to_series().diff()
        for timestamp, delta in diffs[diffs > expected].items():
            missing = max(int(delta / expected) - 1, 0)
            if missing:
                gaps.append({"before": (timestamp - delta).isoformat(), "after": timestamp.isoformat(), "missing_bars": missing})
    return gaps


def write_metadata(df: pd.DataFrame, symbol: str, interval: str, root: str = "data") -> Path:
    path = data_path(symbol, interval, root)
    meta_path = path.with_suffix(".meta.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    report = validate_candles(df)
    payload = {
        "symbol": normalize_symbol(symbol),
        "interval": interval,
        "rows": len(df),
        "first_timestamp": df.index.min().isoformat() if not df.empty else None,
        "last_timestamp": df.index.max().isoformat() if not df.empty else None,
        "duplicates": report["duplicates"],
        "gap_count": len(detect_gaps(df, interval)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return meta_path


def save_candles(df: pd.DataFrame, symbol: str, interval: str, root: str = "data") -> Path:
    path = data_path(symbol, interval, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index_label="timestamp")
    write_metadata(df, symbol, interval, root)
    return path


def update_symbol(symbol: str, period: str = "60d", interval: str = "5m", root: str = "data") -> dict[str, object]:
    normalized = normalize_symbol(symbol)
    existing = load_candles(normalized, interval, root)
    incoming = download_candles(normalized, period=period, interval=interval)
    merged = merge_candles(existing, incoming)
    report = validate_candles(merged)
    if not report["valid"]:
        raise ValueError(f"Validation failed: {report}")
    path = save_candles(merged, normalized, interval, root)
    return {"symbol": normalized, "path": str(path), "old_rows": len(existing), "new_rows": len(merged), "added_rows": max(len(merged) - len(existing), 0), "gaps": len(detect_gaps(merged, interval))}


def update_universe(symbols: Iterable[str] = DEFAULT_SYMBOLS, period: str = "60d", interval: str = "5m", root: str = "data") -> dict[str, object]:
    results: dict[str, object] = {}
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        try:
            results[normalized] = update_symbol(normalized, period, interval, root)
        except Exception as exc:
            results[normalized] = {"error": str(exc)}
    return results
