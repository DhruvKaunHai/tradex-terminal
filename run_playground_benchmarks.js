const fs = require('fs');
const path = require('path');

// 1. Load Data
const DATA_DIR = 'C:/Users/hi/OneDrive/Desktop/Trading Host/data';
const raw5m = fs.readFileSync(path.join(DATA_DIR, 'nifty50_2024_2026_5m.json'), 'utf-8');
const candles5m = JSON.parse(raw5m);

const raw15m = fs.readFileSync(path.join(DATA_DIR, 'nifty50_2024_2026_15m.json'), 'utf-8');
const candles15m = JSON.parse(raw15m);

console.log(`Loaded 5m dataset: ${candles5m.length} candles`);
console.log(`Loaded 15m dataset: ${candles15m.length} candles`);

// Technical Indicator Helper Functions
function calcEma(values, period) {
  const n = values.length;
  if (n < period) return values.slice();
  const ema = new Array(n);
  const mult = 2.0 / (period + 1);
  let sum = 0;
  for (let i = 0; i < period; i++) sum += values[i];
  ema[period - 1] = sum / period;
  for (let i = 0; i < period - 1; i++) ema[i] = values[i];
  for (let i = period; i < n; i++) {
    ema[i] = (values[i] - ema[i - 1]) * mult + ema[i - 1];
  }
  return ema;
}

function calcAtr(candles, period = 14) {
  const n = candles.length;
  if (n === 0) return [];
  const tr = new Array(n);
  tr[0] = candles[0].high - candles[0].low;
  for (let i = 1; i < n; i++) {
    const hl = candles[i].high - candles[i].low;
    const hc = Math.abs(candles[i].high - candles[i - 1].close);
    const lc = Math.abs(candles[i].low - candles[i - 1].close);
    tr[i] = Math.max(hl, hc, lc);
  }
  const atr = new Array(n);
  let sum = 0;
  for (let i = 0; i < period; i++) sum += tr[i];
  atr[period - 1] = sum / period;
  for (let i = 0; i < period - 1; i++) atr[i] = tr[i];
  for (let i = period; i < n; i++) {
    atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period;
  }
  return atr;
}

function calcSupertrend(candles, period = 10, multiplier = 3.0) {
  const n = candles.length;
  if (n === 0) return [[], []];
  const atr = calcAtr(candles, period);
  const st = new Array(n).fill(candles[0].close);
  const trend = new Array(n).fill(1);
  let upper = (candles[0].high + candles[0].low) / 2 + multiplier * atr[0];
  let lower = (candles[0].high + candles[0].low) / 2 - multiplier * atr[0];

  for (let i = 1; i < n; i++) {
    const hl2 = (candles[i].high + candles[i].low) / 2;
    let bUpper = hl2 + multiplier * atr[i];
    let bLower = hl2 - multiplier * atr[i];

    if (bLower > lower || candles[i - 1].close < lower) lower = bLower;
    if (bUpper < upper || candles[i - 1].close > upper) upper = bUpper;

    if (trend[i - 1] === 1) {
      if (candles[i].close < lower) {
        trend[i] = -1;
        st[i] = upper;
      } else {
        trend[i] = 1;
        st[i] = lower;
      }
    } else {
      if (candles[i].close > upper) {
        trend[i] = 1;
        st[i] = lower;
      } else {
        trend[i] = -1;
        st[i] = upper;
      }
    }
  }
  return [st, trend];
}

function calcRsi(values, period = 14) {
  const n = values.length;
  if (n <= period) return new Array(n).fill(50.0);
  const gains = new Array(n - 1);
  const losses = new Array(n - 1);
  for (let i = 1; i < n; i++) {
    const diff = values[i] - values[i - 1];
    gains[i - 1] = diff > 0 ? diff : 0;
    losses[i - 1] = diff < 0 ? -diff : 0;
  }
  const rsi = new Array(n).fill(50.0);
  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

  rsi[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < n; i++) {
    avgGain = (avgGain * (period - 1) + gains[i - 1]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period;
    rsi[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return rsi;
}

function calcVwap(candles) {
  const n = candles.length;
  const vwap = new Array(n).fill(0.0);
  let curDay = "";
  let cSum = 0.0, cCnt = 0;
  for (let i = 0; i < n; i++) {
    const dStr = new Date((candles[i].time + 19800) * 1000).toISOString().slice(0, 10);
    if (dStr !== curDay) {
      curDay = dStr;
      cSum = (candles[i].high + candles[i].low + candles[i].close) / 3;
      cCnt = 1;
    } else {
      cSum += (candles[i].high + candles[i].low + candles[i].close) / 3;
      cCnt++;
    }
    vwap[i] = cSum / cCnt;
  }
  return vwap;
}

function getIstTime(epochSec) {
  const d = new Date((epochSec + 19800) * 1000);
  return {
    dayKey: d.toISOString().slice(0, 10),
    hh: d.getUTCHours(),
    mm: d.getUTCMinutes(),
    tInt: d.getUTCHours() * 100 + d.getUTCMinutes()
  };
}

// Performance Metrics Calculator
function computeMetrics(trades, candles) {
  if (!trades || trades.length === 0) {
    return { total_trades: 0, win_rate: 0, profit_factor: 0, net_pnl: 0, net_inr: 0, max_dd_pts: 0, max_dd_pct: 0, expectancy: 0, sharpe: 0, recovery: 0 };
  }
  const total = trades.length;
  const wins = trades.filter(t => t.pnl > 0);
  const losses = trades.filter(t => t.pnl <= 0);
  const win_rate = Math.round((wins.length / total) * 10000) / 100;

  const gross_win = wins.reduce((acc, t) => acc + t.pnl, 0);
  const gross_loss = Math.abs(losses.reduce((acc, t) => acc + t.pnl, 0));
  const profit_factor = gross_loss > 0 ? Math.round((gross_win / gross_loss) * 100) / 100 : 99.0;
  const net_pnl = Math.round((gross_win - gross_loss) * 100) / 100;
  const net_inr = Math.round(net_pnl * 75 * 100) / 100;

  // Drawdown
  let peak = 0, cum = 0, max_dd = 0;
  trades.forEach(t => {
    cum += t.pnl;
    if (cum > peak) peak = cum;
    const dd = peak - cum;
    if (dd > max_dd) max_dd = dd;
  });
  const max_dd_pts = Math.round(max_dd * 100) / 100;
  const max_dd_pct = peak > 0 ? Math.round((max_dd / (candles[0].close + peak)) * 10000) / 100 : 0;
  const recovery = max_dd_pts > 0 ? Math.round((net_pnl / max_dd_pts) * 100) / 100 : (net_pnl > 0 ? 99.0 : 0);
  const expectancy = Math.round((net_pnl / total) * 100) / 100;

  // Simple Sharpe Approximation
  const avgPnl = net_pnl / total;
  const variance = trades.reduce((acc, t) => acc + Math.pow(t.pnl - avgPnl, 2), 0) / total;
  const std = Math.sqrt(variance) || 1;
  const sharpe = Math.round((avgPnl / std) * Math.sqrt(250 * 5) * 100) / 100; // Annualized

  return {
    total_trades: total,
    wins: wins.length,
    losses: losses.length,
    win_rate,
    profit_factor,
    net_pnl,
    net_inr,
    max_dd_pts,
    max_dd_pct,
    expectancy,
    sharpe,
    recovery
  };
}

// -------------------------------------------------------------
// 16 STRATEGY ENGINES
// -------------------------------------------------------------

// Strategy 1: Classical 15m ORB (9:15 - 9:30 range breakout)
function strat_01_orb_15m(candles) {
  const n = candles.length;
  const trades = [];
  const byDay = new Map();
  for (let i = 0; i < n; i++) {
    const t = getIstTime(candles[i].time);
    if (!byDay.has(t.dayKey)) byDay.set(t.dayKey, []);
    byDay.get(t.dayKey).push({ idx: i, c: candles[i], t });
  }

  byDay.forEach(dayBars => {
    if (dayBars.length < 5) return;
    const orbBars = dayBars.filter(b => b.t.tInt >= 915 && b.t.tInt < 930);
    if (orbBars.length === 0) return;
    const orH = Math.max(...orbBars.map(b => b.c.high));
    const orL = Math.min(...orbBars.map(b => b.c.low));
    const orMid = (orH + orL) / 2;
    const postBars = dayBars.filter(b => b.t.tInt >= 930 && b.t.tInt <= 1515);

    let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;
    for (const b of postBars) {
      const c = b.c;
      if (!inPos) {
        if (c.close > orH) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = orMid;
          tp = entryP + (entryP - sl) * 2.0;
        } else if (c.close < orL) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = orMid;
          tp = entryP - (sl - entryP) * 2.0;
        }
      } else {
        if (side === 'BUY') {
          if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; break; }
          if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; break; }
        } else {
          if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; break; }
          if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; break; }
        }
        if (b.t.tInt >= 1515) {
          const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
          trades.push({ pnl: Math.round(pnl * 100) / 100 });
          break;
        }
      }
    }
  });
  return computeMetrics(trades, candles);
}

// Strategy 2: 9/21 EMA Cross on 5m
function strat_02_ema_cross_9_21(candles) {
  const closes = candles.map(c => c.close);
  const e9 = calcEma(closes, 9);
  const e21 = calcEma(closes, 21);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 22; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (e9[i - 1] <= e21[i - 1] && e9[i] > e21[i]) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = entryP - 1.5 * atr[i];
          tp = entryP + 2.5 * atr[i];
        } else if (e9[i - 1] >= e21[i - 1] && e9[i] < e21[i]) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = entryP + 1.5 * atr[i];
          tp = entryP - 2.5 * atr[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
        else if (e9[i] < e21[i]) { trades.push({ pnl: Math.round((c.close - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
        else if (e9[i] > e21[i]) { trades.push({ pnl: Math.round((entryP - c.close) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 3: Supertrend (10, 3) Intraday
function strat_03_supertrend_10_3(candles) {
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i - 1] === -1 && trend[i] === 1) {
          inPos = true; side = 'BUY'; entryP = c.close; sl = st[i];
        } else if (trend[i - 1] === 1 && trend[i] === -1) {
          inPos = true; side = 'SELL'; entryP = c.close; sl = st[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        } else if (st[i] > sl) {
          sl = st[i];
        }
      } else {
        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        } else if (st[i] < sl) {
          sl = st[i];
        }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 4: RSI 14 Mean Reversion (30/70)
function strat_04_rsi_mean_reversion(candles) {
  const closes = candles.map(c => c.close);
  const rsi = calcRsi(closes, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (rsi[i - 1] < 30 && rsi[i] >= 30) {
          inPos = true; side = 'BUY'; entryP = c.close;
        } else if (rsi[i - 1] > 70 && rsi[i] <= 70) {
          inPos = true; side = 'SELL'; entryP = c.close;
        }
      }
    } else {
      if (side === 'BUY' && (rsi[i] >= 55 || t.tInt >= 1515)) {
        trades.push({ pnl: Math.round((c.close - entryP) * 100) / 100 });
        inPos = false;
      } else if (side === 'SELL' && (rsi[i] <= 45 || t.tInt >= 1515)) {
        trades.push({ pnl: Math.round((entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 5: Bollinger Bands Mean Reversion
function strat_05_bollinger_bands(candles) {
  const closes = candles.map(c => c.close);
  const trades = [];
  const bbP = 20;
  let inPos = false, entryP = 0;

  for (let i = bbP; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - bbP + 1; j <= i; j++) sum += closes[j];
    const sma = sum / bbP;
    let vSum = 0;
    for (let j = i - bbP + 1; j <= i; j++) vSum += Math.pow(closes[j] - sma, 2);
    const std = Math.sqrt(vSum / bbP);
    const lower = sma - 2.0 * std;
    const upper = sma + 2.0 * std;
    const c = candles[i];
    const t = getIstTime(c.time);

    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445 && c.close <= lower) {
        inPos = true; entryP = c.close;
      }
    } else {
      if (c.close >= sma || t.tInt >= 1515) {
        trades.push({ pnl: Math.round((c.close - entryP) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 6: Dual Supertrend + Intraday VWAP Confluence
function strat_06_dual_supertrend_vwap(candles) {
  const [stFast, trFast] = calcSupertrend(candles, 7, 2.0);
  const [stSlow, trSlow] = calcSupertrend(candles, 14, 3.0);
  const vwap = calcVwap(candles);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 925 && t.tInt <= 1430) {
        if (trFast[i] === 1 && trSlow[i] === 1 && c.close > vwap[i] && trFast[i - 1] !== 1) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = Math.max(stFast[i], entryP - 1.5 * atr[i]);
          tp = entryP + (entryP - sl) * 2.2;
        } else if (trFast[i] === -1 && trSlow[i] === -1 && c.close < vwap[i] && trFast[i - 1] !== -1) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = Math.min(stFast[i], entryP + 1.5 * atr[i]);
          tp = entryP - (sl - entryP) * 2.2;
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl || trFast[i] === -1) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
        else if (stFast[i] > sl) sl = stFast[i];
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl || trFast[i] === 1) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
        else if (stFast[i] < sl) sl = stFast[i];
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 7: Apex Institutional 4-EMA Ribbon (8/21/55/200) + Volatility Squeeze
function strat_07_apex_institutional_ribbon(candles) {
  const closes = candles.map(c => c.close);
  const e8 = calcEma(closes, 8);
  const e21 = calcEma(closes, 21);
  const e55 = calcEma(closes, 55);
  const e200 = calcEma(closes, 200);
  const atr = calcAtr(candles, 14);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 205; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        const isBullAligned = e8[i] > e21[i] && e21[i] > e55[i] && c.close > e200[i] && c.close > vwap[i];
        const isBearAligned = e8[i] < e21[i] && e21[i] < e55[i] && c.close < e200[i] && c.close < vwap[i];
        if (isBullAligned && (e8[i - 1] <= e21[i - 1] || c.close > candles[i - 1].high)) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = Math.min(e55[i], entryP - 1.5 * atr[i]);
          tp = entryP + (entryP - sl) * 2.8;
        } else if (isBearAligned && (e8[i - 1] >= e21[i - 1] || c.close < candles[i - 1].low)) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = Math.max(e55[i], entryP + 1.5 * atr[i]);
          tp = entryP - (sl - entryP) * 2.8;
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl || c.close < e55[i]) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
        else if (e21[i] > sl) sl = e21[i];
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl || c.close > e55[i]) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
        else if (e21[i] < sl) sl = e21[i];
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 8: APEX NEW / Symphony v2 (5m mode)
function strat_08_apex_symphony_v2_5m(candles) {
  const closes = candles.map(c => c.close);
  const [stLine, stTrend] = calcSupertrend(candles, 14, 3.5);
  const eFast = calcEma(closes, 9);
  const eSlow = calcEma(closes, 21);
  const rsi = calcRsi(closes, 14);
  const atr = calcAtr(candles, 14);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, posSide = null, entryP = 0, sl = 0, tp = 0, initRisk = 0;

  for (let i = 25; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (posSide === 'BUY') {
        // Stage 1: Breakeven ratchet
        if (c.high >= entryP + initRisk * 1.0) sl = Math.max(sl, entryP + initRisk * 0.25);
        // Stage 2: Profit lock
        if (c.high >= entryP + initRisk * 2.0) sl = Math.max(sl, entryP + initRisk * 1.10);
        // Supertrend trail
        if (stTrend[i] === 1 && stLine[i] > sl) sl = stLine[i];

        if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
        else if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (stTrend[i] === -1 && eFast[i] < eSlow[i]) { trades.push({ pnl: Math.round((c.close - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= entryP - initRisk * 1.0) sl = Math.min(sl, entryP - initRisk * 0.25);
        if (c.low <= entryP - initRisk * 2.0) sl = Math.min(sl, entryP - initRisk * 1.10);
        if (stTrend[i] === -1 && stLine[i] < sl) sl = stLine[i];

        if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
        else if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (stTrend[i] === 1 && eFast[i] > eSlow[i]) { trades.push({ pnl: Math.round((entryP - c.close) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = posSide === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        const curAtr = Math.max(atr[i], 15.0);
        const buySignal = (stTrend[i] === 1 && stTrend[i - 1] === -1) ||
                          (stTrend[i] === 1 && eFast[i] > eSlow[i] && eFast[i - 1] <= eSlow[i - 1] && c.close > vwap[i] && rsi[i] >= 55);
        const sellSignal = (stTrend[i] === -1 && stTrend[i - 1] === 1) ||
                           (stTrend[i] === -1 && eFast[i] < eSlow[i] && eFast[i - 1] >= eSlow[i - 1] && c.close < vwap[i] && rsi[i] <= 45);

        if (buySignal) {
          inPos = true; posSide = 'BUY'; entryP = c.close;
          initRisk = curAtr * 1.8;
          sl = entryP - initRisk;
          tp = entryP + initRisk * 3.5;
        } else if (sellSignal) {
          inPos = true; posSide = 'SELL'; entryP = c.close;
          initRisk = curAtr * 1.8;
          sl = entryP + initRisk;
          tp = entryP - initRisk * 3.5;
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 9: APEX NEW / Symphony v2 on 15m mode
function strat_09_apex_symphony_v2_15m(candles) {
  const closes = candles.map(c => c.close);
  const [stLine, stTrend] = calcSupertrend(candles, 10, 3.0);
  const eFast = calcEma(closes, 8);
  const eSlow = calcEma(closes, 21);
  const rsi = calcRsi(closes, 14);
  const atr = calcAtr(candles, 14);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, posSide = null, entryP = 0, sl = 0, tp = 0, initRisk = 0;

  for (let i = 25; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (posSide === 'BUY') {
        if (c.high >= entryP + initRisk * 1.1) sl = Math.max(sl, entryP + initRisk * 0.20);
        if (c.high >= entryP + initRisk * 2.2) sl = Math.max(sl, entryP + initRisk * 1.20);
        if (stTrend[i] === 1 && stLine[i] > sl) sl = stLine[i];

        if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
        else if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (stTrend[i] === -1 && eFast[i] < eSlow[i]) { trades.push({ pnl: Math.round((c.close - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= entryP - initRisk * 1.1) sl = Math.min(sl, entryP - initRisk * 0.20);
        if (c.low <= entryP - initRisk * 2.2) sl = Math.min(sl, entryP - initRisk * 1.20);
        if (stTrend[i] === -1 && stLine[i] < sl) sl = stLine[i];

        if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
        else if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (stTrend[i] === 1 && eFast[i] > eSlow[i]) { trades.push({ pnl: Math.round((entryP - c.close) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = posSide === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        const curAtr = Math.max(atr[i], 20.0);
        const buySignal = (stTrend[i] === 1 && stTrend[i - 1] === -1) ||
                          (stTrend[i] === 1 && eFast[i] > eSlow[i] && eFast[i - 1] <= eSlow[i - 1] && c.close > vwap[i] && rsi[i] >= 52);
        const sellSignal = (stTrend[i] === -1 && stTrend[i - 1] === 1) ||
                           (stTrend[i] === -1 && eFast[i] < eSlow[i] && eFast[i - 1] >= eSlow[i - 1] && c.close < vwap[i] && rsi[i] <= 48);

        if (buySignal) {
          inPos = true; posSide = 'BUY'; entryP = c.close;
          initRisk = curAtr * 1.6;
          sl = entryP - initRisk;
          tp = entryP + initRisk * 4.5;
        } else if (sellSignal) {
          inPos = true; posSide = 'SELL'; entryP = c.close;
          initRisk = curAtr * 1.6;
          sl = entryP + initRisk;
          tp = entryP - initRisk * 4.5;
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 10: Adaptive Dual ORB (15m + 30m Breakout Confirmation)
function strat_10_adaptive_dual_orb(candles) {
  const n = candles.length;
  const trades = [];
  const byDay = new Map();
  for (let i = 0; i < n; i++) {
    const t = getIstTime(candles[i].time);
    if (!byDay.has(t.dayKey)) byDay.set(t.dayKey, []);
    byDay.get(t.dayKey).push({ idx: i, c: candles[i], t });
  }

  byDay.forEach(dayBars => {
    if (dayBars.length < 8) return;
    const b15 = dayBars.filter(b => b.t.tInt >= 915 && b.t.tInt < 930);
    const b30 = dayBars.filter(b => b.t.tInt >= 915 && b.t.tInt < 945);
    if (b15.length === 0 || b30.length === 0) return;
    const orH15 = Math.max(...b15.map(b => b.c.high));
    const orL15 = Math.min(...b15.map(b => b.c.low));
    const orH30 = Math.max(...b30.map(b => b.c.high));
    const orL30 = Math.min(...b30.map(b => b.c.low));
    const postBars = dayBars.filter(b => b.t.tInt >= 945 && b.t.tInt <= 1515);

    let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;
    for (const b of postBars) {
      const c = b.c;
      if (!inPos) {
        if (c.close > orH30 && c.close > orH15) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = orL15 + (orH15 - orL15) * 0.5; // Mid of OR15
          tp = entryP + (entryP - sl) * 2.2;
        } else if (c.close < orL30 && c.close < orL15) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = orL15 + (orH15 - orL15) * 0.5;
          tp = entryP - (sl - entryP) * 2.2;
        }
      } else {
        if (side === 'BUY') {
          if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; break; }
          if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; break; }
        } else {
          if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; break; }
          if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; break; }
        }
        if (b.t.tInt >= 1515) {
          const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
          trades.push({ pnl: Math.round(pnl * 100) / 100 });
          break;
        }
      }
    }
  });
  return computeMetrics(trades, candles);
}

// Strategy 11: Inside Candle (Harami) Breakout + VWAP + 21 EMA
function strat_11_inside_candle_vwap(candles) {
  const closes = candles.map(c => c.close);
  const e21 = calcEma(closes, 21);
  const vwap = calcVwap(candles);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 25; i < candles.length - 1; i++) {
    const prev = candles[i - 1];
    const cur = candles[i];
    const t = getIstTime(cur.time);

    if (!inPos) {
      if (t.tInt >= 930 && t.tInt <= 1430) {
        // Inside bar condition
        const isInside = cur.high <= prev.high && cur.low >= prev.low;
        if (isInside) {
          const nxt = candles[i + 1];
          if (nxt.close > prev.high && nxt.close > vwap[i] && nxt.close > e21[i]) {
            inPos = true; side = 'BUY'; entryP = nxt.close;
            sl = prev.low;
            tp = entryP + (entryP - sl) * 2.0;
          } else if (nxt.close < prev.low && nxt.close < vwap[i] && nxt.close < e21[i]) {
            inPos = true; side = 'SELL'; entryP = nxt.close;
            sl = prev.high;
            tp = entryP - (sl - entryP) * 2.0;
          }
        }
      }
    } else {
      const c = cur;
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 12: Triple Momentum Fusion (RSI 14 + EMA 9/21 + VWAP Trend)
function strat_12_triple_momentum_fusion(candles) {
  const closes = candles.map(c => c.close);
  const e9 = calcEma(closes, 9);
  const e21 = calcEma(closes, 21);
  const rsi = calcRsi(closes, 14);
  const vwap = calcVwap(candles);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 25; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 925 && t.tInt <= 1430) {
        if (e9[i] > e21[i] && c.close > vwap[i] && rsi[i] > 55 && rsi[i - 1] <= 55) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = entryP - 1.6 * atr[i];
          tp = entryP + 3.2 * atr[i];
        } else if (e9[i] < e21[i] && c.close < vwap[i] && rsi[i] < 45 && rsi[i - 1] >= 45) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = entryP + 1.6 * atr[i];
          tp = entryP - 3.2 * atr[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl || rsi[i] < 45) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl || rsi[i] > 55) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 13: MACD Histogram Acceleration + 50 EMA Filter
function strat_13_macd_histogram_acceleration(candles) {
  const closes = candles.map(c => c.close);
  const e12 = calcEma(closes, 12);
  const e26 = calcEma(closes, 26);
  const macd = e12.map((v, i) => v - e26[i]);
  const signal = calcEma(macd, 9);
  const hist = macd.map((v, i) => v - signal[i]);
  const e50 = calcEma(closes, 50);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 55; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 930 && t.tInt <= 1430) {
        if (c.close > e50[i] && hist[i - 1] <= 0 && hist[i] > 0 && macd[i] > 0) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = entryP - 1.5 * atr[i];
          tp = entryP + 3.0 * atr[i];
        } else if (c.close < e50[i] && hist[i - 1] >= 0 && hist[i] < 0 && macd[i] < 0) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = entryP + 1.5 * atr[i];
          tp = entryP - 3.0 * atr[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl || hist[i] < 0) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl || hist[i] > 0) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 14: VWAP Standard Deviation Bands Squeeze & Reversal
function strat_14_vwap_bands_squeeze(candles) {
  const vwap = calcVwap(candles);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 20; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    const upper2 = vwap[i] + 2.0 * atr[i];
    const lower2 = vwap[i] - 2.0 * atr[i];

    if (!inPos) {
      if (t.tInt >= 930 && t.tInt <= 1430) {
        if (c.low <= lower2 && c.close > lower2) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = c.low - 0.5 * atr[i];
          tp = vwap[i];
        } else if (c.high >= upper2 && c.close < upper2) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = c.high + 0.5 * atr[i];
          tp = vwap[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 15: Chaikin Money Flow & 4-EMA Ribbon Breakout
function strat_15_cmf_ema_ribbon(candles) {
  const closes = candles.map(c => c.close);
  const e8 = calcEma(closes, 8);
  const e21 = calcEma(closes, 21);
  const e55 = calcEma(closes, 55);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0;

  for (let i = 60; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 925 && t.tInt <= 1430) {
        if (e8[i] > e21[i] && e21[i] > e55[i] && c.close > candles[i - 1].high && (c.high - c.low) > 1.2 * atr[i]) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = e55[i];
          tp = entryP + (entryP - sl) * 2.5;
        } else if (e8[i] < e21[i] && e21[i] < e55[i] && c.close < candles[i - 1].low && (c.high - c.low) > 1.2 * atr[i]) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = e55[i];
          tp = entryP - (sl - entryP) * 2.5;
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Strategy 16: Multi-Timeframe (MTF) Trend Confluence Champion
// 15m Trend Direction (Supertrend 10,3 + 50 EMA) + 5m Micro Trigger (8/21 EMA Cross + VWAP + 2-Stage Ratchet Stop)
function strat_16_mtf_confluence_champion(candles5m, candles15m) {
  // Map 15m trend onto 5m time
  const [st15, trend15] = calcSupertrend(candles15m, 10, 3.0);
  const closes15 = candles15m.map(c => c.close);
  const e50_15 = calcEma(closes15, 50);

  const t15Map = new Map();
  for (let i = 0; i < candles15m.length; i++) {
    t15Map.set(candles15m[i].time, { trend: trend15[i], ema50: e50_15[i] });
  }

  const closes5m = candles5m.map(c => c.close);
  const e8 = calcEma(closes5m, 8);
  const e21 = calcEma(closes5m, 21);
  const vwap5m = calcVwap(candles5m);
  const atr5m = calcAtr(candles5m, 14);
  const rsi5m = calcRsi(closes5m, 14);
  const trades = [];

  let inPos = false, side = null, entryP = 0, sl = 0, tp = 0, initRisk = 0;

  for (let i = 50; i < candles5m.length; i++) {
    const c = candles5m[i];
    const t = getIstTime(c.time);

    // Look up 15m bar
    const b15Time = Math.floor(c.time / 900) * 900;
    const mtf15 = t15Map.get(b15Time) || { trend: 0, ema50: c.close };

    if (inPos) {
      if (side === 'BUY') {
        // Stage 1 Breakeven (+1R -> lock +0.25R)
        if (c.high >= entryP + initRisk * 1.0) sl = Math.max(sl, entryP + initRisk * 0.25);
        // Stage 2 Profit Lock (+2R -> lock +1.2R)
        if (c.high >= entryP + initRisk * 2.0) sl = Math.max(sl, entryP + initRisk * 1.20);
        // EMA 21 structural trail
        if (e21[i] > sl) sl = e21[i];

        if (c.low <= sl) { trades.push({ pnl: Math.round((sl - entryP) * 100) / 100 }); inPos = false; }
        else if (c.high >= tp) { trades.push({ pnl: Math.round((tp - entryP) * 100) / 100 }); inPos = false; }
        else if (e8[i] < e21[i] && rsi5m[i] < 45) { trades.push({ pnl: Math.round((c.close - entryP) * 100) / 100 }); inPos = false; }
      } else {
        if (c.low <= entryP - initRisk * 1.0) sl = Math.min(sl, entryP - initRisk * 0.25);
        if (c.low <= entryP - initRisk * 2.0) sl = Math.min(sl, entryP - initRisk * 1.20);
        if (e21[i] < sl) sl = e21[i];

        if (c.high >= sl) { trades.push({ pnl: Math.round((entryP - sl) * 100) / 100 }); inPos = false; }
        else if (c.low <= tp) { trades.push({ pnl: Math.round((entryP - tp) * 100) / 100 }); inPos = false; }
        else if (e8[i] > e21[i] && rsi5m[i] > 55) { trades.push({ pnl: Math.round((entryP - c.close) * 100) / 100 }); inPos = false; }
      }
      if (inPos && t.tInt >= 1515) {
        const pnl = side === 'BUY' ? (c.close - entryP) : (entryP - c.close);
        trades.push({ pnl: Math.round(pnl * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        const curAtr = Math.max(atr5m[i], 16.0);
        const buyMtf = mtf15.trend === 1 && c.close > mtf15.ema50;
        const sellMtf = mtf15.trend === -1 && c.close < mtf15.ema50;

        const buy5m = (e8[i] > e21[i] && e8[i - 1] <= e21[i - 1] && c.close > vwap5m[i] && rsi5m[i] >= 54);
        const sell5m = (e8[i] < e21[i] && e8[i - 1] >= e21[i - 1] && c.close < vwap5m[i] && rsi5m[i] <= 46);

        if (buyMtf && buy5m) {
          inPos = true; side = 'BUY'; entryP = c.close;
          initRisk = curAtr * 1.6;
          sl = entryP - initRisk;
          tp = entryP + initRisk * 3.6;
        } else if (sellMtf && sell5m) {
          inPos = true; side = 'SELL'; entryP = c.close;
          initRisk = curAtr * 1.6;
          sl = entryP + initRisk;
          tp = entryP - initRisk * 3.6;
        }
      }
    }
  }
  return computeMetrics(trades, candles5m);
}

// -------------------------------------------------------------
// RUN ALL 16 STRATEGIES & TABULATE
// -------------------------------------------------------------
console.log('\n========================================================================================');
console.log('       QUANTITATIVE PLAYGROUND: BENCHMARKING 16 STRATEGIES ON NIFTY 50 (2024-2026)');
console.log('========================================================================================\n');

const suite = [
  { id: 'S01', name: 'Classical 15m ORB', run: () => strat_01_orb_15m(candles5m) },
  { id: 'S02', name: '9/21 EMA Cross (5m)', run: () => strat_02_ema_cross_9_21(candles5m) },
  { id: 'S03', name: 'Supertrend (10, 3) (5m)', run: () => strat_03_supertrend_10_3(candles5m) },
  { id: 'S04', name: 'RSI 14 Mean Reversion (5m)', run: () => strat_04_rsi_mean_reversion(candles5m) },
  { id: 'S05', name: 'Bollinger Bands 20,2 (5m)', run: () => strat_05_bollinger_bands(candles5m) },
  { id: 'S06', name: 'Dual Supertrend + VWAP (5m)', run: () => strat_06_dual_supertrend_vwap(candles5m) },
  { id: 'S07', name: 'Apex Institutional 4-EMA Ribbon (5m)', run: () => strat_07_apex_institutional_ribbon(candles5m) },
  { id: 'S08', name: 'Apex Symphony v2 (5m Auto)', run: () => strat_08_apex_symphony_v2_5m(candles5m) },
  { id: 'S09', name: 'Apex Symphony v2 (15m Macro)', run: () => strat_09_apex_symphony_v2_15m(candles15m) },
  { id: 'S10', name: 'Adaptive Dual ORB (15m+30m)', run: () => strat_10_adaptive_dual_orb(candles5m) },
  { id: 'S11', name: 'Inside Candle Harami + VWAP (5m)', run: () => strat_11_inside_candle_vwap(candles5m) },
  { id: 'S12', name: 'Triple Momentum Fusion (5m)', run: () => strat_12_triple_momentum_fusion(candles5m) },
  { id: 'S13', name: 'MACD Hist + 50 EMA Filter (5m)', run: () => strat_13_macd_histogram_acceleration(candles5m) },
  { id: 'S14', name: 'VWAP Bands Reversal (5m)', run: () => strat_14_vwap_bands_squeeze(candles5m) },
  { id: 'S15', name: 'CMF + 4-EMA Breakout (5m)', run: () => strat_15_cmf_ema_ribbon(candles5m) },
  { id: 'S16', name: 'MTF Trend Confluence Champion (15m+5m)', run: () => strat_16_mtf_confluence_champion(candles5m, candles15m) }
];

const results = [];
suite.forEach(s => {
  const m = s.run();
  results.push({ id: s.id, name: s.name, ...m });
});

// Sort by Net Return Points descending
results.sort((a, b) => b.net_pnl - a.net_pnl);

console.log('RANK | ID  | STRATEGY NAME                       | TRADES | WIN RATE | PROFIT FACTOR | NET RETURN (PTS) | NET RETURN (INR)  | MAX DRAWDOWN | SHARPE | RECOVERY');
console.log('------------------------------------------------------------------------------------------------------------------------------------------------------');
results.forEach((r, idx) => {
  const rank = String(idx + 1).padStart(4, ' ');
  const id = r.id.padEnd(4, ' ');
  const name = r.name.padEnd(35, ' ');
  const trades = String(r.total_trades).padStart(6, ' ');
  const wr = (r.win_rate.toFixed(1) + '%').padStart(8, ' ');
  const pf = (r.profit_factor.toFixed(2)).padStart(13, ' ');
  const sign = r.net_pnl >= 0 ? '+' : '';
  const pts = (sign + r.net_pnl.toLocaleString('en-IN', { minimumFractionDigits: 1 })).padStart(16, ' ');
  const inr = ((r.net_inr >= 0 ? '+₹' : '-₹') + Math.abs(r.net_inr).toLocaleString('en-IN')).padStart(17, ' ');
  const dd = ('-' + r.max_dd_pts.toFixed(1) + ' pts').padStart(12, ' ');
  const sharpe = (r.sharpe.toFixed(2)).padStart(6, ' ');
  const rec = (r.recovery.toFixed(1) + 'x').padStart(8, ' ');

  console.log(`${rank} | ${id} | ${name} | ${trades} | ${wr} | ${pf} | ${pts} | ${inr} | ${dd} | ${sharpe} | ${rec}`);
});

fs.writeFileSync('C:/Users/hi/OneDrive/Desktop/Trading Host/benchmark_results.json', JSON.stringify(results, null, 2));
console.log('\nResults saved to benchmark_results.json');
