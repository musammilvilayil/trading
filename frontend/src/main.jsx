import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowDownRight, ArrowUpRight, Bot, CandlestickChart, CircleDollarSign, Cpu, Gauge, Layers3, Play, RefreshCw, ShieldCheck, Wallet, FlaskConical, BrainCircuit, Sparkles } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const fmt = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n ?? 0);

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [market, setMarket] = useState('stocks');
  const [symbol, setSymbol] = useState('RELIANCE');
  const [analysis, setAnalysis] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [mlBacktest, setMlBacktest] = useState(null);
  const [mlBacktestBusy, setMlBacktestBusy] = useState(false);
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
  const [geminiStatus, setGeminiStatus] = useState(null);
  const [geminiBrief, setGeminiBrief] = useState(null);
  const [geminiBusy, setGeminiBusy] = useState(false);
  const [dhanStatus, setDhanStatus] = useState(null);
  const [dhanSecurityId, setDhanSecurityId] = useState('');
  const [dhanSegment, setDhanSegment] = useState('NSE_EQ');
  const [dhanBusy, setDhanBusy] = useState(false);

  async function refresh() {
    try {
      const [d, h, a, g, df] = await Promise.all([fetch(API + '/api/dashboard'), fetch(API + '/api/health'), fetch(API + '/api/automation/status'), fetch(API + '/api/ai/status'), fetch(API + '/api/market/dhan/status')]);
      if (!d.ok || !h.ok) throw new Error('API unavailable');
      setDashboard(await d.json()); setHealth(await h.json());
      if (a.ok) setAutoStatus(await a.json());
      if (g.ok) setGeminiStatus(await g.json());
      if (df.ok) setDhanStatus(await df.json());
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
      if (body.entry_price_inr) {
        setPriceInr(String(body.entry_price_inr));
        const atr = Number(body.proposal?.atr || 0);
        const entryInr = Number(body.entry_price_inr);
        if (atr > 0) setStopInr(String(entryInr - Math.max(atr * Number(body.fx_to_inr || 1), entryInr * 0.002)));
      } else if (nativePrice && body.instrument?.quote_currency === 'INR') {
        setPriceInr(String(nativePrice));
      }
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }

  async function startDhanFeed() {
    setDhanBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/market/dhan/start', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          mode:'quote',
          instruments:[{symbol, market:'stocks', exchange_segment:dhanSegment, security_id:dhanSecurityId.trim()}]
        })
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not start Dhan market feed');
      setDhanStatus(body);
      setNotice('Dhan live quote feed requested. Paper positions mapped to this symbol will be marked from incoming INR quotes.');
    } catch(e) { setError(e.message); }
    finally { setDhanBusy(false); await refresh(); }
  }

  async function stopDhanFeed() {
    setDhanBusy(true); setError('');
    try {
      const res = await fetch(API + '/api/market/dhan/stop', {method:'POST'});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not stop Dhan market feed');
      setDhanStatus(body);
      setNotice('Dhan live market feed stopped.');
    } catch(e) { setError(e.message); }
    finally { setDhanBusy(false); await refresh(); }
  }

  async function runGeminiBrief() {
    setGeminiBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/ai/market-brief', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({symbol, market, analysis, news_context:[]})
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Gemini market brief failed');
      setGeminiBrief(body);
    } catch(e) { setError(e.message); }
    finally { setGeminiBusy(false); }
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

  async function closePosition(position) {
    setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/paper/orders', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        symbol:position.symbol, market:position.market, side:'sell',
        quantity:Number(position.quantity), price_inr:Number(position.last_price)
      })});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not close paper position');
      setNotice('Paper position closed: ' + body.id);
      await refresh();
    } catch(e) { setError(e.message); }
  }

  async function runMlBacktest() {
    setMlBacktestBusy(true); setError(''); setNotice('');
    try {
      const res = await fetch(API + '/api/backtest/ml', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,market})});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'ML walk-forward evaluation failed');
      setMlBacktest(body);
    } catch(e) { setError(e.message); } finally { setMlBacktestBusy(false); }
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
          <div className="action-row"><button onClick={runAutonomous} disabled={autoBusy}><Play size={14}/>{autoBusy?'Running agent…':'Run one AI cycle'}</button><button className="secondary" onClick={autoStatus?.running ? stopAutomation : startAutomation} disabled={autoBusy}>{autoStatus?.running ? 'Stop autonomous' : 'Start autonomous'}</button><button className="secondary" onClick={runBacktest} disabled={backtestBusy}><FlaskConical size={14}/>{backtestBusy?'Testing…':'EMA backtest 2 years'}</button><button className="secondary" onClick={runMlBacktest} disabled={mlBacktestBusy}><FlaskConical size={14}/>{mlBacktestBusy?'Evaluating…':'ML walk-forward'}</button></div>
        </article>
        <article className="panel agents"><div className="panel-title"><div><span className="eyebrow">AUTOMATION LAYER</span><h2>Agent status</h2></div><Cpu size={19}/></div>
          {[['Market research','Yahoo Finance historical adapter','active'],['ML strategy','HistGradientBoosting + EMA/VWAP','active'],['Risk manager','0.5% trade risk / 2% daily guard','active'],['Paper broker','SQLite ledger + simulated fills','active'],['Live execution','Not implemented / disabled','locked']].map(([a,b,c])=><div className="agent-row" key={a}><span className="agent-dot"/><div><b>{a}</b><small>{b}</small></div><span className={'agent-state '+c}>{c}</span></div>)}
        </article>
      </div>
      <article className="panel dhan-panel">
        <div className="panel-title"><div><span className="eyebrow">REAL-TIME MARKET DATA</span><h2>DhanHQ live feed</h2></div><Activity size={19}/></div>
        <p className="muted">Optional DhanHQ v2 WebSocket quotes. Incoming INR prices update mapped paper positions and evaluate protective exits. This connection cannot place real broker orders.</p>
        <div className="controls dhan-controls">
          <select value={dhanSegment} onChange={e=>setDhanSegment(e.target.value)} aria-label="Dhan exchange segment">
            <option value="NSE_EQ">NSE Equity</option><option value="BSE_EQ">BSE Equity</option><option value="NSE_FNO">NSE F&amp;O</option><option value="MCX_COMM">MCX Commodity</option>
          </select>
          <input value={dhanSecurityId} onChange={e=>setDhanSecurityId(e.target.value.replace(/[^0-9]/g,''))} placeholder="Dhan Security ID" aria-label="Dhan Security ID"/>
          <button onClick={dhanStatus?.running ? stopDhanFeed : startDhanFeed} disabled={dhanBusy || (!dhanStatus?.running && (!dhanStatus?.configured || !dhanSecurityId.trim()))}>
            {dhanBusy ? 'Connecting…' : dhanStatus?.running ? 'Stop feed' : 'Connect live feed'}
          </button>
        </div>
        <div className="dhan-feed-state">
          <span className={'agent-dot '+(dhanStatus?.connected?'':'offline')}></span>
          <b>{dhanStatus?.connected ? 'Connected' : dhanStatus?.running ? 'Connecting / reconnecting' : 'Disconnected'}</b>
          <small>{dhanStatus?.configured ? 'Credentials configured on backend' : 'Add DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN to backend .env'}</small>
          <span className="tag">{dhanStatus?.received_ticks || 0} TICKS</span>
        </div>
        {dhanStatus?.latest_ticks?.length ? <div className="dhan-ticks">{dhanStatus.latest_ticks.slice(-5).reverse().map((tick,i)=><div className="dhan-tick" key={tick.symbol+tick.received_at+i}><b>{tick.symbol}</b><strong>{fmt(tick.last_price)}</strong><small>{tick.exchange_time ? new Date(tick.exchange_time).toLocaleTimeString() : 'Exchange time unavailable'}</small>{tick.paper_exit && <span className="agent-state">PAPER EXIT</span>}</div>)}</div> : <div className="empty"><Activity size={20}/><b>No live ticks received</b><span>Enter the exact Dhan security ID to subscribe to a symbol.</span></div>}
        {dhanStatus?.last_error && <p className="feed-error">{dhanStatus.last_error}</p>}
      </article>
      <article className="panel gemini-panel">
        <div className="panel-title"><div><span className="eyebrow">GENERATIVE AI INTELLIGENCE</span><h2>Gemini market brief</h2></div><BrainCircuit size={19}/></div>
        <div className="gemini-toolbar"><p className="muted">{geminiStatus?.configured ? 'Gemini is connected. Generate an advisory explanation of the selected instrument and quantitative ML output.' : 'Gemini API key is not configured. Add GEMINI_API_KEY to the backend environment to enable this panel.'}</p><button onClick={runGeminiBrief} disabled={geminiBusy || !geminiStatus?.configured}><Sparkles size={14}/>{geminiBusy ? 'Thinking…' : 'Generate brief'}</button></div>
        {geminiBrief?.brief && <div className="gemini-content">
          <div className="gemini-summary"><div><small>OVERALL BIAS</small><b className={'bias '+geminiBrief.brief.overall_bias}>{geminiBrief.brief.overall_bias.toUpperCase()}</b></div><div><small>CONFIDENCE</small><b>{geminiBrief.brief.confidence.toUpperCase()}</b></div><div><small>NEWS SENTIMENT</small><b>{geminiBrief.brief.news_sentiment.replaceAll('_',' ').toUpperCase()}</b></div><div><small>ML ALIGNMENT</small><b>{geminiBrief.brief.signal_alignment.replaceAll('_',' ').toUpperCase()}</b></div></div>
          <p>{geminiBrief.brief.summary}</p><h3>Technical interpretation</h3><p>{geminiBrief.brief.technical_interpretation}</p>
          <div className="gemini-columns"><div><h3>Key factors</h3><ul>{geminiBrief.brief.key_factors.map((x,i)=><li key={i}>{x}</li>)}</ul></div><div><h3>Risks</h3><ul>{geminiBrief.brief.risks.map((x,i)=><li key={i}>{x}</li>)}</ul></div><div><h3>Bull case</h3><p>{geminiBrief.brief.bull_case}</p></div><div><h3>Bear case</h3><p>{geminiBrief.brief.bear_case}</p></div></div>
          <small className="gemini-disclaimer">{geminiBrief.disclaimer} · {geminiBrief.model}</small>
        </div>}
        {!geminiBrief && <div className="empty"><BrainCircuit size={22}/><b>No Gemini brief generated</b><span>Gemini explains supplied analysis; it does not place or approve trades.</span></div>}
      </article>
      <div className="grid">
        <article className="panel"><div className="panel-title"><div><span className="eyebrow">PAPER EXECUTION</span><h2>Place simulated buy</h2></div><Wallet size={18}/></div>
          <p className="muted">Price and stop must be entered in INR. For non-INR instruments, convert the quote price before placing a paper order.</p>
          <div className="trade-form"><label>Quantity<input type="number" min="0.000001" step="any" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label><label>Entry price (₹)<input type="number" min="0" step="any" value={priceInr} onChange={e=>setPriceInr(e.target.value)} placeholder="INR converted price"/></label><label>Stop-loss (₹)<input type="number" min="0" step="any" value={stopInr} onChange={e=>setStopInr(e.target.value)} placeholder="Below entry"/></label><button onClick={placeOrder} disabled={orderBusy || !priceInr || !stopInr}>{orderBusy?'Submitting…':'Place paper buy'}</button></div>
        </article>
        <article className="panel"><div className="panel-title"><div><span className="eyebrow">BACKTEST RESULTS</span><h2>Historical strategy test</h2></div><FlaskConical size={18}/></div>
          {backtest ? <div className="backtest-stats"><div><small>NET RETURN</small><b>{backtest.total_return_pct}%</b></div><div><small>MAX DRAWDOWN</small><b>{backtest.max_drawdown_pct}%</b></div><div><small>WIN RATE</small><b>{backtest.win_rate_pct}%</b></div><div><small>TRADES</small><b>{backtest.closed_trades}</b></div><p>{backtest.account_currency} quote currency · {backtest.execution_assumptions?.signal_execution} · fees/slippage included.</p></div> : <div className="empty"><FlaskConical size={22}/><b>No backtest run</b><span>Run a 2-year EMA crossover simulation above.</span></div>}
        </article>
      </div>
      <article className="panel ml-evaluation"><div className="panel-title"><div><span className="eyebrow">MODEL VALIDATION</span><h2>Out-of-sample ML evaluation</h2></div><Cpu size={18}/></div>
        {mlBacktest ? <div className="backtest-stats"><div><small>ACCURACY</small><b>{mlBacktest.metrics.accuracy_pct}%</b></div><div><small>PRECISION</small><b>{mlBacktest.metrics.precision_pct}%</b></div><div><small>RECALL</small><b>{mlBacktest.metrics.recall_pct}%</b></div><div><small>F1 SCORE</small><b>{mlBacktest.metrics.f1_pct}%</b></div><div><small>ROC-AUC</small><b>{mlBacktest.metrics.roc_auc_pct == null ? 'N/A' : mlBacktest.metrics.roc_auc_pct+'%'}</b></div><div><small>FOLDS / ROWS</small><b>{mlBacktest.fold_count} / {mlBacktest.rows_evaluated}</b></div><p>Expanding-window out-of-sample classifier evaluation · {mlBacktest.instrument?.provider_symbol} · Not strategy returns.</p></div> : <div className="empty"><Cpu size={22}/><b>No ML evaluation yet</b><span>Run an expanding-window evaluation before trusting model signals.</span></div>}
      </article>
      <article className="panel positions"><div className="panel-title"><div><span className="eyebrow">OPEN EXPOSURE</span><h2>Paper positions</h2></div><span className="tag">{dashboard?.positions?.length || 0} OPEN</span></div>
        {dashboard?.positions?.length ? <div className="position-list">{dashboard.positions.map(p=><div className="position" key={p.symbol}><div><b>{p.symbol}</b><small>{p.market} · {p.quantity} units · stop {fmt(p.stop_loss)}</small></div><div><b>{fmt(p.last_price)}</b><small>Avg cost {fmt(p.average_price)}</small></div><button className="secondary" onClick={()=>closePosition(p)}>Close</button></div>)}</div> : <div className="empty"><Wallet size={22}/><b>No open positions</b><span>Paper holdings will appear here.</span></div>}
      </article>
      <article className="panel orders"><div className="panel-title"><div><span className="eyebrow">ACTIVITY</span><h2>Recent paper orders</h2></div><span className="tag">SIMULATED</span></div>
        {dashboard?.recent_orders?.length ? <div className="order-list">{dashboard.recent_orders.map(o=><div className="order" key={o.id}><span className={'side '+o.side}>{o.side==='buy'?<ArrowUpRight size={15}/>:<ArrowDownRight size={15}/>}</span><b>{o.symbol}</b><span>{o.side.toUpperCase()}</span><span>{o.quantity} @ {o.price}</span><small>{o.status}</small></div>)}</div> : <div className="empty"><Activity size={22}/><b>No paper orders yet</b><span>Approved simulated orders will appear here.</span></div>}
      </article>
      <footer>ATLAS AI · Historical provider data · FX converted to INR for paper risk sizing · Not investment advice</footer>
    </section>
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
