import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowDownRight, ArrowUpRight, Bot, CandlestickChart, CircleDollarSign, Cpu, Gauge, Layers3, Play, RefreshCw, ShieldCheck, Wallet, FlaskConical } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const fmt = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n ?? 0);

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [market, setMarket] = useState('stocks');
  const [symbol, setSymbol] = useState('RELIANCE');
  const [analysis, setAnalysis] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [useMl, setUseMl] = useState(true);
  const [autoBusy, setAutoBusy] = useState(false);
  const [autoStatus, setAutoStatus] = useState(null);
  const [backtestBusy, setBacktestBusy] = useState(false);
  const [orderBusy, setOrderBusy] = useState(false);
  const [quantity, setQuantity] = useState('1');
  const [priceInr, setPriceInr] = useState('');
  const [stopInr, setStopInr] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [health, setHealth] = useState(null);

  async function refresh() {
    try {
      const [d, h, a] = await Promise.all([fetch(API + '/api/dashboard'), fetch(API + '/api/health'), fetch(API + '/api/automation/status')]);
      if (!d.ok || !h.ok) throw new Error('API unavailable');
      setDashboard(await d.json()); setHealth(await h.json());
      if (a.ok) setAutoStatus(await a.json());
      setError('');
    } catch { setError('Backend unavailable. Start the FastAPI server on port 8000.'); }
  }
  useEffect(() => { refresh(); const id = setInterval(refresh, 12000); return () => clearInterval(id); }, []);

  async function analyze() {
    setLoading(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + (useMl ? '/api/analyze/ml' : '/api/analyze'), {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({symbol, market})
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Analysis request failed');
      setAnalysis(body);
      const nativePrice = body.proposal?.entry ?? body.last_price;
      if (nativePrice && body.instrument?.quote_currency === 'INR') setPriceInr(String(nativePrice));
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  async function runAutonomous() {
    setAutoBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/automation/run-once', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,market})});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Autonomous cycle failed');
      setAnalysis(body.analysis || null);
      setNotice(body.status === 'paper_order_filled' ? 'AI agent submitted a risk-approved simulated paper order.' : body.reason || 'No trade was placed.');
      await refresh();
    } catch(e) { setError(e.message); } finally { setAutoBusy(false); }
  }

  async function startAutomation() {
    setAutoBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/automation/start', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({watchlist:[{symbol,market}],interval_seconds:300})});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not start autonomous worker');
      setAutoStatus(body); setNotice('Autonomous paper worker started. It scans this instrument every 5 minutes while the API process remains running.');
    } catch(e) { setError(e.message); } finally { setAutoBusy(false); await refresh(); }
  }

  async function stopAutomation() {
    setAutoBusy(true); setError('');
    try {
      const res = await fetch(API + '/api/automation/stop', {method:'POST'});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not stop worker');
      setAutoStatus(body); setNotice('Autonomous paper worker stopped.');
    } catch(e) { setError(e.message); } finally { setAutoBusy(false); await refresh(); }
  }

  async function runBacktest() {
    setBacktestBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/backtest', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,market,period:'2y',interval:'1d'})});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Backtest failed');
      setBacktest(body);
    } catch(e) { setError(e.message); } finally { setBacktestBusy(false); }
  }

  async function placeOrder() {
    setOrderBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/paper/orders', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        symbol, market, side:'buy', quantity:Number(quantity), price_inr:Number(priceInr), stop_loss_inr:Number(stopInr)
      })});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Paper order rejected');
      setNotice('Simulated order filled: ' + body.id);
      await refresh();
    } catch(e) { setError(e.message); } finally { setOrderBusy(false); }
  }

  const signal = analysis?.proposal?.action?.toLowerCase() || analysis?.signal;
  const confidence = analysis?.proposal?.confidence ?? analysis?.confidence;
  const lastPrice = analysis?.proposal?.entry ?? analysis?.last_price;
  const metrics = useMemo(() => [
    {label:'Paper equity', value:fmt(dashboard?.equity), icon:Wallet, detail:'Cash + marked paper positions'},
    {label:'Available cash', value:fmt(dashboard?.cash), icon:CircleDollarSign, detail:'Unallocated paper capital'},
    {label:'Invested value', value:fmt(dashboard?.invested_value), icon:Layers3, detail:'Marked in INR'},
    {label:'Total P&L', value:fmt(dashboard?.total_pnl), icon:Activity, detail:'Realized + unrealized'},
  ], [dashboard]);

  return <main className="shell">
    <aside className="sidebar"><div className="brand"><div className="brand-icon"><CandlestickChart size={22}/></div><div><b>ATLAS</b><small>AI TRADING DESK</small></div></div>
      <div className="nav-label">WORKSPACE</div><div className="nav active"><Gauge size={17}/> Overview</div><div className="nav"><Activity size={17}/> Market intelligence</div><div className="nav"><Bot size={17}/> AI agents</div><div className="nav"><ShieldCheck size={17}/> Risk controls</div>
      <div className="sidebar-bottom"><span className="pulse"></span><div><b>Paper environment</b><small>Live execution disabled</small></div></div>
    </aside>
    <section className="content">
      <header className="topbar"><div><div className="eyebrow">PERSONAL TRADING TERMINAL</div><h1>Market overview</h1></div><button className="refresh" onClick={refresh}><RefreshCw size={15}/> Refresh</button></header>
      <div className="banner"><div className="banner-icon"><ShieldCheck size={20}/></div><div><b>Protected paper-trading mode</b><p>Persistent simulated account · ₹25,000 starting capital · Live broker execution disabled.</p></div><span className="status">SAFE MODE</span></div>
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      <div className="section-head"><div><h2>Portfolio snapshot</h2><p>Starting virtual capital · {fmt(dashboard?.capital ?? 25000)}</p></div><span className="tag"><span className="pulse"/> {health?.status === 'ok' ? 'API connected' : 'Connecting'}</span></div>
      <div className="metrics">{metrics.map(({label,value,icon:Icon,detail})=><article className="metric" key={label}><div className="metric-top"><span>{label}</span><Icon size={17}/></div><strong>{value}</strong><small>{detail}</small></article>)}</div>
      <div className="grid">
        <article className="panel analysis"><div className="panel-title"><div><span className="eyebrow">STRATEGY WORKBENCH</span><h2>AI market analysis</h2></div><span className="tag">{autoStatus?.running ? 'AUTO SCANNING' : 'HISTORICAL FEED'}</span></div>
          <p className="muted">Choose a market and provider symbol. ML analysis uses historical Yahoo Finance candles. Autonomous mode is paper-only and scans every 5 minutes.</p>
          <div className="controls"><select value={market} onChange={e=>setMarket(e.target.value)}><option value="stocks">Stocks</option><option value="crypto">Crypto</option><option value="forex">Forex</option><option value="commodities">Commodities</option></select><input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} aria-label="Symbol"/><label className="ml-toggle"><input type="checkbox" checked={useMl} onChange={e=>setUseMl(e.target.checked)}/> V1 ML</label><button onClick={analyze} disabled={loading}>{loading?'Analysing…':'Analyse'}</button></div>
          {analysis && <div className="result"><div><small>MODEL SIGNAL</small><strong className={'signal '+signal}>{(signal || 'wait').toUpperCase()}</strong></div><div><small>CONFIDENCE</small><b>{confidence == null ? '—' : (confidence*100).toFixed(1)+'%'}</b></div><div><small>LAST / ENTRY</small><b>{lastPrice == null ? '—' : Number(lastPrice).toFixed(2)}</b></div><p>{analysis.disclaimer || analysis.data_source + ' · ' + analysis.data_mode}</p></div>}
          <div className="action-row"><button onClick={runAutonomous} disabled={autoBusy}><Play size={14}/>{autoBusy?'Running agent…':'Run one AI cycle'}</button><button className="secondary" onClick={autoStatus?.running ? stopAutomation : startAutomation} disabled={autoBusy}>{autoStatus?.running ? 'Stop autonomous' : 'Start autonomous'}</button><button className="secondary" onClick={runBacktest} disabled={backtestBusy}><FlaskConical size={14}/>{backtestBusy?'Testing…':'Backtest 2 years'}</button></div>
        </article>
        <article className="panel agents"><div className="panel-title"><div><span className="eyebrow">AUTOMATION LAYER</span><h2>Agent status</h2></div><Cpu size={19}/></div>
          {[['Market research','Yahoo Finance historical adapter','active'],['ML strategy','HistGradientBoosting + EMA/VWAP','active'],['Risk manager','0.5% trade risk / 2% daily guard','active'],['Paper broker','SQLite ledger + simulated fills','active'],['Live execution','Not implemented / disabled','locked']].map(([a,b,c])=><div className="agent-row" key={a}><span className="agent-dot"/><div><b>{a}</b><small>{b}</small></div><span className={'agent-state '+c}>{c}</span></div>)}
        </article>
      </div>
      <div className="grid">
        <article className="panel"><div className="panel-title"><div><span className="eyebrow">PAPER EXECUTION</span><h2>Place simulated buy</h2></div><Wallet size={18}/></div>
          <p className="muted">Price and stop must be entered in INR. For non-INR instruments, convert the quote price before placing a paper order.</p>
          <div className="trade-form"><label>Quantity<input type="number" min="0.000001" step="any" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label><label>Entry price (₹)<input type="number" min="0" step="any" value={priceInr} onChange={e=>setPriceInr(e.target.value)} placeholder="INR converted price"/></label><label>Stop-loss (₹)<input type="number" min="0" step="any" value={stopInr} onChange={e=>setStopInr(e.target.value)} placeholder="Below entry"/></label><button onClick={placeOrder} disabled={orderBusy || !priceInr || !stopInr}>{orderBusy?'Submitting…':'Place paper buy'}</button></div>
        </article>
        <article className="panel"><div className="panel-title"><div><span className="eyebrow">BACKTEST RESULTS</span><h2>Historical strategy test</h2></div><FlaskConical size={18}/></div>
          {backtest ? <div className="backtest-stats"><div><small>NET RETURN</small><b>{backtest.total_return_pct}%</b></div><div><small>MAX DRAWDOWN</small><b>{backtest.max_drawdown_pct}%</b></div><div><small>WIN RATE</small><b>{backtest.win_rate_pct}%</b></div><div><small>TRADES</small><b>{backtest.closed_trades}</b></div><p>{backtest.account_currency} quote currency · {backtest.execution_assumptions?.signal_execution} · fees/slippage included.</p></div> : <div className="empty"><FlaskConical size={22}/><b>No backtest run</b><span>Run a 2-year EMA crossover simulation above.</span></div>}
        </article>
      </div>
      <article className="panel orders"><div className="panel-title"><div><span className="eyebrow">ACTIVITY</span><h2>Recent paper orders</h2></div><span className="tag">SIMULATED</span></div>
        {dashboard?.recent_orders?.length ? <div className="order-list">{dashboard.recent_orders.map(o=><div className="order" key={o.id}><span className={'side '+o.side}>{o.side==='buy'?<ArrowUpRight size={15}/>:<ArrowDownRight size={15}/>}</span><b>{o.symbol}</b><span>{o.side.toUpperCase()}</span><span>{o.quantity} @ {o.price}</span><small>{o.status}</small></div>)}</div> : <div className="empty"><Activity size={22}/><b>No paper orders yet</b><span>Approved simulated orders will appear here.</span></div>}
      </article>
      <footer>ATLAS AI · Research and simulation only · Not investment advice</footer>
    </section>
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
