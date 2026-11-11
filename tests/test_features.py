import numpy as np
import pandas as pd
from trading_agent.market import features


def test_feature_target_excludes_last_candle_without_future_label():
    n = 80
    close = 100 + np.arange(n) * 0.1 + np.sin(np.arange(n) / 5)
    raw = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": 1000 + (np.arange(n) % 17) * 20
    }, index=pd.date_range("2025-01-01", periods=n, freq="5min", tz="UTC"))
    featured = features(raw)
    assert featured.index[-1] < raw.index[-1]
    assert featured["target"].notna().all()
