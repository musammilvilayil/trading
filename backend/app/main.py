from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .core import (Market, Side, settings, portfolio, market_data,
                   strategy_engine, place_paper_order, RiskRejected)
from .ml_adapter import analyze_with_preserved_ml
from .paper import PaperBroker, PaperTradeRejected
from trading_agent.providers import fetch_market_candles
from trading_agent.backtest import BacktestConfig, run_ema_backtest

paper_broker = PaperBroker(initial_capital=settings.starting_capital)

app = FastAPI(title="Atlas AI Trading API", version="0.2.0",
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
    price: float = Field(gt=0)
    stop_loss: float | None = Field(default=None, gt=0)


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": "paper-first",
            "market_data_mode": settings.market_data_mode,
            "live_trading_enabled": settings.live_trading_enabled}


@app.get("/api/markets")
def markets():
    return [{"id": m.value, "name": m.value.title()} for m in Market]


@app.get("/api/dashboard")
def dashboard():
    snapshot = paper_broker.portfolio()
    snapshot["market_data_mode"] = settings.market_data_mode
    snapshot["live_trading_enabled"] = False
    return snapshot@app.post("/api/paper/orders")
def paper_order(request: PaperOrderRequest):
    try:
        return paper_broker.place_order(request.symbol.upper(), request.market.value,
                                        request.side.value, request.quantity,
                                        request.price, request.stop_loss)
    except PaperTradeRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class PriceTickRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market
    price: float = Field(gt=0)


@app.post("/api/paper/market-tick")
def paper_market_tick(request: PriceTickRequest):
    try:
        return paper_broker.process_price(request.symbol, request.market.value, request.price)
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


class BacktestRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market
    period: str = "2y"
    interval: str = "1d"


@app.post("/api/backtest")
def backtest(request: BacktestRequest):
    try:
        instrument, frame = fetch_market_candles(request.symbol, request.market.value,
                                                  request.period, request.interval)
        result = run_ema_backtest(frame, BacktestConfig(starting_cash=settings.starting_capital))
        result["instrument"] = instrument.__dict__
        result["data_mode"] = "provider_historical"
        return result
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Backtest unavailable: {exc}") from exc


@app.post("/api/automation/run-once")
def autonomous_paper_run(request: AnalyzeRequest):
    try:
        report = analyze_with_preserved_ml(request.symbol.upper(), request.market.value,
                                            paper_broker.portfolio()["equity"])
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

