# AI Trading Agent — V1

A paper-trading-first intraday AI agent for research and experimentation. The design separates probabilistic market decisions from deterministic risk controls.

## Architecture

`Market data -> Feature engine -> ML agent -> Trade proposal -> Hard risk engine -> Paper execution`

The current model uses 5-minute OHLCV data, EMA 9/21, RSI-14, ATR-14, VWAP, volume z-score and short-term returns. A HistGradientBoosting classifier estimates the probability of the next bar closing higher. EMA/VWAP confirmation filters the model output.

The risk engine is deliberately outside the ML model. Default experimental settings for a ₹25,000 account cap position exposure at ₹3,000, risk budget at 0.5% equity per trade, daily loss at 2%, and require 62% model confidence. These limits reduce exposure; they do not guarantee safety or profit.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python main.py
pytest -q
```

Default symbol: `RELIANCE.NS`. Change the symbol passed to `run()` to test another Yahoo Finance NSE ticker.

## Safety status

**Paper trading only.** Live broker order placement is intentionally disabled in V1. Do not enable real-money execution until the system has been evaluated with point-in-time historical data, transaction costs/slippage, out-of-sample walk-forward testing, and a meaningful live paper-trading period.

## Next milestones

- Event-driven paper broker with positions, stop/target simulation and trade journal
- Walk-forward backtester with brokerage/slippage and drawdown metrics
- Multi-symbol NSE scanner
- Persistent model artifacts and scheduled retraining
- Optional multi-agent research layer inspired by TradingAgents
- Broker adapter only after validation, with kill switch and hard account limits

## Disclaimer

For software research/education. Trading involves risk and model predictions can fail, especially under changing market regimes.
