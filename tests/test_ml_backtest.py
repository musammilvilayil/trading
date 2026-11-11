import numpy as np
import pandas as pd
from trading_agent.market import features
from trading_agent.backtest import evaluate_ml_walk_forward


def test_ml_walk_forward_uses_out_of_sample_folds():
    n = 900
    x = np.arange(n)
    close = 100 + np.sin(x / 11) * 2 + x * 0.002
    raw = pd.DataFrame({
        "Open": close, "High": close + 0.8, "Low": close - 0.8,
        "Close": close, "Volume": 1000 + (x % 19) * 25
    }, index=pd.date_range("2024-01-01", periods=n, freq="5min", tz="UTC"))
    featured = features(raw)
    result = evaluate_ml_walk_forward(featured, min_train=300, test_window=200)
    assert result["fold_count"] >= 2
    assert result["rows_evaluated"] > 0
    assert 0 <= result["metrics"]["accuracy_pct"] <= 100
