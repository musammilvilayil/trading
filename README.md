# Atlas — Multi-market AI Trading Platform

A personal AI trading research and simulation workspace, built on the original AI Trading Agent V1 rather than replacing it.

## Preserved V1 engine
The existing `trading_agent/` package remains intact: 5-minute OHLCV feature engineering, HistGradientBoosting probability model, EMA/VWAP confirmation, deterministic risk sizing, NSE data pipeline, candle validation/gap detection, CLI runner and tests. The original V1 configuration starts with ₹25,000 and caps risk per trade and daily drawdown.

## Added platform foundation
- FastAPI service and React/Vite dashboard.
- Portfolio and simulated order API.
- Strategy workbench and multi-market instrument selection.
- Configurable paper capital (default ₹25,000).
- Docker Compose and CI workflows.
- Explicitly disabled live trading.

## Markets and data adapters
The dashboard supports stocks, crypto, forex and commodities as market categories. The sample provider is labelled MOCK and must not be mistaken for a quote. The preserved ML engine uses Yahoo Finance via `yfinance`; it is a research data source, not an execution-grade feed. For multi-market analysis, use provider-native symbols such as `RELIANCE.NS`, `BTC-USD`, `EURUSD=X`, or `GC=F` where Yahoo Finance supports them. Availability, delays, history and instrument mappings vary by market.

## Run locally
### Original ML agent
```bash
python -m venv .venv
# activate, then:
pip install -r requirements.txt
python main.py
pytest -q
```

### API
```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### Frontend
```bash
cd frontend && npm install && npm run dev
```

### Docker
```bash
docker compose up --build
```

## API endpoints
- `GET /api/health`, `GET /api/dashboard`, `GET /api/markets`
- `GET /api/market/{symbol}/candles`
- `POST /api/analyze` — illustrative analysis on MOCK candles
- `POST /api/analyze/ml` — historical Yahoo Finance data + preserved V1 model/risk engine
- `POST /api/paper/orders`, `GET /api/paper/portfolio`

## Safety
This repository is paper-trading-first. Live broker execution is not implemented or enabled. The dashboard's mock-data analysis is illustrative. ML results are historical-data research signals, not guaranteed forecasts. Before any real-money integration, add point-in-time backtesting, costs/slippage, out-of-sample walk-forward validation, provider reliability checks, persistent order reconciliation, kill-switches, broker sandbox testing and a legal/regulatory review. Do not treat a model signal as a recommendation to buy or sell.

## Next engineering milestones
1. Persist orders, positions, candles and model versions in PostgreSQL/TimescaleDB.
2. Build event-driven paper broker with stop/target simulation and trade journal.
3. Add multi-market provider adapters and normalized instrument master.
4. Implement realistic backtesting with fees, slippage, latency and walk-forward evaluation.
5. Add model registry, scheduled retraining, monitoring and alerting.
6. Only after validation, assess broker sandbox and compliant live-order integration.
