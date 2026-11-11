import numpy as np
import pandas as pd

from trading_agent.market import features


def test_vwap_resets_for_each_utc_session():
    index = pd.date_range("2026-11-10T09:15:00Z", periods=25, freq="5min").append(
        pd.date_range("2026-11-11T09:15:00Z", periods=25, freq="5min")
    )
    close = 100 + np.sin(np.arange(50) / 3) * 2 + np.arange(50) * 0.05
    frame = pd.DataFrame({
        "Open": close - 0.2,
        "High": close + 0.5,
        "Low": close - 0.5,
        "Close": close,
        "Volume": np.full(50, 1000.0),
    }, index=index)

    result = features(frame)

    first_bar_second_day = index[25]
    expected = (frame.loc[first_bar_second_day, "High"]
                + frame.loc[first_bar_second_day, "Low"]
                + frame.loc[first_bar_second_day, "Close"]) / 3
    actual = result.loc[first_bar_second_day, "vwap"]

    assert actual == expected
