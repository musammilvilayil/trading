import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowDownRight, ArrowUpRight, Bot, CandlestickChart, CircleDollarSign, Cpu, Gauge, Layers3, RefreshCw, ShieldCheck, Wallet } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const fmt = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n ?? 0);

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [market, setMarket] = useState('crypto');
  const [symbol, setSymbol] = useState('BTC-USD');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState(null);

  async function refresh() {
    try {
      const [d, h] = await Promise.all([fetch(API + '/api/dashboard'), fetch(API + '/api/health')]);
      if (!d.ok || !h.ok) throw new Error('API unavailable');
      setDashboard(await d.json()); setHealth(await h.json()); setError('');
    } catch { setError('Backend unavailable. Start the FastAPI server on port 8000.'); }
  }
  useEffect(() => { refresh(); const id = setInterval(refresh, 12000); return () => clearInterval(id); }, []);
  async function analyze() {
    setLoading(true); setError('');
    try {
      const res = await fetch(API + '/api/analyze', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({symbol, market}) });
      if (!res.ok) throw new Error('Analysis request failed');
      setAnalysis(await res.json());
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  const metrics = useMemo(() => [
    {label:'Paper equity', value:fmt(dashboard?.equity), icon:Wallet, detail:'Cash + marked paper positions'},
    {label:'Available cash', value:fmt(dashboard?.cash), icon:CircleDollarSign, detail:'Unallocated paper capital'},
    {label:'Invested value', value:fmt(dashboard?.invested_value), icon:Layers3, detail:'At average entry price'},
    {label:'Realized P&L', value:fmt(dashboard?.realized_pnl), icon:Activity, detail:'Closed-trade P&L'},
  ], [dashboard]);
  return <main className="shell">
    <aside className="sidebar"><div className="brand"><div className="brand-icon"><CandlestickChart size={22}/></div><div><b>ATLAS</b><small>AI TRADING DESK</small></div></div>
      <div className="nav-label">WORKSPACE</div><div className="nav active"><Gauge size={17}/> Overview</div><div className="nav"><Activity size={17}/> Market intelligence</div><div className="nav"><Bot size={17}/> AI agents</div><div className="nav"><ShieldCheck size={17}/> Risk controls</div>
      <div className="sidebar-bottom"><span className="pulse"></span><div><b>Paper environment</b><small>Live execution disabled</small></div></div>
    </aside>
    <section className="content">
      <header className="topbar"><div><div className="eyebrow">PERSONAL TRADING TERMINAL</div><h1>Market overview</h1></div><button className="refresh" onClick={refresh}><RefreshCw size={15}/> Refresh</button></header>
      <div className="banner"><div className="banner-icon"><ShieldCheck size={20}/></div><div><b>Protected paper-trading mode</b><p>All orders are simulated. Live broker execution is not connected or enabled.</p></div><span className="status">SAFE MODE</span></div>
      {error && <div className="error">{error}</div>}
      <div className="section-head"><div><h2>Portfolio snapshot</h2><p>Starting virtual capital · {fmt(dashboard?.capital ?? 25000)}</p></div><span className="tag"><span className="pulse"/> {health?.status === 'ok' ? 'API connected' : 'Connecting'}</span></div>
      <div className="metrics">{metrics.map(({label,value,icon:Icon,detail})=><article className="metric" key={label}><div className="metric-top"><span>{label}</span><Icon size={17}/></div><strong>{value}</strong><small>{detail}</small></article>)}</div>
      <div className="grid">
        <article className="panel analysis"><div className="panel-title"><div><span className="eyebrow">STRATEGY WORKBENCH</span><h2>AI market analysis</h2></div><span className="tag">MOCK DATA</span></div>
          <p className="muted">Run an illustrative moving-average and momentum analysis on a sample instrument.</p>
          <div className="controls"><select value={market} onChange={e=>setMarket(e.target.value)}><option value="stocks">Stocks</option><option value="crypto">Crypto</option><option value="forex">Forex</option><option value="commodities">Commodities</option></select><input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} aria-label="Symbol"/><button onClick={analyze} disabled={loading}>{loading?'Analysing…':'Analyse market'}</button></div>
          {analysis && <div className="result"><div><small>MODEL SIGNAL</small><strong className={'signal '+analysis.signal}>{analysis.signal.toUpperCase()}</strong></div><div><small>CONFIDENCE (HEURISTIC)</small><b>{(analysis.confidence*100).toFixed(1)}%</b></div><div><small>LAST SAMPLE PRICE</small><b>{analysis.last_price.toFixed(2)}</b></div><p>{analysis.disclaimer}</p></div>}
        </article>
        <article className="panel agents"><div className="panel-title"><div><span className="eyebrow">AUTOMATION LAYER</span><h2>Agent status</h2></div><Cpu size={19}/></div>
          {[['Market research','Sample data adapter','active'],['Strategy engine','SMA + momentum rules','active'],['Risk manager','Order guardrails','active'],['Broker execution','Not connected','locked']].map(([a,b,c])=><div className="agent-row" key={a}><span className="agent-dot"/><div><b>{a}</b><small>{b}</small></div><span className={'agent-state '+c}>{c}</span></div>)}
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
