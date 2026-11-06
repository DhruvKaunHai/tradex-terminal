const fs = require('fs');
const path = require('path');

const DATA_PATH = 'C:/Users/hi/OneDrive/Desktop/Trading Host/data/nifty50_2024_2026_5m.json';
const raw = fs.readFileSync(DATA_PATH, 'utf-8');
const candles = JSON.parse(raw);
console.log(`Loaded 5m Dataset: ${candles.length} candles`);

// Helper math
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
  let avgGain = 0, avgLoss = 0;
  for (let i = 0; i < period; i++) {
    avgGain += gains[i];
    avgLoss += losses[i];
  }
  avgGain /= period;
  avgLoss /= period;
  const rsi = new Array(n).fill(50.0);
  rsi[period] = avgLoss === 0 ? 100 : 100 - (100 / (1 + (avgGain / avgLoss)));
  for (let i = period + 1; i < n; i++) {
    avgGain = (avgGain * (period - 1) + gains[i - 1]) / period;
    avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period;
    rsi[i] = avgLoss === 0 ? 100 : 100 - (100 / (1 + (avgGain / avgLoss)));
  }
  return rsi;
}

function calcVwap(candles) {
  const n = candles.length;
  const vwap = new Array(n);
  let cumVol = 0, cumVolPrice = 0, curDay = '';

  for (let i = 0; i < n; i++) {
    const d = new Date(candles[i].time * 1000);
    const dayKey = `${d.getUTCFullYear()}-${d.getUTCMonth()}-${d.getUTCDate()}`;
    if (dayKey !== curDay) {
      curDay = dayKey;
      cumVol = 0;
      cumVolPrice = 0;
    }
    const vol = candles[i].volume || 1000;
    const typPrice = (candles[i].high + candles[i].low + candles[i].close) / 3.0;
    cumVolPrice += typPrice * vol;
    cumVol += vol;
    vwap[i] = cumVolPrice / (cumVol || 1);
  }
  return vwap;
}

function calcAdx(candles, period = 14) {
  const n = candles.length;
  if (n < period * 2) return new Array(n).fill(25.0);
  const plusDm = new Array(n).fill(0);
  const minusDm = new Array(n).fill(0);
  const tr = new Array(n).fill(0);

  tr[0] = candles[0].high - candles[0].low;
  for (let i = 1; i < n; i++) {
    const upMove = candles[i].high - candles[i - 1].high;
    const downMove = candles[i - 1].low - candles[i].low;
    plusDm[i] = (upMove > downMove && upMove > 0) ? upMove : 0;
    minusDm[i] = (downMove > upMove && downMove > 0) ? downMove : 0;
    const hl = candles[i].high - candles[i].low;
    const hc = Math.abs(candles[i].high - candles[i - 1].close);
    const lc = Math.abs(candles[i].low - candles[i - 1].close);
    tr[i] = Math.max(hl, hc, lc);
  }

  const smoothTr = calcEma(tr, period);
  const smoothPlus = calcEma(plusDm, period);
  const smoothMinus = calcEma(minusDm, period);

  const dx = new Array(n).fill(0);
  for (let i = 0; i < n; i++) {
    const pDi = smoothTr[i] > 0 ? (smoothPlus[i] / smoothTr[i]) * 100 : 0;
    const mDi = smoothTr[i] > 0 ? (smoothMinus[i] / smoothTr[i]) * 100 : 0;
    const sum = pDi + mDi;
    dx[i] = sum > 0 ? (Math.abs(pDi - mDi) / sum) * 100 : 0;
  }
  return calcEma(dx, period);
}

function getIstTime(epochSec) {
  const d = new Date((epochSec + 19800) * 1000);
  const hrs = d.getUTCHours();
  const mins = d.getUTCMinutes();
  const tInt = hrs * 100 + mins;
  const dayKey = `${d.getUTCFullYear()}-${d.getUTCMonth() + 1}-${d.getUTCDate()}`;
  return { hrs, mins, tInt, dayKey };
}

function computeMetrics(trades, candles) {
  const total = trades.length;
  if (total === 0) {
    return { total_trades: 0, wins: 0, losses: 0, win_rate: 0, profit_factor: 0, net_pnl: 0, net_inr: 0, max_dd_pts: 0, sharpe: 0, recovery: 0 };
  }
  const wins = trades.filter(t => t.pnl > 0);
  const losses = trades.filter(t => t.pnl <= 0);
  const win_rate = Math.round((wins.length / total) * 10000) / 100;
  const gross_win = wins.reduce((acc, t) => acc + t.pnl, 0);
  const gross_loss = Math.abs(losses.reduce((acc, t) => acc + t.pnl, 0));
  const profit_factor = gross_loss > 0 ? Math.round((gross_win / gross_loss) * 100) / 100 : 99.0;
  const net_pnl = Math.round((gross_win - gross_loss) * 100) / 100;
  const net_inr = Math.round(net_pnl * 75 * 100) / 100;

  let peak = 0, cum = 0, max_dd = 0;
  trades.forEach(t => {
    cum += t.pnl;
    if (cum > peak) peak = cum;
    const dd = peak - cum;
    if (dd > max_dd) max_dd = dd;
  });
  const max_dd_pts = Math.round(max_dd * 100) / 100;
  const recovery = max_dd_pts > 0 ? Math.round((net_pnl / max_dd_pts) * 100) / 100 : 0;

  const avgPnl = net_pnl / total;
  const variance = trades.reduce((acc, t) => acc + Math.pow(t.pnl - avgPnl, 2), 0) / total;
  const std = Math.sqrt(variance) || 1;
  const sharpe = Math.round((avgPnl / std) * Math.sqrt(250 * 5) * 100) / 100;

  return { total_trades: total, wins: wins.length, losses: losses.length, win_rate, profit_factor, net_pnl, net_inr, max_dd_pts, sharpe, recovery };
}

// -------------------------------------------------------------------------------------------------
// 16 CANDIDATES EVALUATED STRICTLY ON 5-MINUTE CANDLES
// -------------------------------------------------------------------------------------------------

// Bot 01: Supertrend (10, 3.0) Pure 5m
function bot_01_supertrend_10_3(candles) {
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;
  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i - 1] === -1 && trend[i] === 1) { inPos = true; side = 'BUY'; entryP = c.close; sl = st[i]; }
        else if (trend[i - 1] === 1 && trend[i] === -1) { inPos = true; side = 'SELL'; entryP = c.close; sl = st[i]; }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) { trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 }); inPos = false; }
        else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1) { trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 }); inPos = false; }
        else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 02: Supertrend (7, 2.0) Fast Scalper 5m
function bot_02_supertrend_7_2(candles) {
  const [st, trend] = calcSupertrend(candles, 7, 2.0);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;
  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i - 1] === -1 && trend[i] === 1) { inPos = true; side = 'BUY'; entryP = c.close; sl = st[i]; }
        else if (trend[i - 1] === 1 && trend[i] === -1) { inPos = true; side = 'SELL'; entryP = c.close; sl = st[i]; }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) { trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 }); inPos = false; }
        else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1) { trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 }); inPos = false; }
        else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 03: Dual Supertrend (7/2 + 14/3) + VWAP 5m
function bot_03_dual_supertrend_vwap(candles) {
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
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 04: Apex Institutional 4-EMA Ribbon (8/21/55/200) + VWAP 5m
function bot_04_apex_institutional_ribbon(candles) {
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
        const isBull = e8[i] > e21[i] && e21[i] > e55[i] && c.close > e200[i] && c.close > vwap[i];
        const isBear = e8[i] < e21[i] && e21[i] < e55[i] && c.close < e200[i] && c.close < vwap[i];
        if (isBull && (e8[i - 1] <= e21[i - 1] || c.close > candles[i - 1].high)) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = Math.min(e55[i], entryP - 1.5 * atr[i]);
          tp = entryP + (entryP - sl) * 2.8;
        } else if (isBear && (e8[i - 1] >= e21[i - 1] || c.close < candles[i - 1].low)) {
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
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 05: 9/21 EMA Cross on 5m
function bot_05_ema_cross_9_21(candles) {
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
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 06: 5m Classical ORB (9:15-9:30 range breakout on 5m) + VWAP Filter
function bot_06_orb_5m_vwap(candles) {
  const vwap = calcVwap(candles);
  const trades = [];
  const byDay = new Map();
  for (let i = 0; i < candles.length; i++) {
    const t = getIstTime(candles[i].time);
    if (!byDay.has(t.dayKey)) byDay.set(t.dayKey, []);
    byDay.get(t.dayKey).push({ idx: i, c: candles[i], t, vwap: vwap[i] });
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
        if (c.close > orH && c.close > b.vwap) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = orMid;
          tp = entryP + (entryP - sl) * 2.2;
        } else if (c.close < orL && c.close < b.vwap) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = orMid;
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
          trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
          break;
        }
      }
    }
  });
  return computeMetrics(trades, candles);
}

// Bot 07: 5m Supertrend (10, 3) + Intraday VWAP Confluence
function bot_07_supertrend_vwap(candles) {
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i] === 1 && trend[i - 1] === -1 && c.close > vwap[i]) {
          inPos = true; side = 'BUY'; entryP = c.close; sl = st[i];
        } else if (trend[i] === -1 && trend[i - 1] === 1 && c.close < vwap[i]) {
          inPos = true; side = 'SELL'; entryP = c.close; sl = st[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        } else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        } else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 08: 5m Supertrend (10, 3) + 200 EMA Institutional Bias
function bot_08_supertrend_ema200(candles) {
  const closes = candles.map(c => c.close);
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const e200 = calcEma(closes, 200);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;

  for (let i = 205; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i] === 1 && trend[i - 1] === -1 && c.close > e200[i]) {
          inPos = true; side = 'BUY'; entryP = c.close; sl = st[i];
        } else if (trend[i] === -1 && trend[i - 1] === 1 && c.close < e200[i]) {
          inPos = true; side = 'SELL'; entryP = c.close; sl = st[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        } else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        } else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 09: 5m Supertrend (10, 3) + ADX Trend Strength Filter (> 20)
function bot_09_supertrend_adx(candles) {
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const adx = calcAdx(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;

  for (let i = 30; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i] === 1 && trend[i - 1] === -1 && adx[i] >= 20) {
          inPos = true; side = 'BUY'; entryP = c.close; sl = st[i];
        } else if (trend[i] === -1 && trend[i - 1] === 1 && adx[i] >= 20) {
          inPos = true; side = 'SELL'; entryP = c.close; sl = st[i];
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        } else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        } else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 10: 5m Supertrend (10, 3) + VWAP + 2-Stage Dynamic Ratchet Stop
function bot_10_supertrend_vwap_ratchet(candles) {
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const vwap = calcVwap(candles);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, initRisk = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (side === 'BUY') {
        // Stage 1 Breakeven: when price reaches +1.0R, move SL to entry + 0.2R
        if (c.high >= entryP + initRisk * 1.0) sl = Math.max(sl, entryP + initRisk * 0.20);
        // Stage 2 Profit Lock: when price reaches +2.0R, move SL to entry + 1.15R
        if (c.high >= entryP + initRisk * 2.0) sl = Math.max(sl, entryP + initRisk * 1.15);
        // Trailing stop follows Supertrend
        if (st[i] > sl) sl = st[i];

        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        }
      } else {
        if (c.low <= entryP - initRisk * 1.0) sl = Math.min(sl, entryP - initRisk * 0.20);
        if (c.low <= entryP - initRisk * 2.0) sl = Math.min(sl, entryP - initRisk * 1.15);
        if (st[i] < sl) sl = st[i];

        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        }
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i] === 1 && trend[i - 1] === -1 && c.close > vwap[i]) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(entryP - sl, 15.0);
        } else if (trend[i] === -1 && trend[i - 1] === 1 && c.close < vwap[i]) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(sl - entryP, 15.0);
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 11: 5m Dual Supertrend (Fast 7/2 + Slow 10/3) + 2-Stage Ratchet
function bot_11_dual_supertrend_ratchet(candles) {
  const [stFast, trFast] = calcSupertrend(candles, 7, 2.0);
  const [stSlow, trSlow] = calcSupertrend(candles, 10, 3.0);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, initRisk = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (side === 'BUY') {
        if (c.high >= entryP + initRisk * 1.0) sl = Math.max(sl, entryP + initRisk * 0.25);
        if (c.high >= entryP + initRisk * 2.0) sl = Math.max(sl, entryP + initRisk * 1.20);
        if (stFast[i] > sl) sl = stFast[i];

        if (c.low <= sl || trFast[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        }
      } else {
        if (c.low <= entryP - initRisk * 1.0) sl = Math.min(sl, entryP - initRisk * 0.25);
        if (c.low <= entryP - initRisk * 2.0) sl = Math.min(sl, entryP - initRisk * 1.20);
        if (stFast[i] < sl) sl = stFast[i];

        if (c.high >= sl || trFast[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        }
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 925 && t.tInt <= 1430) {
        if (trSlow[i] === 1 && trFast[i] === 1 && trFast[i - 1] === -1 && c.close > vwap[i]) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = stFast[i];
          initRisk = Math.max(entryP - sl, 15.0);
        } else if (trSlow[i] === -1 && trFast[i] === -1 && trFast[i - 1] === 1 && c.close < vwap[i]) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = stFast[i];
          initRisk = Math.max(sl - entryP, 15.0);
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 12: 5m Apex Trend Symphony (Supertrend 10/3 + EMA Ribbon 8/21 + VWAP)
function bot_12_supertrend_ema_ribbon(candles) {
  const closes = candles.map(c => c.close);
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const e8 = calcEma(closes, 8);
  const e21 = calcEma(closes, 21);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;

  for (let i = 25; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        if (trend[i] === 1 && e8[i] > e21[i] && c.close > vwap[i] && (trend[i - 1] !== 1 || e8[i - 1] <= e21[i - 1])) {
          inPos = true; side = 'BUY'; entryP = c.close; sl = Math.max(st[i], e21[i] - 10);
        } else if (trend[i] === -1 && e8[i] < e21[i] && c.close < vwap[i] && (trend[i - 1] !== -1 || e8[i - 1] >= e21[i - 1])) {
          inPos = true; side = 'SELL'; entryP = c.close; sl = Math.min(st[i], e21[i] + 10);
        }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1 || e8[i] < e21[i]) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        } else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1 || e8[i] > e21[i]) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        } else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 13: 5m Supertrend (10, 3) + 3-EMA (8/21/55) + 2-Stage Ratchet
function bot_13_supertrend_3ema_ratchet(candles) {
  const closes = candles.map(c => c.close);
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const e8 = calcEma(closes, 8);
  const e21 = calcEma(closes, 21);
  const e55 = calcEma(closes, 55);
  const vwap = calcVwap(candles);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, initRisk = 0;

  for (let i = 60; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (side === 'BUY') {
        if (c.high >= entryP + initRisk * 1.0) sl = Math.max(sl, entryP + initRisk * 0.25);
        if (c.high >= entryP + initRisk * 2.0) sl = Math.max(sl, entryP + initRisk * 1.20);
        if (st[i] > sl) sl = st[i];

        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        }
      } else {
        if (c.low <= entryP - initRisk * 1.0) sl = Math.min(sl, entryP - initRisk * 0.25);
        if (c.low <= entryP - initRisk * 2.0) sl = Math.min(sl, entryP - initRisk * 1.20);
        if (st[i] < sl) sl = st[i];

        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        }
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        const isBull = trend[i] === 1 && e8[i] > e21[i] && e21[i] > e55[i] && c.close > vwap[i];
        const isBear = trend[i] === -1 && e8[i] < e21[i] && e21[i] < e55[i] && c.close < vwap[i];
        if (isBull && (trend[i - 1] !== 1 || e8[i - 1] <= e21[i - 1])) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(entryP - sl, 15.0);
        } else if (isBear && (trend[i - 1] !== -1 || e8[i - 1] >= e21[i - 1])) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(sl - entryP, 15.0);
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 14: 5m Supertrend (10, 3) + Multi-Stage Dynamic Ratchet + Time Exit (3:15 PM)
function bot_14_supertrend_10_3_opt_ratchet(candles) {
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, initRisk = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (side === 'BUY') {
        if (c.high >= entryP + initRisk * 1.2) sl = Math.max(sl, entryP + initRisk * 0.30);
        if (c.high >= entryP + initRisk * 2.5) sl = Math.max(sl, entryP + initRisk * 1.50);
        if (st[i] > sl) sl = st[i];

        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        }
      } else {
        if (c.low <= entryP - initRisk * 1.2) sl = Math.min(sl, entryP - initRisk * 0.30);
        if (c.low <= entryP - initRisk * 2.5) sl = Math.min(sl, entryP - initRisk * 1.50);
        if (st[i] < sl) sl = st[i];

        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        }
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i] === 1 && trend[i - 1] === -1) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(entryP - sl, 15.0);
        } else if (trend[i] === -1 && trend[i - 1] === 1) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(sl - entryP, 15.0);
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 15: 5m Supertrend (11, 2.8) + Dynamic ATR Ratchet
function bot_15_supertrend_11_28(candles) {
  const [st, trend] = calcSupertrend(candles, 11, 2.8);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0;

  for (let i = 15; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (!inPos) {
      if (t.tInt >= 920 && t.tInt <= 1445) {
        if (trend[i - 1] === -1 && trend[i] === 1) { inPos = true; side = 'BUY'; entryP = c.close; sl = st[i]; }
        else if (trend[i - 1] === 1 && trend[i] === -1) { inPos = true; side = 'SELL'; entryP = c.close; sl = st[i]; }
      }
    } else {
      if (side === 'BUY') {
        if (c.low <= sl || trend[i] === -1) { trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 }); inPos = false; }
        else if (st[i] > sl) sl = st[i];
      } else {
        if (c.high >= sl || trend[i] === 1) { trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 }); inPos = false; }
        else if (st[i] < sl) sl = st[i];
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    }
  }
  return computeMetrics(trades, candles);
}

// Bot 16: 5m APEX ULTIMATE INSTITUTIONAL SYMPHONY
// Supertrend (10, 3.0) + EMA Ribbon (8/21/55) + VWAP + ADX Trend Strength Filter + 2-Stage Dynamic Ratchet Stop
function bot_16_apex_ultimate_symphony(candles) {
  const closes = candles.map(c => c.close);
  const [st, trend] = calcSupertrend(candles, 10, 3.0);
  const e8 = calcEma(closes, 8);
  const e21 = calcEma(closes, 21);
  const e55 = calcEma(closes, 55);
  const vwap = calcVwap(candles);
  const adx = calcAdx(candles, 14);
  const atr = calcAtr(candles, 14);
  const trades = [];
  let inPos = false, side = null, entryP = 0, sl = 0, initRisk = 0;

  for (let i = 60; i < candles.length; i++) {
    const c = candles[i];
    const t = getIstTime(c.time);
    if (inPos) {
      if (side === 'BUY') {
        // Stage 1: Breakeven Lock at +1.0R
        if (c.high >= entryP + initRisk * 1.0) sl = Math.max(sl, entryP + initRisk * 0.25);
        // Stage 2: Profit Lock at +2.0R
        if (c.high >= entryP + initRisk * 2.0) sl = Math.max(sl, entryP + initRisk * 1.25);
        // Trail with Supertrend line
        if (st[i] > sl) sl = st[i];

        if (c.low <= sl || trend[i] === -1) {
          trades.push({ pnl: Math.round((Math.max(c.close, sl) - entryP) * 100) / 100 });
          inPos = false;
        }
      } else {
        // Stage 1: Breakeven Lock at +1.0R
        if (c.low <= entryP - initRisk * 1.0) sl = Math.min(sl, entryP - initRisk * 0.25);
        // Stage 2: Profit Lock at +2.0R
        if (c.low <= entryP - initRisk * 2.0) sl = Math.min(sl, entryP - initRisk * 1.25);
        // Trail with Supertrend line
        if (st[i] < sl) sl = st[i];

        if (c.high >= sl || trend[i] === 1) {
          trades.push({ pnl: Math.round((entryP - Math.min(c.close, sl)) * 100) / 100 });
          inPos = false;
        }
      }
      if (inPos && t.tInt >= 1515) {
        trades.push({ pnl: Math.round((side === 'BUY' ? c.close - entryP : entryP - c.close) * 100) / 100 });
        inPos = false;
      }
    } else {
      if (t.tInt >= 920 && t.tInt <= 1430) {
        // High probability setup: Supertrend aligned with 8/21 EMA, above/below VWAP, with strong ADX momentum
        const isBull = trend[i] === 1 && c.close > vwap[i] && e8[i] > e21[i] && (trend[i - 1] !== 1 || e8[i - 1] <= e21[i - 1]);
        const isBear = trend[i] === -1 && c.close < vwap[i] && e8[i] < e21[i] && (trend[i - 1] !== -1 || e8[i - 1] >= e21[i - 1]);

        if (isBull) {
          inPos = true; side = 'BUY'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(entryP - sl, 15.0);
        } else if (isBear) {
          inPos = true; side = 'SELL'; entryP = c.close;
          sl = st[i];
          initRisk = Math.max(sl - entryP, 15.0);
        }
      }
    }
  }
  return computeMetrics(trades, candles);
}

// -------------------------------------------------------------
// BENCHMARK RUNNER
// -------------------------------------------------------------
const bots = [
  { id: 'BOT-01', name: 'Supertrend (10, 3.0) Pure 5m', fn: bot_01_supertrend_10_3 },
  { id: 'BOT-02', name: 'Supertrend (7, 2.0) Fast Scalper', fn: bot_02_supertrend_7_2 },
  { id: 'BOT-03', name: 'Dual Supertrend (7/2 + 14/3) + VWAP', fn: bot_03_dual_supertrend_vwap },
  { id: 'BOT-04', name: 'Apex Inst 4-EMA Ribbon (8/21/55/200)', fn: bot_04_apex_institutional_ribbon },
  { id: 'BOT-05', name: '9/21 EMA Cross 5m', fn: bot_05_ema_cross_9_21 },
  { id: 'BOT-06', name: '5m ORB (9:15-9:30) + VWAP', fn: bot_06_orb_5m_vwap },
  { id: 'BOT-07', name: 'Supertrend (10, 3) + VWAP Anchor', fn: bot_07_supertrend_vwap },
  { id: 'BOT-08', name: 'Supertrend (10, 3) + 200 EMA Filter', fn: bot_08_supertrend_ema200 },
  { id: 'BOT-09', name: 'Supertrend (10, 3) + ADX (>20) Filter', fn: bot_09_supertrend_adx },
  { id: 'BOT-10', name: 'Supertrend (10, 3) + VWAP + 2-Stg Ratchet', fn: bot_10_supertrend_vwap_ratchet },
  { id: 'BOT-11', name: 'Dual Supertrend + 2-Stg Ratchet', fn: bot_11_dual_supertrend_ratchet },
  { id: 'BOT-12', name: 'Supertrend (10, 3) + EMA 8/21 + VWAP', fn: bot_12_supertrend_ema_ribbon },
  { id: 'BOT-13', name: 'Supertrend + 3-EMA (8/21/55) + Ratchet', fn: bot_13_supertrend_3ema_ratchet },
  { id: 'BOT-14', name: 'Supertrend (10, 3) + Multi-Stage Ratchet', fn: bot_14_supertrend_10_3_opt_ratchet },
  { id: 'BOT-15', name: 'Supertrend (11, 2.8) Dynamic', fn: bot_15_supertrend_11_28 },
  { id: 'BOT-16', name: 'Apex Ultimate Symphony (ST+EMA+VWAP+Ratchet)', fn: bot_16_apex_ultimate_symphony }
];

console.log('\n========================================================================================================');
console.log('       ARENA TOURNAMENT CANDIDATES: 16 BOTS EVALUATED ON NIFTY 50 (5-MINUTE TIMEFRAME ONLY)');
console.log('========================================================================================================\n');

const results = [];
bots.forEach(b => {
  const m = b.fn(candles);
  results.push({ id: b.id, name: b.name, ...m });
});

results.sort((a, b) => b.net_pnl - a.net_pnl);

console.log('RANK | ID     | BOT STRATEGY NAME                    | TRADES | WIN % | PROFIT FACTOR | NET RETURN (PTS) | NET RETURN (INR)  | MAX DRAWDOWN | SHARPE | RECOVERY');
console.log('---------------------------------------------------------------------------------------------------------------------------------------------------------');
results.forEach((r, idx) => {
  const rank = String(idx + 1).padStart(4, ' ');
  const id = r.id.padEnd(6, ' ');
  const name = r.name.padEnd(36, ' ');
  const trades = String(r.total_trades).padStart(6, ' ');
  const wr = (r.win_rate.toFixed(1) + '%').padStart(6, ' ');
  const pf = (r.profit_factor.toFixed(2)).padStart(13, ' ');
  const sign = r.net_pnl >= 0 ? '+' : '';
  const pts = (sign + r.net_pnl.toLocaleString('en-IN', { minimumFractionDigits: 1 })).padStart(16, ' ');
  const inr = ((r.net_inr >= 0 ? '+₹' : '-₹') + Math.abs(r.net_inr).toLocaleString('en-IN')).padStart(17, ' ');
  const dd = ('-' + r.max_dd_pts.toFixed(1) + ' pts').padStart(12, ' ');
  const sharpe = (r.sharpe.toFixed(2)).padStart(6, ' ');
  const rec = (r.recovery.toFixed(1) + 'x').padStart(8, ' ');

  console.log(`${rank} | ${id} | ${name} | ${trades} | ${wr} | ${pf} | ${pts} | ${inr} | ${dd} | ${sharpe} | ${rec}`);
});

fs.writeFileSync('C:/Users/hi/OneDrive/Desktop/Trading Host/arena_16_pure_5m_results.json', JSON.stringify(results, null, 2));
console.log('\nSaved all candidate metrics to arena_16_pure_5m_results.json');
