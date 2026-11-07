# Atlas — Multi-market AI Trading Platform

Personal AI research and **autonomous paper-trading** workspace, built on top of the existing AI Trading Agent V1. The paper account starts with **₹25,000 INR**. Real-money broker execution is not implemented and remains disabled.

## Included

- Preserved V1 ML engine: HistGradientBoosting classifier, EMA/VWAP confirmation, OHLCV features, NSE data pipeline and gap validation.
- Multi-market historical data adapters for stocks, crypto, forex and commodities through Yahoo Finance (`yfinance`) where symbols and intervals are supported.
- FX conversion to INR using recent provider FX closes, with fail-closed behavior when a conversion is unavailable.
- FastAPI backend and responsive React/Vite dashboard.
- SQLite paper ledger with persistent account, average-cost accounting, realized/unrealized P&L, simulated fees/slippage, order journal and stop-loss monitoring.
- Deterministic risk limits: 0.5% equity risk per trade, 2% daily drawdown guard, 10% initial-capital buy-order cap and 50% gross exposure cap.
- EMA crossover historical backtest with next-candle-open execution, fees, slippage, drawdown, Sharpe and win-rate reporting.
- Expanding-window, out-of-sample ML walk-forward evaluation with accuracy, precision, recall, F1, ROC-AUC and Brier score. Backtest capital is converted from INR into the instrument quote currency and results are reported in that currency.
- Opt-in autonomous paper worker with watchlist, 1–60 minute scan interval, start/stop controls, ML-based entry/exit proposals, FX-aware sizing and stop-loss checks.
- Open-position monitor and manual close controls in the dashboard.
- GitHub Actions tests/build and Docker Compose with persistent SQLite volume.

## Safety and limitations

- The account and all paper ledger values are INR-denominated. Manual paper orders and mark-price requests must use INR-converted prices.
- Autonomous scans can analyse all supported quote currencies; execution sizing converts quote prices and ATR into INR. If provider FX conversion is unavailable, that instrument's scan fails closed.
- The autonomous worker runs inside the API process and stops when that process restarts. It is opt-in and paper-only.
- Yahoo Finance is a historical/research data source, not a guaranteed real-time feed or broker execution feed. Symbol coverage, intervals, delays and availability vary.
- Backtests are simulations, not proof of profitability. The included EMA backtest is a baseline, not the ML agent's walk-forward performance report.
- No real broker credentials, live order endpoints or live execution switch are provided. Broker sandbox/live trading must remain a separate, reviewed milestone after independent validation, reconciliation, security review and regulatory assessment.

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
The SQLite ledger persists in the named `atlas_data` volume.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | API and safety status |
| GET | `/api/dashboard` | Persistent INR paper account |
| GET | `/api/markets` | Supported market categories |
| GET | `/api/market/{symbol}/candles` | Clearly labelled mock candles |
| GET | `/api/market/provider-candles` | Provider historical candles |
| GET | `/api/market/fx-to-inr` | Provider FX conversion rate |
| POST | `/api/analyze` | Mock-data technical signal |
| POST | `/api/analyze/ml` | Historical-data V1 ML research analysis |
| POST | `/api/backtest` | Historical EMA baseline backtest |
| POST | `/api/backtest/ml` | Expanding-window out-of-sample ML metrics |
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
  "watchlist": [
    {"symbol": "RELIANCE", "market": "stocks"},
    {"symbol": "BTC-USD", "market": "crypto"}
  ],
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

## Remaining production milestones

1. Replace the process-local automation loop with a durable worker/queue and persisted run state.
2. Add more data vendors, exchange instrument master, exchange calendars and corporate actions.
3. Add model registry, drift monitoring and scheduled retraining; the current walk-forward evaluator is a first validation baseline.
4. Add market-specific fees, taxes, lot sizes, spreads, latency and realistic order-book simulation.
5. Add alert delivery, observability, secrets management and disaster recovery.
6. Consider broker sandbox integration only after sustained paper validation and legal/regulatory review.

This is a software research and simulation project, not financial advice. Historical performance and model confidence do not guarantee future results.
