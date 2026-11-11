import asyncio
import json
from datetime import datetime, timezone, time as dt_time
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .core import Market, Side, settings, market_data, strategy_engine
from .ml_adapter import analyze_with_preserved_ml, analyze_with_dhan_history
from .paper import PaperBroker, PaperTradeRejected
from .automation import PaperAutomation
from trading_agent.providers import fetch_market_candles, quote_to_inr_rate
from trading_agent.backtest import BacktestConfig, run_ema_backtest, evaluate_ml_walk_forward
from trading_agent.market import features
from .execution import build_paper_buy_plan
from .exit_manager import risk_policy_summary
from .gemini import (GeminiNotConfiguredError, GeminiProviderError,
                     generate_market_brief, get_gemini_status)
from .brokers.dhan_feed import DhanFeedError, DhanFeedService

paper_broker = PaperBroker(initial_capital=settings.starting_capital)


async def _monitor_paper_positions_from_dhan(tick: dict):
    # Dhan live quotes are used only to mark INR-denominated cash-equity paper
    # positions and evaluate protective exits. No real order is sent.
    if tick.get("market") != Market.stocks.value or tick.get("exchange_segment") not in {"NSE_EQ", "BSE_EQ"}:
        return
    try:
        result = await asyncio.to_thread(
            paper_broker.process_price, tick["symbol"], tick["market"], float(tick["last_price"])
        )
        if result.get("stop_triggered"):
            tick["paper_exit"] = result
    except PaperTradeRejected as exc:
        tick["paper_monitor_error"] = str(exc)


dhan_feed_service = DhanFeedService(on_tick=_monitor_paper_positions_from_dhan)


def is_nse_regular_session(now: datetime | None = None) -> bool:
    local = (now or datetime.now(ZoneInfo("Asia/Kolkata"))).astimezone(ZoneInfo("Asia/Kolkata"))
    return local.weekday() < 5 and dt_time(9, 15) <= local.time() <= dt_time(15, 30)


def require_fresh_dhan_tick(symbol: str, market: str):
    if not is_nse_regular_session():
        raise ValueError("NSE/BSE autonomous mode is available only during the weekday 09:15–15:30 IST session.")
    if market != Market.stocks.value:
        raise ValueError("Autonomous intraday execution currently supports mapped NSE/BSE cash equities only.")
    tick = dhan_feed_service.latest_tick(symbol, market)
    if not tick:
        raise ValueError("Connect the Dhan live feed and receive a quote before running autonomous intraday trading.")
    received_at = datetime.fromisoformat(tick["received_at"])
    age_seconds = (datetime.now(timezone.utc) - received_at).total_seconds()
    if age_seconds < 0 or age_seconds > 10:
        raise ValueError("Dhan live quote is stale; autonomous entries are blocked until a fresh tick arrives.")
    return tick, age_seconds


def analyze_for_autonomous_intraday(symbol: str, market: str, equity: float):
    """Train/evaluate on history, but require a fresh Dhan quote for execution price."""
    tick, age_seconds = require_fresh_dhan_tick(symbol, market)
    report = analyze_with_dhan_history(
        symbol, market, equity,
        security_id=tick["security_id"],
        exchange_segment=tick["exchange_segment"],
    )
    signal_candle_at = datetime.fromisoformat(report["latest_signal_candle_at"])
    signal_age_seconds = (datetime.now(timezone.utc) - signal_candle_at).total_seconds()
    if signal_age_seconds < 0 or signal_age_seconds > 600:
        raise ValueError("Dhan historical signal candle is older than 10 minutes; autonomous trading is blocked.")
    report["signal_candle_age_seconds"] = round(signal_age_seconds, 3)
    fx_rate = float(report["fx_to_inr"])
    if fx_rate <= 0:
        raise ValueError("Invalid INR conversion rate.")
    live_price_inr = float(tick["last_price"])
    report["proposal"]["entry"] = live_price_inr / fx_rate
    report["entry_price_inr"] = live_price_inr
    report["data_mode"] = "historical_model_with_fresh_dhan_quote"
    report["live_quote"] = {
        "provider": "DhanHQ v2",
        "last_price_inr": live_price_inr,
        "exchange_time": tick.get("exchange_time"),
        "received_at": tick["received_at"],
        "age_seconds": round(age_seconds, 3),
    }
    return report

automation_service = PaperAutomation(paper_broker, analyze_for_autonomous_intraday)

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


class GeminiBriefRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market
    analysis: dict | None = None
    news_context: list[str] = Field(default_factory=list, max_length=8)


@app.get("/")
def root():
    return {"name": "Atlas AI Trading API", "docs": "/docs", "mode": "paper-only"}


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": "paper-first",
            "market_data_mode": settings.market_data_mode,
            "live_trading_enabled": False, "database": "sqlite-paper-ledger"}


@app.get("/api/risk/policy")
def risk_policy():
    """Expose deterministic paper risk/exit settings; never enables live trading."""
    return risk_policy_summary()


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
        fx_rate = quote_to_inr_rate(instrument.quote_currency)
        return {"instrument": instrument.__dict__, "data_mode": "provider_historical",
                "fx_to_inr": fx_rate, "count": len(rows), "candles": rows}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Market data unavailable: {exc}") from exc



@app.get("/api/market/fx-to-inr")
def fx_to_inr(currency: str):
    try:
        return {"currency": currency.upper(), "fx_to_inr": quote_to_inr_rate(currency),
                "data_source": "Yahoo Finance recent historical FX close"}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"FX conversion unavailable: {exc}") from exc

@app.post("/api/backtest")
def backtest(request: BacktestRequest):
    try:
        instrument, frame = fetch_market_candles(request.symbol, request.market.value,
                                                  request.period, request.interval)
        # The backtest's cash unit matches the instrument quote currency.
        fx_rate = quote_to_inr_rate(instrument.quote_currency)
        result = run_ema_backtest(frame, BacktestConfig(starting_cash=settings.starting_capital / fx_rate))
        result["instrument"] = instrument.__dict__
        result["account_currency"] = instrument.quote_currency
        result["starting_capital_inr"] = settings.starting_capital
        result["fx_to_inr"] = fx_rate
        result["data_mode"] = "provider_historical"
        result["disclaimer"] = ("Starting INR capital is converted using a recent provider FX close; "
                                "results are reported in instrument quote currency. Fees, slippage and future conditions may differ.")
        return result
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Backtest unavailable: {exc}") from exc





class AutomationInstrument(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market


class AutomationStartRequest(BaseModel):
    watchlist: list[AutomationInstrument] = Field(min_length=1, max_length=10)
    interval_seconds: int = Field(default=300, ge=60, le=3600)


class DhanInstrumentRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=24)
    market: Market = Market.stocks
    exchange_segment: str = Field(default="NSE_EQ", min_length=3, max_length=24)
    security_id: str = Field(min_length=1, max_length=24)


class DhanFeedStartRequest(BaseModel):
    instruments: list[DhanInstrumentRequest] = Field(min_length=1, max_length=5000)
    mode: str = Field(default="quote")



@app.post("/api/backtest/ml")
def ml_walk_forward_backtest(request: AnalyzeRequest):
    try:
        instrument, frame = fetch_market_candles(request.symbol, request.market.value,
                                                  period="60d", interval="5m")
        featured = features(frame)
        result = evaluate_ml_walk_forward(featured)
        result["instrument"] = instrument.__dict__
        result["data_source"] = instrument.provider
        result["data_mode"] = "historical_walk_forward"
        return result
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"ML walk-forward evaluation unavailable: {exc}") from exc

@app.get("/api/ai/status")
def ai_status():
    return get_gemini_status()


@app.post("/api/ai/market-brief")
async def ai_market_brief(request: GeminiBriefRequest):
    if not get_gemini_status()["configured"]:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Add GEMINI_API_KEY to the backend environment.")
    analysis = request.analysis
    if analysis is None:
        try:
            analysis = await asyncio.to_thread(
                analyze_with_preserved_ml, request.symbol.upper(), request.market.value,
                paper_broker.portfolio()["equity"]
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Quantitative analysis unavailable: {exc}") from exc
    if len(json.dumps(analysis, default=str)) > 12000:
        raise HTTPException(status_code=413, detail="Analysis payload is too large for a market brief.")
    try:
        return await asyncio.to_thread(
            generate_market_brief, request.symbol.upper(), request.market.value,
            analysis, request.news_context
        )
    except GeminiNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GeminiProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/automation/status")
def automation_status():
    return automation_service.status()


@app.post("/api/automation/start")
async def automation_start(request: AutomationStartRequest):
    try:
        watchlist = [{"symbol": item.symbol.upper(), "market": item.market.value}
                     for item in request.watchlist]
        for item in watchlist:
            require_fresh_dhan_tick(item["symbol"], item["market"])
        return await automation_service.start(watchlist, request.interval_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/automation/stop")
async def automation_stop():
    return await automation_service.stop()

@app.post("/api/automation/run-once")
def autonomous_paper_run(request: AnalyzeRequest):
    try:
        report = analyze_for_autonomous_intraday(request.symbol.upper(), request.market.value,
                                                  paper_broker.portfolio()["equity"])
        proposal = report["proposal"]
        price_inr = float(proposal["entry"]) * float(report["fx_to_inr"])
        tick = paper_broker.process_price(request.symbol.upper(), request.market.value, price_inr)
        if tick.get("stop_triggered"):
            return {"status": "stop_loss_filled", "analysis": report, "order": tick["order"],
                    "live_trading_enabled": False}
        snapshot = paper_broker.portfolio()
        position = next((p for p in snapshot["positions"]
                         if p["symbol"] == request.symbol.upper() and p["market"] == request.market.value), None)
        if proposal["action"] == "SELL" and position:
            order = paper_broker.place_order(request.symbol.upper(), request.market.value,
                                             "sell", position["quantity"], price_inr,
                                             reason="autonomous_ml_exit")
            return {"status": "paper_position_closed", "analysis": report, "order": order,
                    "live_trading_enabled": False}
        if proposal["action"] != "BUY" or position:
            return {"status": "no_trade", "analysis": report,
                    "reason": "No new long entry; either the model did not signal BUY or a position is already open."}
        plan = build_paper_buy_plan(proposal, snapshot["equity"], snapshot["cash"],
                                    snapshot["capital"], report["fx_to_inr"], request.market.value)
        if not plan:
            return {"status": "no_trade", "analysis": report,
                    "reason": "Risk sizing is below the minimum tradable quantity or available cash."}
        order = paper_broker.place_order(request.symbol.upper(), request.market.value,
                                         "buy", plan["quantity"], plan["entry_inr"],
                                         stop_loss=plan["stop_loss_inr"],
                                         reason="autonomous_ml_paper_agent")
        return {"status": "paper_order_filled", "analysis": report, "order": order,
                "risk_plan": plan, "live_trading_enabled": False}
    except (PaperTradeRejected, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/market/dhan/status")
def dhan_feed_status():
    return dhan_feed_service.status()


@app.post("/api/market/dhan/start")
async def dhan_feed_start(request: DhanFeedStartRequest):
    try:
        instruments = [
            {
                "symbol": item.symbol.upper(),
                "market": item.market.value,
                "exchange_segment": item.exchange_segment.upper(),
                "security_id": item.security_id,
            }
            for item in request.instruments
        ]
        return await dhan_feed_service.start(instruments, request.mode.lower())
    except DhanFeedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/market/dhan/stop")
async def dhan_feed_stop():
    return await dhan_feed_service.stop()
