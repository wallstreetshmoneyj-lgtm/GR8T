'use strict';
const $ = (s) => document.querySelector(s);
const LWC = window.LightweightCharts;

const CHART_OPTS = {
  layout: { background: { color: '#161b22' }, textColor: '#8b97a7' },
  grid: { vertLines: { color: '#1c2430' }, horzLines: { color: '#1c2430' } },
  timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#2a3240' },
  rightPriceScale: { borderColor: '#2a3240' },
  crosshair: { mode: LWC.CrosshairMode.Normal },
};

let priceChart, candle, smaLine;
let poiLines = [];
let lastTrades = [];

function initCharts() {
  const cEl = $('#chart');
  priceChart = LWC.createChart(cEl, { ...CHART_OPTS, width: cEl.clientWidth, height: 460 });
  candle = priceChart.addCandlestickSeries({
    upColor: '#1f9d55', downColor: '#e3342f', borderVisible: false,
    wickUpColor: '#1f9d55', wickDownColor: '#e3342f',
  });
  smaLine = priceChart.addLineSeries({ color: '#d29922', lineWidth: 2, priceLineVisible: false, lastValueVisible: false });

  new ResizeObserver(() => {
    priceChart.applyOptions({ width: cEl.clientWidth });
  }).observe(document.body);
}

function gatherParams() {
  const form = $('#cfg');
  const p = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') p[el.name] = el.checked;
    else p[el.name] = el.value;
  }
  // form uses a percentage; Config wants a fraction
  if (p.risk_per_trade_pct != null) {
    p.risk_per_trade = parseFloat(p.risk_per_trade_pct) / 100;
    delete p.risk_per_trade_pct;
  }
  return p;
}

async function run(ev) {
  if (ev) ev.preventDefault();
  const btn = $('#run');
  btn.disabled = true;
  $('#status').textContent = 'Fetching data & running backtest…';
  try {
    const res = await fetch('/api/backtest', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(gatherParams()),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'backtest failed');
    render(data);
    $('#status').textContent = `Source: ${data.source}`;
  } catch (e) {
    $('#status').textContent = '⚠ ' + e.message;
    console.error(e);
  } finally {
    btn.disabled = false;
  }
}

function render(d) {
  candle.setData(d.bars);
  smaLine.setData(d.sma);
  candle.setMarkers(d.markers);
  priceChart.timeScale().fitContent();

  $('#visual').innerHTML = d.charts_html || '<div class="muted">no chart data</div>';

  const c = d.config || {};
  const tf = (x) => ({ '5min': '5m', '15min': '15m', '30min': '30m', '60min': '1h',
                       '4h': '4h', '1D': '1d', '1d': '1d' }[x] || x);
  $('#chart-title').textContent = `${d.symbol} · ${tf(c.base_tf)} · ${d.sma_period} SMA`;
  $('#meta').textContent =
    `${d.meta.start} → ${d.meta.end} · ${d.meta.n_base} ${tf(c.base_tf)} / ` +
    `${d.meta.n_mid} ${tf(c.mid_tf)} / ${d.meta.n_high} ${tf(c.high_tf)}`;

  renderStats(d.stats);
  renderTrades(d.trades);
  lastTrades = d.trades;
}

function statRow(k, v, cls = '') {
  return `<div class="k">${k}</div><div class="v ${cls}">${v}</div>`;
}

function renderStats(s) {
  const el = $('#stats');
  if (!s || !s.trades) { el.innerHTML = '<div class="k">No trades for these parameters.</div>'; return; }
  const sign = (x) => (x > 0 ? 'pos' : x < 0 ? 'neg' : '');
  el.innerHTML = [
    statRow('Trades', `${s.trades} (${s.wins}W / ${s.losses}L)`),
    statRow('Win rate', `${(s.win_rate * 100).toFixed(1)}%`),
    statRow('Expectancy', `${s.expectancy_r >= 0 ? '+' : ''}${s.expectancy_r.toFixed(3)} R`, sign(s.expectancy_r)),
    statRow('Total', `${s.total_r >= 0 ? '+' : ''}${s.total_r.toFixed(2)} R`, sign(s.total_r)),
    statRow('Avg win / loss', `+${s.avg_win_r.toFixed(2)} / ${s.avg_loss_r.toFixed(2)} R`),
    statRow('Profit factor', isFinite(s.profit_factor) ? s.profit_factor.toFixed(2) : '∞'),
    statRow('Payoff ratio', isFinite(s.payoff_ratio) ? s.payoff_ratio.toFixed(2) : '∞'),
    statRow('Max drawdown', `${s.max_drawdown_r.toFixed(2)} R (${s.max_drawdown_pct.toFixed(1)}%)`, 'neg'),
    statRow('Best / worst', `+${s.best_trade_r.toFixed(2)} / ${s.worst_trade_r.toFixed(2)} R`),
    statRow('Max consec. losses', s.max_consecutive_losses),
    statRow('Reached break-even', `${(s.breakeven_reached_rate * 100).toFixed(0)}%`),
    statRow('Avg bars held', s.avg_bars_held.toFixed(1)),
    statRow('Equity', `$${s.starting_equity.toLocaleString()} → $${Math.round(s.ending_equity).toLocaleString()}`,
            sign(s.return_pct)),
    statRow('Return', `${s.return_pct >= 0 ? '+' : ''}${s.return_pct.toFixed(1)}% @ ${s.risk_per_trade_pct}% risk`,
            sign(s.return_pct)),
  ].join('');
}

function renderTrades(trades) {
  $('#tcount').textContent = `(${trades.length})`;
  const tb = $('#trades tbody');
  tb.innerHTML = '';
  trades.forEach((t, i) => {
    const tr = document.createElement('tr');
    const rcls = t.r > 0 ? 'r-pos' : 'r-neg';
    const dcls = t.direction === 'bull' ? 'bull' : 'bear';
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${t.entry_time}</td>
      <td class="${dcls}">${t.direction === 'bull' ? 'LONG' : 'SHORT'}</td>
      <td>${t.pattern.replace(/_/g, ' ')}</td>
      <td>${t.poi_tf}</td>
      <td>${t.entry_price}</td>
      <td>${t.init_stop}</td>
      <td>${t.exit_price}</td>
      <td class="${rcls}">${t.r >= 0 ? '+' : ''}${t.r.toFixed(2)}</td>
      <td>${t.reason}</td>`;
    tr.addEventListener('click', () => selectTrade(i, tr));
    tb.appendChild(tr);
  });
}

function selectTrade(i, rowEl) {
  document.querySelectorAll('#trades tbody tr').forEach((r) => r.classList.remove('sel'));
  rowEl.classList.add('sel');
  const t = lastTrades[i];

  poiLines.forEach((l) => candle.removePriceLine(l));
  poiLines = [];
  const add = (price, color, title, style = LWC.LineStyle.Dashed) => {
    if (price == null) return;
    poiLines.push(candle.createPriceLine({ price, color, lineWidth: 1, lineStyle: style, title }));
  };
  add(t.poi_upper, '#58a6ff', 'POI top', LWC.LineStyle.Solid);
  add(t.poi_lower, '#58a6ff', 'POI bottom', LWC.LineStyle.Solid);
  add(t.entry_price, '#e6edf3', 'entry');
  add(t.init_stop, '#e3342f', 'stop');
  add(t.exit_price, '#8795a1', 'exit');
  if (t.poc != null) add(t.poc, '#d29922', 'POC', LWC.LineStyle.Dotted);

  if (t.entry_unix && t.exit_unix) {
    const pad = 6 * 3600;
    priceChart.timeScale().setVisibleRange({ from: t.entry_unix - pad, to: t.exit_unix + pad });
  }
}

async function downloadReport() {
  const btn = $('#download');
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = 'Building report…';
  try {
    const res = await fetch('/api/report', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(gatherParams()),
    });
    if (!res.ok) throw new Error('report failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gr8t_${$('#symbol').value || 'report'}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    $('#status').textContent = '⚠ ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

async function loadSymbols() {
  try {
    const r = await fetch('/api/symbols');
    const list = await r.json();
    $('#symlist').innerHTML = list.map((s) => `<option value="${s.symbol}">${s.label}</option>`).join('');
  } catch (e) { /* non-fatal */ }
}

window.addEventListener('DOMContentLoaded', () => {
  initCharts();
  loadSymbols();
  $('#cfg').addEventListener('submit', run);
  $('#download').addEventListener('click', downloadReport);
  run();  // auto-run once on load
});
