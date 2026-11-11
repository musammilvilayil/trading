# Atlas — Multi-market AI Trading Platform

Personal AI research and **autonomous paper-trading** workspace, built on top of the existing AI Trading Agent V1. The paper account starts with **₹25,000 INR**. Real-money broker execution is not implemented and remains disabled.

## Included

- Preserved V1 ML engine: HistGradientBoosting classifier, EMA/VWAP confirmation, OHLCV features, NSE data pipeline and gap validation.
- Multi-market historical data adapters for stocks, crypto, forex and commodities through Yahoo Finance (`yfinance`) where symbols and intervals are supported.
- FX conversion to INR using recent provider FX closes, with fail-closed behavior when a conversion is unavailable.
- FastAPI backend and responsive React/Vite dashboard.
- Optional Google Gemini market-intelligence layer: structured market briefs, technical interpretation, balanced bull/bear scenarios, risk notes and sentiment classification for explicitly supplied headlines.
- SQLite paper ledger with persistent account, average-cost accounting, realized/unrealized P&L, simulated fees/slippage, order journal and protective exit monitoring.
- Protective exit manager: initial stop, break-even stop after +0.8%, trailing stop activation after +1.2%, and a 0.6% trailing distance. Stops only ratchet upward for long positions.
- Deterministic risk limits: estimated 0.5% equity risk per trade including simulated round-trip costs, 2% daily drawdown guard, maximum 5 new entries per IST trading day, 10% initial-capital buy-order cap and 50% gross exposure cap.
- EMA crossover historical backtest with next-candle-open execution, fees, slippage, drawdown, Sharpe and win-rate reporting.
- Expanding-window, out-of-sample ML walk-forward evaluation with accuracy, precision, recall, F1, ROC-AUC and Brier score. Backtest capital is converted from INR into the instrument quote currency and results are reported in that currency.
- Opt-in autonomous paper worker with watchlist, 1–60 minute scan interval, start/stop controls, ML-based entry/exit proposals, FX-aware sizing and stop-loss checks.
- Open-position monitor and manual close controls in the dashboard.
- GitHub Actions tests/build and Docker Compose with persistent SQLite volume.

## Safety and limitations

- The account and all paper ledger values are INR-denominated. Manual paper orders and mark-price requests must use INR-converted prices. Estimated stop risk includes entry/exit fees and slippage assumptions.
- Autonomous scans can analyse all supported quote currencies; execution sizing converts quote prices and ATR into INR. If provider FX conversion is unavailable, that instrument's scan fails closed.
- The autonomous worker runs inside the API process and stops when that process restarts. It is opt-in and paper-only. Autonomous NSE/BSE cash-equity entries are limited to weekdays during 09:15–15:30 IST, require a fresh Dhan quote (maximum age 10 seconds), and use Dhan's 5-minute historical candles for model features/training; Yahoo historical candles remain a separate manual research path. The session check does not include an exchange holiday/special-session calendar. The ML confidence gate is configurable and must not be interpreted as a calibrated probability of profit.
- Yahoo Finance is a historical/research data source, not a guaranteed real-time feed or broker execution feed. Symbol coverage, intervals, delays and availability vary.
- Optional DhanHQ v2 WebSocket adapter receives live ticker/quote/full packets. It can mark mapped INR stock paper positions and evaluate protective exits, but it never submits broker orders. The Dhan instrument security ID must be mapped explicitly by the user. Autonomous model history is fetched from Dhan's intraday historical endpoint (60-day window per request), while live quote ticks provide the execution mark.
- Dhan feed credentials are read only from backend environment variables `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN`; never commit them. Dhan Data API access/subscription and current broker terms may apply.
- Backtests are simulations, not proof of profitability. The included EMA backtest is a baseline, not the ML agent's walk-forward performance report.
- Gemini is an advisory-only layer. Its output is never passed to the autonomous paper worker, risk engine or order executor; the quantitative ML engine remains independent.
- Gemini does not fetch live market news in this integration. Sentiment is marked `not_assessed` unless the caller explicitly supplies headlines; supplied headlines are treated as untrusted text.
- No real broker credentials, live order endpoints or live execution switch are provided. Broker sandbox/live trading must remain a separate, reviewed milestone after independent validation, reconciliation, security review and regulatory assessment.

## Run locally

### Backend API
```bash
python -m venv .venv
# activate environment
pip install -r requirements.txt
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000 --env-file .env
```
API docs: http://localhost:8000/docs

### Optional DhanHQ live market-data setup

1. Use a Dhan account and create/enable DhanHQ Trading & Data API access in the Dhan web platform.
2. Add `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN` to the backend's local `.env` file. Never expose the token in frontend code or commit it.
3. Obtain the exact Dhan exchange segment and security ID from Dhan's instrument master. Do not guess IDs.
4. Start the feed through `POST /api/market/dhan/start` with an instrument mapping and `mode` of `ticker`, `quote` or `full`. The feed supports reconnects and reports status through `GET /api/market/dhan/status`.
5. For mapped NSE/BSE cash positions, incoming INR prices update paper marks and run the protective exit manager. No real broker order is sent.

Dhan's API documentation specifies WebSocket live market data and separate trading order APIs. The live order API is deliberately not implemented in this release. Confirm broker requirements, static-IP whitelisting, exchange algo registration and applicable SEBI/NSE requirements before any real-money automation.

### Optional Gemini setup
1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` locally. Never commit the key or expose it in the Vite frontend.
3. Optionally set `GEMINI_MODEL` (default: `gemini-3.8-flash`). Restart the backend after changing environment variables.
4. Check `GET /api/ai/status`, then call `POST /api/ai/market-brief` or use **Generate brief** in the dashboard.

Without a key, Atlas continues to run its existing ML and paper-trading features; only the Gemini brief is disabled. Docker Compose forwards the key from the local environment into the API container.

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
| GET | `/api/market/dhan/status` | DhanHQ live market-feed status |
| POST | `/api/market/dhan/start` | Start DhanHQ v2 live quote feed for mapped instruments |
| POST | `/api/market/dhan/stop` | Stop DhanHQ live quote feed |
| POST | `/api/analyze` | Mock-data technical signal |
| POST | `/api/analyze/ml` | Historical-data V1 ML research analysis |
| POST | `/api/backtest` | Historical EMA baseline backtest |
| POST | `/api/backtest/ml` | Expanding-window out-of-sample ML metrics |
| GET | `/api/paper/portfolio` | Paper account and positions |
| POST | `/api/paper/orders` | Simulated INR-denominated order |
| GET | `/api/risk/policy` | Active deterministic risk and exit policy |
| POST | `/api/paper/market-tick` | Mark position and run protective exit manager |
| GET | `/api/ai/status` | Gemini configuration status (never returns the key) |\n| POST | `/api/ai/market-brief` | Gemini advisory market brief from supplied ML analysis and optional headlines |\n| GET | `/api/automation/status` | Autonomous worker status |
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
