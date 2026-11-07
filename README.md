# Atlas — Multi-market AI Trading Platform

Personal AI research and **autonomous paper-trading** workspace, built on top of the existing AI Trading Agent V1. The INR paper account starts with ₹25,000. Live broker execution is not implemented and remains disabled.

## What is included

- Preserved V1 ML engine: HistGradientBoosting classifier, EMA/VWAP confirmation, OHLCV features, NSE data pipeline and gap validation.
- Multi-market historical data adapter for stocks, crypto, forex and commodities through Yahoo Finance (`yfinance`) where symbols and intervals are supported.
- FastAPI backend and React/Vite responsive dashboard.
- SQLite paper ledger with persistence, average-cost accounting, realized/unrealized P&L, simulated fees/slippage, order journal and stop-loss monitoring endpoint.
- Deterministic paper risk limits: 0.5% equity risk per trade, 2% daily drawdown guard, 10% initial-capital buy-order cap and 50% gross exposure cap.
- EMA crossover historical backtest with next-bar-open execution, fees, slippage, drawdown, Sharpe and win-rate reporting.
- Opt-in autonomous paper worker with start/stop controls and a configurable scan interval.
- GitHub Actions tests/build and Docker Compose.

## Safety and market currency

The paper account is denominated in INR. Manual paper order and mark-price APIs require prices converted to INR. The autonomous worker only executes instruments whose quote currency is INR; non-INR instruments can be researched and backtested but are not automatically traded until FX-normalized sizing and accounting are added. The current provider is historical/research-grade and does not guarantee real-time quotes or order execution.

No real broker credentials, live order endpoints, or live execution switches are provided. Do not connect real capital without independent validation, broker sandbox testing, reconciliation, security review and applicable regulatory review.

## Run locally

### Backend API
```bash
python -m venv .venv
# activate environment
pip install -r requirements.txt
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
```
API docs: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker compose up --build
```
The SQLite ledger is stored in the named `atlas_data` volume.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | API and safety status |
| GET | `/api/dashboard` | Persistent paper account snapshot |
| GET | `/api/markets` | Supported market categories |
| GET | `/api/market/{symbol}/candles` | Clearly labelled deterministic mock candles |
| GET | `/api/market/provider-candles` | Provider historical candles |
| POST | `/api/analyze` | Mock-data technical signal |
| POST | `/api/analyze/ml` | Historical-data V1 ML research analysis |
| POST | `/api/backtest` | Historical EMA strategy backtest |
| GET | `/api/paper/portfolio` | Paper account and positions |
| POST | `/api/paper/orders` | Simulated INR-denominated order |
| POST | `/api/paper/market-tick` | Mark position and check stop-loss |
| GET | `/api/automation/status` | Autonomous worker status |
| POST | `/api/automation/start` | Start paper-only autonomous scanning |
| POST | `/api/automation/stop` | Stop autonomous scanning |
| POST | `/api/automation/run-once` | Run one AI-to-paper cycle |

Example autonomous worker:
```json
{
  "watchlist": [{"symbol": "RELIANCE", "market": "stocks"}],
  "interval_seconds": 300
}
```

Example INR paper order:
```json
{
  "symbol": "RELIANCE",
  "market": "stocks",
  "side": "buy",
  "quantity": 1,
  "price_inr": 1200,
  "stop_loss_inr": 1180
}
```

## Current limitations / next milestones

1. Multi-provider market data, FX conversion and instrument master.
2. Persistent automation worker outside the API process (queue/worker deployment).
3. More strategy families and walk-forward ML evaluation.
4. Corporate actions, exchange calendars, lot sizes and market-specific transaction costs.
5. Alert delivery, observability and model registry.
6. Broker sandbox integration only after paper validation and legal/regulatory review.

This is a software research and simulation project, not financial advice. Historical backtests and model confidence do not guarantee future results.
