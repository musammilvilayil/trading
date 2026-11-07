from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .core import (Market, Side, settings, portfolio, market_data,
                   strategy_engine, place_paper_order, RiskRejected)
from .ml_adapter import analyze_with_preserved_ml

app = FastAPI(title="Atlas AI Trading API", version="0.1.0",
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
    return {"capital": portfolio.initial_capital, "cash": round(portfolio.cash, 2),
            "invested_value": round(portfolio.invested_value, 2),
            "equity": round(portfolio.equity, 2),
            "realized_pnl": round(portfolio.realized_pnl, 2),
            "positions": [vars(p) for p in portfolio.positions.values()],
            "recent_orders": portfolio.orders[:8],
            "market_data_mode": settings.market_data_mode,
            "live_trading_enabled": settings.live_trading_enabled}


@app.get("/api/market/{symbol}/candles")
def candles(symbol: str, market: Market = Market.stocks, limit: int = 60):
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
        return analyze_with_preserved_ml(request.symbol.upper(), portfolio.equity)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"ML research analysis unavailable: {exc}") from exc


@app.get("/api/paper/portfolio")
def paper_portfolio():
    return dashboard()


@app.post("/api/paper/orders")
def paper_order(request: PaperOrderRequest):
    try:
        return place_paper_order(request.symbol.upper(), request.market.value,
                                 request.side, request.quantity, request.price,
                                 request.stop_loss)
    except RiskRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/")
def root():
    return {"name": "Atlas AI Trading API", "docs": "/docs", "mode": "paper-only"}
