import pandas as pd

from trading_agent.data import clean_candles, normalize_symbol, validate_candles


def test_normalize_symbol():
    assert normalize_symbol("reliance") == "RELIANCE.NS"
    assert normalize_symbol("TCS.NS") == "TCS.NS"


def test_clean_removes_duplicate_timestamp():
    idx = pd.to_datetime(["2026-01-01 09:15", "2026-01-01 09:15", "2026-01-01 09:20"])
    df = pd.DataFrame(
        {
            "Open": [100, 101, 102],
            "High": [102, 103, 104],
            "Low": [99, 100, 101],
            "Close": [101, 102, 103],
            "Volume": [1000, 1100, 1200],
        },
        index=idx,
    )
    cleaned = clean_candles(df)
    report = validate_candles(cleaned)
    assert len(cleaned) == 2
    assert report["valid"] is True
    assert report["duplicates"] == 0
