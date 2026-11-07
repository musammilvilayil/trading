from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .core import Market, Side, settings, market_data, strategy_engine
from .ml_adapter import analyze_with_preserved_ml
from .paper import PaperBroker, PaperTradeRejected
from .automation import PaperAutomation
from trading_agent.providers import fetch_market_candles
from trading_agent.backtest import BacktestConfig, run_ema_backtest

paper_broker = PaperBroker(initial_capital=settings.starting_capital)
automation_service = PaperAutomation(paper_broker, analyze_with_preserved_ml)

app = FastAPI(title="Atlas AI Trading API", version="0.3.0",
              description="Multi-market research and paper trading. Live trading is disabled.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


class AnalyzeRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market
    side: Side
    quantity: float = Field(gt=0)
    price_inr: float = Field(gt=0, description="Price converted to INR; paper account is INR-denominated.")
    stop_loss_inr: float | None = Field(default=None, gt=0)


class PriceTickRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market
    price_inr: float = Field(gt=0, description="Latest mark price converted to INR.")


class BacktestRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market
    period: str = "2y"
    interval: str = "1d"


@app.get("/")
def root():
    return {"name": "Atlas AI Trading API", "docs": "/docs", "mode": "paper-only"}


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": "paper-first",
            "market_data_mode": settings.market_data_mode,
            "live_trading_enabled": False, "database": "sqlite-paper-ledger"}


@app.get("/api/markets")
def markets():
    return [{"id": m.value, "name": m.value.title()} for m in Market]


@app.get("/api/dashboard")
def dashboard():
    snapshot = paper_broker.portfolio()
    snapshot["market_data_mode"] = settings.market_data_mode
    snapshot["live_trading_enabled"] = False
    return snapshot


@app.get("/api/market/{symbol}/candles")
def mock_candles(symbol: str, market: Market = Market.stocks, limit: int = 60):
    if not 20 <= limit <= 250:
        raise HTTPException(400, "limit must be between 20 and 250")
    return {"symbol": symbol.upper(), "market": market.value,
            "data_mode": "mock", "candles": market_data.candles(symbol.upper(), limit)}


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    rows = market_data.candles(request.symbol.upper())
    return strategy_engine.analyze(request.symbol.upper(), request.market.value, rows)


@app.post("/api/analyze/ml")
def analyze_ml(request: AnalyzeRequest):
    try:
        return analyze_with_preserved_ml(request.symbol.upper(), request.market.value,
                                         paper_broker.portfolio()["equity"])
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"ML research analysis unavailable: {exc}") from exc


@app.get("/api/paper/portfolio")
def paper_portfolio():
    return dashboard()


@app.post("/api/paper/orders")
def paper_order(request: PaperOrderRequest):
    try:
        return paper_broker.place_order(request.symbol.upper(), request.market.value,
                                        request.side.value, request.quantity,
                                        request.price_inr, request.stop_loss_inr)
    except PaperTradeRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/paper/market-tick")
def paper_market_tick(request: PriceTickRequest):
    try:
        return paper_broker.process_price(request.symbol, request.market.value, request.price_inr)
    except PaperTradeRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/market/provider-candles")
def provider_candles(symbol: str, market: Market, period: str = "60d", interval: str = "1d"):
    try:
        instrument, frame = fetch_market_candles(symbol, market.value, period, interval)
        rows = [{"time": index.isoformat(), **{key.lower(): float(row[key]) for key in ["Open", "High", "Low", "Close", "Volume"]}}
                for index, row in frame.iterrows()]
        return {"instrument": instrument.__dict__, "data_mode": "provider_historical",
                "count": len(rows), "candles": rows}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Market data unavailable: {exc}") from exc


@app.post("/api/backtest")
def backtest(request: BacktestRequest):
    try:
        instrument, frame = fetch_market_candles(request.symbol, request.market.value,
                                                  request.period, request.interval)
        # The backtest's cash unit matches the instrument quote currency.
        result = run_ema_backtest(frame, BacktestConfig(starting_cash=settings.starting_capital))
        result["instrument"] = instrument.__dict__
        result["account_currency"] = instrument.quote_currency
        result["data_mode"] = "provider_historical"
        result["disclaimer"] = ("Historical simulation in instrument quote currency; this is not the INR paper ledger. "
                                "Fees, slippage and future market conditions may differ.")
        return result
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Backtest unavailable: {exc}") from exc





class AutomationInstrument(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market


class AutomationStartRequest(BaseModel):
    watchlist: list[AutomationInstrument] = Field(min_length=1, max_length=10)
    interval_seconds: int = Field(default=300, ge=60, le=3600)


@app.get("/api/automation/status")
def automation_status():
    return automation_service.status()


@app.post("/api/automation/start")
async def automation_start(request: AutomationStartRequest):
    try:
        watchlist = [{"symbol": item.symbol.upper(), "market": item.market.value}
                     for item in request.watchlist]
        return await automation_service.start(watchlist, request.interval_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/automation/stop")
async def automation_stop():
    return await automation_service.stop()

@app.post("/api/automation/run-once")
def autonomous_paper_run(request: AnalyzeRequest):
    try:
        report = analyze_with_preserved_ml(request.symbol.upper(), request.market.value,
                                            paper_broker.portfolio()["equity"])
        instrument = report["instrument"]
        if instrument["quote_currency"] != "INR":
            return {"status": "research_only", "analysis": report,
                    "reason": "Autonomous paper execution requires INR-denominated pricing. "
                              "This instrument is quoted in another currency; FX-normalized risk sizing is not enabled."}
        proposal = report["proposal"]
        approved = report["risk_approved_paper_order"]
        if not approved or proposal["action"] != "BUY":
            return {"status": "no_trade", "analysis": report,
                    "reason": "No risk-approved long entry; no order was submitted."}
        order = paper_broker.place_order(request.symbol.upper(), request.market.value,
                                         "buy", approved["quantity"], approved["entry"],
                                         stop_loss=approved["stop"], reason="autonomous_ml_paper_agent")
        return {"status": "paper_order_filled", "analysis": report, "order": order,
                "live_trading_enabled": False}
    except (PaperTradeRejected, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
