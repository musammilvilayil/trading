import pandas as pd

from trading_agent.data import clean_candles, detect_gaps, merge_candles, normalize_symbol, validate_candles


def candle_frame(times, closes=None):
    idx = pd.to_datetime(times, utc=True)
    closes = closes or [101 + i for i in range(len(idx))]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [v + 1 for v in closes],
            "Low": [v - 1 for v in closes],
            "Close": closes,
            "Volume": [1000] * len(idx),
        },
        index=idx,
    )


def test_normalize_symbol():
    assert normalize_symbol("reliance") == "RELIANCE.NS"
    assert normalize_symbol("TCS.NS") == "TCS.NS"


def test_clean_removes_duplicate_timestamp():
    df = candle_frame(["2026-01-01 09:15", "2026-01-01 09:15", "2026-01-01 09:20"])
    cleaned = clean_candles(df)
    report = validate_candles(cleaned)
    assert len(cleaned) == 2
    assert report["valid"] is True
    assert report["duplicates"] == 0


def test_merge_is_incremental_and_deduplicated():
    old = candle_frame(["2026-01-01 03:45", "2026-01-01 03:50"], [100, 101])
    new = candle_frame(["2026-01-01 03:50", "2026-01-01 03:55"], [105, 106])
    merged = merge_candles(old, new)
    assert len(merged) == 3
    assert merged.loc[pd.Timestamp("2026-01-01 03:50", tz="UTC"), "Close"] == 105


def test_detect_intraday_gap():
    df = candle_frame(["2026-01-01 03:45", "2026-01-01 03:50", "2026-01-01 04:00"])
    gaps = detect_gaps(df, "5m")
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 1


def test_overnight_gap_is_ignored():
    df = candle_frame(["2026-01-01 10:00", "2026-01-02 03:45"])
    assert detect_gaps(df, "5m") == []
