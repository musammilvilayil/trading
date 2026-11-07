import numpy as np
import pandas as pd
from trading_agent.backtest import BacktestConfig, run_ema_backtest


def sample_candles():
    n = 160
    close = 100 + np.sin(np.arange(n) / 8) * 8 + np.arange(n) * 0.04
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                         "Close": close, "Volume": np.full(n, 1000)})


def test_backtest_returns_metrics_and_charges_costs():
    result = run_ema_backtest(sample_candles(), BacktestConfig())
    assert result["final_equity"] > 0
    assert result["max_drawdown_pct"] <= 0
    assert result["closed_trades"] >= 1
    assert result["execution_assumptions"]["signal_execution"] == "next candle open"


def test_backtest_rejects_short_history():
    import pytest
    with pytest.raises(ValueError):
        run_ema_backtest(sample_candles().head(10))
