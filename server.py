#!/usr/bin/env python3

"""NSE Quant Studio - Professional Institutional Trading Terminal

Features:

- Dedicated Analytics Time Period Selector (ALL, 2026, 2025, 2024, Last 6M, Last 3M, Last 30D, Custom Dates) that filters ALL analytics data & syncs the chart.

- Fully Interactive Key Stats (clickable Total PnL, Max Drawdown, Profitable Trades, Profit Factor -> opens filtered Drawer).

- Fully Interactive Trades Analysis Studio (clickable Expectancy, Outliers PnL, Largest Profit/Loss, clickable Histogram Bins, clickable Donut chart, clickable Weekday & Session pattern cards).

- Restored Net Cumulative Performance tile (Image 1) with "Last 30 Active Market Sessions" subtitle.

- Floating 'Jump to Latest / Today' button on chart.

- 'Strategy View' button in bottom toolbar with strategy overlays + Strategy Telemetry HUD.

- Populated OHLC values on load and hover (never empty).

- Slide-Over Detail Drawer with complete trade ledger & 'Zoom Chart to Period' functionality.

- 100% Python Standard Library.

"""



import argparse

import csv

import datetime

import http.server

import json

import math

import os

import socketserver

import sys

import urllib.parse

import urllib.request

try:

    from live_market import (

        fetch_live_intraday,

        blend_historical_with_live,

        get_market_session_status,

        get_ist_now,

        PAPER_TRADER

    )

except ImportError:

    from dashboard.live_market import (

        fetch_live_intraday,

        blend_historical_with_live,

        get_market_session_status,

        get_ist_now,

        PAPER_TRADER

    )



try:

    sys.stdout.reconfigure(encoding="utf-8")

    sys.stderr.reconfigure(encoding="utf-8")

except Exception:

    pass



SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = SCRIPT_DIR

DATA_DIR = os.path.join(SCRIPT_DIR, "data") if os.path.isdir(os.path.join(SCRIPT_DIR, "data")) else os.path.join(os.path.dirname(SCRIPT_DIR), "data")

STATIC_DIR = os.path.join(SCRIPT_DIR, "static") if os.path.isdir(os.path.join(SCRIPT_DIR, "static")) else os.path.join(os.path.dirname(SCRIPT_DIR), "static")



DATASET_5M = os.path.join(DATA_DIR, "nifty50_2024_2026_5m.json")

DATASET_15M = os.path.join(DATA_DIR, "nifty50_2024_2026_15m.json")



try:

    from dashboard.pine_engine import (

        parse_pine_script,

        load_all_pine_strategies,

        save_custom_pine_strategy,

        delete_custom_pine_strategy,

        run_pine_strategy,

        DEFAULT_PINE_TEMPLATES

    )

except ImportError:

    from pine_engine import (

        parse_pine_script,

        load_all_pine_strategies,

        save_custom_pine_strategy,

        delete_custom_pine_strategy,

        run_pine_strategy,

        DEFAULT_PINE_TEMPLATES

    )





UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

YAHOO_HOST = "https://query2.finance.yahoo.com"



CACHE = {}



def load_local_dataset(filepath):

    if not os.path.exists(filepath):

        return []

    try:

        with open(filepath, "r", encoding="utf-8") as f:

            return json.load(f)

    except Exception as e:

        print(f"Error loading {filepath}: {e}", file=sys.stderr)

        return []



def get_market_data(symbol, timeframe, year_filter="all", start_ts=None, end_ts=None):

    cache_key = f"{symbol}_{timeframe}_{year_filter}_{start_ts}_{end_ts}"

    if cache_key in CACHE:

        return CACHE[cache_key]



    raw_candles = []

    if symbol in ("^NSEI", "NIFTY", "NIFTY50"):

        if timeframe == "5m":

            raw_candles = load_local_dataset(DATASET_5M)

        elif timeframe == "15m":

            raw_candles = load_local_dataset(DATASET_15M)

        elif timeframe == "1d":

            daily_url = f"{YAHOO_HOST}/v8/finance/chart/%5ENSEI?interval=1d&range=3y"

            try:

                req = urllib.request.Request(daily_url, headers={"User-Agent": UA})

                with urllib.request.urlopen(req, timeout=8) as resp:

                    d = json.loads(resp.read().decode("utf-8"))["chart"]["result"][0]

                    ts = d["timestamp"]

                    q = d["indicators"]["quote"][0]

                    for i in range(len(ts)):

                        dt = datetime.datetime.fromtimestamp(ts[i], datetime.timezone.utc)

                        if dt.year >= 2024:

                            if q["open"][i] is not None and q["close"][i] is not None:

                                raw_candles.append({

                                    "time": ts[i],

                                    "open": round(q["open"][i], 2),

                                    "high": round(q["high"][i], 2),

                                    "low": round(q["low"][i], 2),

                                    "close": round(q["close"][i], 2)

                                })

            except Exception:

                pass



        # Continuously blend real-time live intraday candles onto baseline dataset

        try:

            live_bars, _ = fetch_live_intraday(symbol, timeframe, range_str="5d")

            if live_bars:

                raw_candles = blend_historical_with_live(raw_candles, live_bars)

        except Exception as e:

            print(f"[LIVE_BLEND_WARN] {e}", file=sys.stderr)

    else:

        ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"

        url = f"{YAHOO_HOST}/v8/finance/chart/{urllib.parse.quote(ticker)}?interval={timeframe}&range=60d"

        try:

            req = urllib.request.Request(url, headers={"User-Agent": UA})

            with urllib.request.urlopen(req, timeout=8) as resp:

                data = json.loads(resp.read().decode("utf-8"))

                chart = data.get("chart", {}).get("result", [None])[0]

                if chart:

                    ts = chart.get("timestamp", [])

                    q = chart.get("indicators", {}).get("quote", [{}])[0]

                    for i in range(len(ts)):

                        if (q.get("open") and i < len(q["open"]) and q["open"][i] is not None and

                            q.get("close") and i < len(q["close"]) and q["close"][i] is not None):

                            raw_candles.append({

                                "time": ts[i],

                                "open": round(q["open"][i], 2),

                                "high": round(q["high"][i], 2),

                                "low": round(q["low"][i], 2),

                                "close": round(q["close"][i], 2)

                            })

        except Exception:

            pass



    if not raw_candles:

        return []



    # Time period filter

    if start_ts is not None and end_ts is not None:

        filtered = [c for c in raw_candles if start_ts <= c["time"] <= end_ts]

    elif year_filter == "2024":

        filtered = [c for c in raw_candles if datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc).year == 2024]

    elif year_filter == "2025":

        filtered = [c for c in raw_candles if datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc).year == 2025]

    elif year_filter == "2026":

        filtered = [c for c in raw_candles if datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc).year == 2026]

    elif year_filter == "6m":

        cutoff = raw_candles[-1]["time"] - (180 * 86400)

        filtered = [c for c in raw_candles if c["time"] >= cutoff]

    elif year_filter == "3m":

        cutoff = raw_candles[-1]["time"] - (90 * 86400)

        filtered = [c for c in raw_candles if c["time"] >= cutoff]

    elif year_filter == "30d":

        cutoff = raw_candles[-1]["time"] - (30 * 86400)

        filtered = [c for c in raw_candles if c["time"] >= cutoff]

    elif year_filter == "recent60":

        filtered = raw_candles[-4500:] if len(raw_candles) > 4500 else raw_candles

    else:

        filtered = raw_candles



    # Only cache non-live symbols permanently; live symbols update dynamically

    if symbol not in ("^NSEI", "NIFTY", "NIFTY50"):

        CACHE[cache_key] = filtered

    return filtered



def calc_ema(values, period):

    if len(values) < period:

        return values[:]

    ema = []

    multiplier = 2.0 / (period + 1)

    sma = sum(values[:period]) / period

    ema.extend([sma] * period)

    current = sma

    for val in values[period:]:

        current = (val - current) * multiplier + current

        ema.append(round(current, 2))

    return ema



def calc_rsi(values, period=14):

    if len(values) <= period:

        return [50.0] * len(values)

    gains = []

    losses = []

    for i in range(1, len(values)):

        diff = values[i] - values[i - 1]

        gains.append(max(0.0, diff))

        losses.append(max(0.0, -diff))



    avg_gain = sum(gains[:period]) / period

    avg_loss = sum(losses[:period]) / period



    rsi_vals = [50.0] * period

    for i in range(period, len(gains)):

        avg_gain = (avg_gain * (period - 1) + gains[i]) / period

        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:

            rsi_vals.append(100.0)

        else:

            rs = avg_gain / avg_loss

            rsi_vals.append(round(100.0 - (100.0 / (1.0 + rs)), 2))

    rsi_vals.append(rsi_vals[-1])

    return rsi_vals





def calc_atr_internal(candles, period=14):

    if not candles:

        return []

    tr = [candles[0]["high"] - candles[0]["low"]]

    for i in range(1, len(candles)):

        c = candles[i]

        prev_c = candles[i-1]

        t = max(c["high"] - c["low"], abs(c["high"] - prev_c["close"]), abs(c["low"] - prev_c["close"]))

        tr.append(t)

    atr = []

    cur = sum(tr[:period]) / period if len(tr) >= period else tr[0]

    for i in range(len(tr)):

        if i < period:

            atr.append(cur)

        else:

            cur = ((cur * (period - 1)) + tr[i]) / period

            atr.append(cur)

    return atr



def calc_supertrend_internal(candles, period=10, multiplier=3.0):

    if not candles:

        return [], []

    atr = calc_atr_internal(candles, period)

    st = [candles[0]["close"]] * len(candles)

    trend = [1] * len(candles)

    upper_band = [0.0] * len(candles)

    lower_band = [0.0] * len(candles)

    for i in range(len(candles)):

        hl2 = (candles[i]["high"] + candles[i]["low"]) / 2.0

        basic_upper = hl2 + (multiplier * atr[i])

        basic_lower = hl2 - (multiplier * atr[i])

        if i == 0:

            upper_band[i] = basic_upper

            lower_band[i] = basic_lower

            continue

        if basic_upper < upper_band[i-1] or candles[i-1]["close"] > upper_band[i-1]:

            upper_band[i] = basic_upper

        else:

            upper_band[i] = upper_band[i-1]

        if basic_lower > lower_band[i-1] or candles[i-1]["close"] < lower_band[i-1]:

            lower_band[i] = basic_lower

        else:

            lower_band[i] = lower_band[i-1]

        if trend[i-1] == 1:

            if candles[i]["close"] < lower_band[i]:

                trend[i] = -1

                st[i] = upper_band[i]

            else:

                trend[i] = 1

                st[i] = lower_band[i]

        else:

            if candles[i]["close"] > upper_band[i]:

                trend[i] = 1

                st[i] = lower_band[i]

            else:

                trend[i] = -1

                st[i] = upper_band[i]

    return st, trend



def calc_intraday_vwap_internal(candles):

    if not candles:

        return []

    vwap = [0.0] * len(candles)

    by_day = {}

    for idx, c in enumerate(candles):

        ist_dt = datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

        d_key = ist_dt.strftime("%Y-%m-%d")

        if d_key not in by_day:

            by_day[d_key] = []

        by_day[d_key].append((idx, c))

    for d_key, session in by_day.items():

        c_sum = 0.0

        c_cnt = 0

        for idx, c in session:

            c_cnt += 1

            c_sum += (c["high"] + c["low"] + c["close"]) / 3.0

            vwap[idx] = c_sum / c_cnt

    return vwap



def run_strategy(candles, strategy_type="orb", params=None, symbol="^NSEI"):

    if params is None:

        params = {}

    if not candles:

        return {

            "trades": [], "markers": [], "equity_curve": [], "monthly_matrix": {},

            "strip_30_days": [], "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,

            "profit_factor": 0.0, "net_pnl_pts": 0.0, "net_inr": 0.0, "net_pct": 0.0, "avg_trade_pts": 0.0,

            "avg_win_pts": 0.0, "avg_loss_pts": 0.0, "largest_win_pts": 0.0, "largest_loss_pts": 0.0,

            "max_w_streak": 0, "max_l_streak": 0, "max_drawdown_pts": 0.0, "max_dd_pct": 0.0, "max_dd_inr": 0.0,

            "recovery_factor": 0.0, "sharpe_ratio": 0.0, "period_label": "No Data", "candle_count": 0,

            "returns_distribution": [], "trades_distribution": {}, "expectancy": {},

            "outliers": {"pts": 0.0, "inr": 0.0, "pct": 0.0, "trades": []}, "benchmark_curve": [],

            "time_patterns": {}, "streaks": {}, "strategy_meta": {}

        }



    trades = []

    closes = [c["close"] for c in candles]

    highs = [c["high"] for c in candles]

    lows = [c["low"] for c in candles]

    n = len(candles)

    initial_capital_pts = closes[0] if closes else 22000.0



    # 0. Pine Script Strategies & Dynamic Compilation

    pine_strategies = load_all_pine_strategies()

    strategy_meta_override = None

    parsed_inputs_override = None



    if strategy_type in pine_strategies or strategy_type.startswith("pine_") or strategy_type == "pine_custom":

        pine_entry = pine_strategies.get(strategy_type)

        pine_code = params.get("custom_pine_code") if strategy_type == "pine_custom" else (pine_entry["code"] if pine_entry else "")

        if pine_code:

            pine_res = run_pine_strategy(candles, pine_code, params, symbol=symbol)

            trades = pine_res["trades"]

            strategy_meta_override = pine_res.get("strategy_meta")

            parsed_inputs_override = pine_res.get("parsed_inputs")

            indicators_override = pine_res.get("indicators", {})



    # 1. 15-Minute ORB Strategy

    elif strategy_type == "orb":

        target_r = float(params.get("target_r", 2.0))

        stop_type = params.get("stop_type", "or_mid")

        

        by_day = {}

        for idx, c in enumerate(candles):

            ist_dt = datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

            d_key = ist_dt.strftime("%Y-%m-%d")

            if d_key not in by_day:

                by_day[d_key] = []

            by_day[d_key].append((idx, c, ist_dt))



        for d_key, session in by_day.items():

            if len(session) < 6:

                continue

            or_bars = session[:3]

            or_high = max(x[1]["high"] for x in or_bars)

            or_low = min(x[1]["low"] for x in or_bars)

            or_mid = (or_high + or_low) / 2.0



            stop_price = or_mid if stop_type == "or_mid" else or_low

            entry_price = None

            entry_candle = None

            entry_idx = None

            target_price = None



            for idx, c, dt in session[3:]:

                if entry_price is None:

                    if dt.hour * 100 + dt.minute <= 1400 and c["close"] > or_high:

                        entry_price = c["close"]

                        entry_candle = c

                        entry_idx = idx

                        risk = entry_price - stop_price

                        if risk <= 0:

                            break

                        target_price = entry_price + (risk * target_r)

                else:

                    bars_held = idx - entry_idx

                    if c["low"] <= stop_price:

                        trades.append({

                            "entry_time": entry_candle["time"],

                            "entry_price": entry_price,

                            "exit_time": c["time"],

                            "exit_price": stop_price,

                            "pnl": round(stop_price - entry_price, 2),

                            "pnl_pct": round(((stop_price - entry_price) / entry_price) * 100.0, 2),

                            "reason": "STOP_LOSS",

                            "side": "BUY",

                            "bars_held": bars_held

                        })

                        break

                    elif c["high"] >= target_price:

                        trades.append({

                            "entry_time": entry_candle["time"],

                            "entry_price": entry_price,

                            "exit_time": c["time"],

                            "exit_price": target_price,

                            "pnl": round(target_price - entry_price, 2),

                            "pnl_pct": round(((target_price - entry_price) / entry_price) * 100.0, 2),

                            "reason": "TARGET",

                            "side": "BUY",

                            "bars_held": bars_held

                        })

                        break

                    elif dt.hour * 100 + dt.minute >= 1515:

                        trades.append({

                            "entry_time": entry_candle["time"],

                            "entry_price": entry_price,

                            "exit_time": c["time"],

                            "exit_price": c["close"],

                            "pnl": round(c["close"] - entry_price, 2),

                            "pnl_pct": round(((c["close"] - entry_price) / entry_price) * 100.0, 2),

                            "reason": "MIS_SQUAREOFF",

                            "side": "BUY",

                            "bars_held": bars_held

                        })

                        break



    # 2. EMA Trend Crossover

    elif strategy_type == "ema_cross":

        fast_p = int(params.get("fast_ema", 9))

        slow_p = int(params.get("slow_ema", 21))

        fast_ema = calc_ema(closes, fast_p)

        slow_ema = calc_ema(closes, slow_p)



        in_pos = False

        entry_c = None

        entry_idx = 0



        for i in range(slow_p, n):

            pf = fast_ema[i-1]

            ps = slow_ema[i-1]

            cf = fast_ema[i]

            cs = slow_ema[i]

            c = candles[i]



            if not in_pos and pf <= ps and cf > cs:

                in_pos = True

                entry_c = c

                entry_idx = i

            elif in_pos and pf >= ps and cf < cs:

                pnl = round(c["close"] - entry_c["close"], 2)

                trades.append({

                    "entry_time": entry_c["time"],

                    "entry_price": entry_c["close"],

                    "exit_time": c["time"],

                    "exit_price": c["close"],

                    "pnl": pnl,

                    "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                    "reason": "BEARISH_CROSS",

                    "side": "BUY",

                    "bars_held": i - entry_idx

                })

                in_pos = False



    # 3. Supertrend

    elif strategy_type == "supertrend":

        period = int(params.get("atr_period", 10))

        mult = float(params.get("multiplier", 3.0))



        tr = [highs[0] - lows[0]]

        for i in range(1, n):

            tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))

        

        atr = [sum(tr[:period]) / period]

        for i in range(period, n):

            atr.append((atr[-1] * (period - 1) + tr[i]) / period)

        atr = [atr[0]] * (period - 1) + atr



        upper_band = [0.0] * n

        lower_band = [0.0] * n

        st = [0.0] * n

        trend = [1] * n



        for i in range(period, n):

            hl2 = (highs[i] + lows[i]) / 2.0

            basic_upper = hl2 + (mult * atr[i])

            basic_lower = hl2 - (mult * atr[i])



            if basic_lower > lower_band[i-1] or closes[i-1] < lower_band[i-1]:

                lower_band[i] = basic_lower

            else:

                lower_band[i] = lower_band[i-1]



            if basic_upper < upper_band[i-1] or closes[i-1] > upper_band[i-1]:

                upper_band[i] = basic_upper

            else:

                upper_band[i] = upper_band[i-1]



            prev_st = st[i-1]

            if prev_st == upper_band[i-1]:

                trend[i] = 1 if closes[i] > upper_band[i] else -1

            else:

                trend[i] = -1 if closes[i] < lower_band[i] else 1



            st[i] = lower_band[i] if trend[i] == 1 else upper_band[i]



        in_pos = False

        entry_c = None

        entry_idx = 0



        for i in range(period + 1, n):

            if not in_pos and trend[i-1] == -1 and trend[i] == 1:

                in_pos = True

                entry_c = candles[i]

                entry_idx = i

            elif in_pos and trend[i-1] == 1 and trend[i] == -1:

                pnl = round(candles[i]["close"] - entry_c["close"], 2)

                trades.append({

                    "entry_time": entry_c["time"],

                    "entry_price": entry_c["close"],

                    "exit_time": candles[i]["time"],

                    "exit_price": candles[i]["close"],

                    "pnl": pnl,

                    "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                    "reason": "SUPERTREND_FLIP",

                    "side": "BUY",

                    "bars_held": i - entry_idx

                })

                in_pos = False



    # 4. RSI

    elif strategy_type == "rsi":

        rsi_p = int(params.get("rsi_period", 14))

        buy_thresh = float(params.get("rsi_buy", 30))

        sell_thresh = float(params.get("rsi_sell", 70))

        rsi = calc_rsi(closes, rsi_p)



        in_pos = False

        entry_c = None

        entry_idx = 0

        for i in range(rsi_p + 1, len(rsi)):

            if not in_pos and rsi[i-1] < buy_thresh and rsi[i] >= buy_thresh:

                in_pos = True

                entry_c = candles[i]

                entry_idx = i

            elif in_pos and rsi[i] >= sell_thresh:

                pnl = round(candles[i]["close"] - entry_c["close"], 2)

                trades.append({

                    "entry_time": entry_c["time"],

                    "entry_price": entry_c["close"],

                    "exit_time": candles[i]["time"],

                    "exit_price": candles[i]["close"],

                    "pnl": pnl,

                    "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                    "reason": "RSI_OVERBOUGHT",

                    "side": "BUY",

                    "bars_held": i - entry_idx

                })

                in_pos = False



    # 5. Bollinger Bands

    elif strategy_type == "bollinger":

        bb_p = int(params.get("bb_period", 20))

        bb_m = float(params.get("bb_mult", 2.0))

        sma = []

        for i in range(n):

            if i < bb_p - 1:

                sma.append(closes[i])

            else:

                sma.append(sum(closes[i - bb_p + 1:i + 1]) / bb_p)



        in_pos = False

        entry_c = None

        entry_idx = 0

        for i in range(bb_p, n):

            std = math.sqrt(sum((c - sma[i]) ** 2 for c in closes[i - bb_p + 1:i + 1]) / bb_p)

            lower_b = sma[i] - (bb_m * std)

            c = candles[i]



            if not in_pos and c["close"] <= lower_b:

                in_pos = True

                entry_c = c

                entry_idx = i

            elif in_pos and c["close"] >= sma[i]:

                pnl = round(c["close"] - entry_c["close"], 2)

                trades.append({

                    "entry_time": entry_c["time"],

                    "entry_price": entry_c["close"],

                    "exit_time": c["time"],

                    "exit_price": c["close"],

                    "pnl": pnl,

                    "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                    "reason": "BB_MID_EXIT",

                    "side": "BUY",

                    "bars_held": i - entry_idx

                })

                in_pos = False



    # 6. MACD

    elif strategy_type == "macd":

        ema12 = calc_ema(closes, 12)

        ema26 = calc_ema(closes, 26)

        macd_line = [ema12[i] - ema26[i] for i in range(n)]

        signal_line = calc_ema(macd_line, 9)



        in_pos = False

        entry_c = None

        entry_idx = 0

        for i in range(35, n):

            prev_m = macd_line[i-1]

            prev_s = signal_line[i-1]

            curr_m = macd_line[i]

            curr_s = signal_line[i]

            c = candles[i]



            if not in_pos and prev_m <= prev_s and curr_m > curr_s and curr_m < 0:

                in_pos = True

                entry_c = c

                entry_idx = i

            elif in_pos and prev_m >= prev_s and curr_m < curr_s:

                pnl = round(c["close"] - entry_c["close"], 2)

                trades.append({

                    "entry_time": entry_c["time"],

                    "entry_price": entry_c["close"],

                    "exit_time": c["time"],

                    "exit_price": c["close"],

                    "pnl": pnl,

                    "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                    "reason": "MACD_CROSS_DOWN",

                    "side": "BUY",

                    "bars_held": i - entry_idx

                })

                in_pos = False



    # 7. Custom Multi-Rule Builder

    elif strategy_type == "custom":

        fast_p = int(params.get("custom_fast", 9))

        slow_p = int(params.get("custom_slow", 21))

        target_pct = float(params.get("custom_target_pct", 1.5))

        stop_pct = float(params.get("custom_stop_pct", 0.75))



        fast_ema = calc_ema(closes, fast_p)

        slow_ema = calc_ema(closes, slow_p)



        in_pos = False

        entry_c = None

        entry_idx = 0

        target_price = 0.0

        stop_price = 0.0



        for i in range(slow_p, n):

            c = candles[i]

            if not in_pos:

                if fast_ema[i-1] <= slow_ema[i-1] and fast_ema[i] > slow_ema[i]:

                    in_pos = True

                    entry_c = c

                    entry_idx = i

                    target_price = round(c["close"] * (1.0 + target_pct / 100.0), 2)

                    stop_price = round(c["close"] * (1.0 - stop_pct / 100.0), 2)

            else:

                bars_held = i - entry_idx

                if c["high"] >= target_price:

                    pnl = round(target_price - entry_c["close"], 2)

                    trades.append({

                        "entry_time": entry_c["time"],

                        "entry_price": entry_c["close"],

                        "exit_time": c["time"],

                        "exit_price": round(target_price, 2),

                        "pnl": pnl,

                        "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                        "reason": "CUSTOM_TARGET",

                        "side": "BUY",

                        "bars_held": bars_held

                    })

                    in_pos = False

                elif c["low"] <= stop_price:

                    pnl = round(stop_price - entry_c["close"], 2)

                    trades.append({

                        "entry_time": entry_c["time"],

                        "entry_price": entry_c["close"],

                        "exit_time": c["time"],

                        "exit_price": round(stop_price, 2),

                        "pnl": pnl,

                        "pnl_pct": round((pnl / entry_c["close"]) * 100.0, 2),

                        "reason": "CUSTOM_STOP",

                        "side": "BUY",

                        "bars_held": bars_held

                    })

                    in_pos = False





    # 8. Strategy 1: Dual Supertrend + VWAP Pulse (Institutional Precision & Low Drawdown)

    elif strategy_type == "dual_supertrend_vwap":

        target_r = float(params.get("dual_st_target_r", 1.8))

        sl_atr_mult = float(params.get("dual_st_sl_atr", 1.6))

        

        fast_st, fast_trend = calc_supertrend_internal(candles, 7, 2.0)

        slow_st, slow_trend = calc_supertrend_internal(candles, 10, 3.0)

        e50 = calc_ema(closes, 50)

        atr = calc_atr_internal(candles, 14)

        vwap = calc_intraday_vwap_internal(candles)

        

        by_day = {}

        for idx, c in enumerate(candles):

            ist_dt = datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

            d_key = ist_dt.strftime("%Y-%m-%d")

            if d_key not in by_day:

                by_day[d_key] = []

            by_day[d_key].append((idx, c, ist_dt))

            

        for d_key, session in by_day.items():

            if len(session) < 6:

                continue

            in_trade = False

            pos_side = None

            entry_p = 0.0

            entry_c = None

            entry_idx = 0

            sl = 0.0

            tp = 0.0

            

            for idx, c, dt in session[2:]:

                t_int = dt.hour * 100 + dt.minute

                

                # Strict intraday MIS square-off at 15:15

                if in_trade and t_int >= 1515:

                    pnl = round((c["close"] - entry_p) if pos_side == "BUY" else (entry_p - c["close"]), 2)

                    trades.append({

                        "entry_time": entry_c["time"], "entry_price": entry_p,

                        "exit_time": c["time"], "exit_price": c["close"],

                        "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                        "reason": "MIS_SQUAREOFF", "side": pos_side, "bars_held": idx - entry_idx

                    })

                    in_trade = False

                    break

                    

                if not in_trade:

                    if 930 <= t_int <= 1415 and idx > 0:

                        cur_atr = max(atr[idx], 15.0)

                        # BUY: Macro ST Bullish + Fast ST pullback flip + Above VWAP + Above EMA 50

                        if slow_trend[idx] == 1 and fast_trend[idx] == 1 and fast_trend[idx-1] == -1 and c["close"] > vwap[idx] and c["close"] > e50[idx]:

                            in_trade = True

                            pos_side = "BUY"

                            entry_p = c["close"]

                            entry_c = c

                            entry_idx = idx

                            sl_dist = cur_atr * sl_atr_mult

                            sl = round(entry_p - sl_dist, 2)

                            tp = round(entry_p + (sl_dist * target_r), 2)

                            continue

                        # SELL: Macro ST Bearish + Fast ST rally flip + Below VWAP + Below EMA 50

                        elif slow_trend[idx] == -1 and fast_trend[idx] == -1 and fast_trend[idx-1] == 1 and c["close"] < vwap[idx] and c["close"] < e50[idx]:

                            in_trade = True

                            pos_side = "SELL"

                            entry_p = c["close"]

                            entry_c = c

                            entry_idx = idx

                            sl_dist = cur_atr * sl_atr_mult

                            sl = round(entry_p + sl_dist, 2)

                            tp = round(entry_p - (sl_dist * target_r), 2)

                            continue

                else:

                    bars_held = idx - entry_idx

                    if pos_side == "BUY":

                        if c["low"] <= sl:

                            pnl = round(sl - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["high"] >= tp:

                            pnl = round(tp - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                    elif pos_side == "SELL":

                        if c["high"] >= sl:

                            pnl = round(entry_p - sl, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["low"] <= tp:

                            pnl = round(entry_p - tp, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False



    # 9. Strategy 2: Triple Momentum Fusion (Supertrend + 3-EMA Ribbon + Donchian)

    elif strategy_type == "triple_momentum_fusion":

        target_r = float(params.get("tmf_target_r", 1.0))

        sl_atr_mult = float(params.get("tmf_sl_atr", 1.8))

        

        slow_st, slow_trend = calc_supertrend_internal(candles, 10, 3.0)

        e9 = calc_ema(closes, 9)

        e21 = calc_ema(closes, 21)

        e50 = calc_ema(closes, 50)

        atr = calc_atr_internal(candles, 14)

        vwap = calc_intraday_vwap_internal(candles)

        

        by_day = {}

        for idx, c in enumerate(candles):

            ist_dt = datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

            d_key = ist_dt.strftime("%Y-%m-%d")

            if d_key not in by_day:

                by_day[d_key] = []

            by_day[d_key].append((idx, c, ist_dt))

            

        for d_key, session in by_day.items():

            if len(session) < 15:

                continue

            in_trade = False

            pos_side = None

            entry_p = 0.0

            entry_c = None

            entry_idx = 0

            sl = 0.0

            tp = 0.0

            

            for s_idx, (idx, c, dt) in enumerate(session):

                t_int = dt.hour * 100 + dt.minute

                

                # Strict MIS square-off at 15:15

                if in_trade and t_int >= 1515:

                    pnl = round((c["close"] - entry_p) if pos_side == "BUY" else (entry_p - c["close"]), 2)

                    trades.append({

                        "entry_time": entry_c["time"], "entry_price": entry_p,

                        "exit_time": c["time"], "exit_price": c["close"],

                        "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                        "reason": "MIS_SQUAREOFF", "side": pos_side, "bars_held": idx - entry_idx

                    })

                    in_trade = False

                    break

                    

                if not in_trade:

                    if 935 <= t_int <= 1400 and s_idx >= 5:

                        lookback_bars = [x[1] for x in session[max(0, s_idx - 15):s_idx]]

                        ch_high = max(x["high"] for x in lookback_bars)

                        ch_low = min(x["low"] for x in lookback_bars)

                        cur_atr = max(atr[idx], 15.0)

                        

                        # BUY: Donchian 15-bar breakout + ST Bullish + EMA 9>21>50 + VWAP

                        if c["close"] > ch_high and slow_trend[idx] == 1 and e9[idx] > e21[idx] and c["close"] > e50[idx] and c["close"] > vwap[idx]:

                            in_trade = True

                            pos_side = "BUY"

                            entry_p = c["close"]

                            entry_c = c

                            entry_idx = idx

                            sl_dist = cur_atr * sl_atr_mult

                            sl = round(entry_p - sl_dist, 2)

                            tp = round(entry_p + (sl_dist * target_r), 2)

                            continue

                            

                        # SELL: Donchian 15-bar breakdown + ST Bearish + EMA 9<21<50 + VWAP

                        elif c["close"] < ch_low and slow_trend[idx] == -1 and e9[idx] < e21[idx] and c["close"] < e50[idx] and c["close"] < vwap[idx]:

                            in_trade = True

                            pos_side = "SELL"

                            entry_p = c["close"]

                            entry_c = c

                            entry_idx = idx

                            sl_dist = cur_atr * sl_atr_mult

                            sl = round(entry_p + sl_dist, 2)

                            tp = round(entry_p - (sl_dist * target_r), 2)

                            continue

                else:

                    bars_held = idx - entry_idx

                    if pos_side == "BUY":

                        if c["low"] <= sl:

                            pnl = round(sl - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["high"] >= tp:

                            pnl = round(tp - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                    elif pos_side == "SELL":

                        if c["high"] >= sl:

                            pnl = round(entry_p - sl, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["low"] <= tp:

                            pnl = round(entry_p - tp, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False



    # 10. Strategy 3: Adaptive Dual ORB + Supertrend + VWAP

    elif strategy_type == "adaptive_dual_orb":

        target_r = float(params.get("dual_orb_target_r", 1.0))

        sl_atr_mult = float(params.get("dual_orb_sl_atr", 1.5))

        

        slow_st, slow_trend = calc_supertrend_internal(candles, 10, 3.0)

        atr = calc_atr_internal(candles, 14)

        vwap = calc_intraday_vwap_internal(candles)

        

        by_day = {}

        for idx, c in enumerate(candles):

            ist_dt = datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

            d_key = ist_dt.strftime("%Y-%m-%d")

            if d_key not in by_day:

                by_day[d_key] = []

            by_day[d_key].append((idx, c, ist_dt))

            

        for d_key, session in by_day.items():

            if len(session) < 6:

                continue

            or_bars = session[:3]

            or_high = max(x[1]["high"] for x in or_bars)

            or_low = min(x[1]["low"] for x in or_bars)

            

            in_trade = False

            pos_side = None

            entry_p = 0.0

            entry_c = None

            entry_idx = 0

            sl = 0.0

            tp = 0.0

            

            for idx, c, dt in session[3:]:

                t_int = dt.hour * 100 + dt.minute

                

                # Strict MIS square-off at 15:15

                if in_trade and t_int >= 1515:

                    pnl = round((c["close"] - entry_p) if pos_side == "BUY" else (entry_p - c["close"]), 2)

                    trades.append({

                        "entry_time": entry_c["time"], "entry_price": entry_p,

                        "exit_time": c["time"], "exit_price": c["close"],

                        "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                        "reason": "MIS_SQUAREOFF", "side": pos_side, "bars_held": idx - entry_idx

                    })

                    in_trade = False

                    break

                    

                if not in_trade:

                    if 930 <= t_int <= 1345:

                        cur_atr = max(atr[idx], 15.0)

                        

                        # BUY: Breakout above 15-min High + Above VWAP + Bullish Supertrend

                        if c["close"] > or_high and c["close"] > vwap[idx] and slow_trend[idx] == 1:

                            in_trade = True

                            pos_side = "BUY"

                            entry_p = c["close"]

                            entry_c = c

                            entry_idx = idx

                            sl_dist = cur_atr * sl_atr_mult

                            sl = round(entry_p - sl_dist, 2)

                            tp = round(entry_p + (sl_dist * target_r), 2)

                            continue

                            

                        # SELL: Breakdown below 15-min Low + Below VWAP + Bearish Supertrend

                        elif c["close"] < or_low and c["close"] < vwap[idx] and slow_trend[idx] == -1:

                            in_trade = True

                            pos_side = "SELL"

                            entry_p = c["close"]

                            entry_c = c

                            entry_idx = idx

                            sl_dist = cur_atr * sl_atr_mult

                            sl = round(entry_p + sl_dist, 2)

                            tp = round(entry_p - (sl_dist * target_r), 2)

                            continue

                else:

                    bars_held = idx - entry_idx

                    if pos_side == "BUY":

                        if c["low"] <= sl:

                            pnl = round(sl - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["high"] >= tp:

                            pnl = round(tp - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                    elif pos_side == "SELL":

                        if c["high"] >= sl:

                            pnl = round(entry_p - sl, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["low"] <= tp:

                            pnl = round(entry_p - tp, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False





    # 11. Strategy: Inside Candle + VWAP + 3-EMA Ribbon + Supertrend (User Requested Blend)

    elif strategy_type == "inside_candle_vwap_ema":

        target_r = float(params.get("ic_target_r", 1.0))

        sl_atr_mult = float(params.get("ic_sl_atr", 1.1))

        use_st = str(params.get("ic_use_st", "true")).lower() == "true"

        min_mother_atr = float(params.get("ic_min_mom", 0.6))

        

        slow_st, slow_trend = calc_supertrend_internal(candles, 10, 3.0)

        e9 = calc_ema(closes, 9)

        e21 = calc_ema(closes, 21)

        e50 = calc_ema(closes, 50)

        atr = calc_atr_internal(candles, 14)

        vwap = calc_intraday_vwap_internal(candles)

        

        by_day = {}

        for idx, c in enumerate(candles):

            ist_dt = datetime.datetime.fromtimestamp(c["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

            d_key = ist_dt.strftime("%Y-%m-%d")

            if d_key not in by_day:

                by_day[d_key] = []

            by_day[d_key].append((idx, c, ist_dt))

            

        for d_key, session in by_day.items():

            if len(session) < 6:

                continue

            in_trade = False

            pos_side = None

            entry_p = 0.0

            entry_c = None

            entry_idx = 0

            sl = 0.0

            tp = 0.0

            

            for s_idx in range(2, len(session)):

                idx, c, dt = session[s_idx]

                t_int = dt.hour * 100 + dt.minute

                

                # Strict MIS square-off at 15:15 IST

                if in_trade and t_int >= 1515:

                    pnl = round((c["close"] - entry_p) if pos_side == "BUY" else (entry_p - c["close"]), 2)

                    trades.append({

                        "entry_time": entry_c["time"], "entry_price": entry_p,

                        "exit_time": c["time"], "exit_price": c["close"],

                        "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                        "reason": "MIS_SQUAREOFF", "side": pos_side, "bars_held": idx - entry_idx

                    })

                    in_trade = False

                    break

                    

                if not in_trade:

                    if 925 <= t_int <= 1430:

                        prev_c = session[s_idx - 1][1]

                        mother_c = session[s_idx - 2][1]

                        cur_atr = max(atr[idx], 15.0)

                        mother_range = mother_c["high"] - mother_c["low"]

                        

                        is_inside = (prev_c["high"] <= mother_c["high"]) and (prev_c["low"] >= mother_c["low"])

                        expansion_mother = (mother_range >= cur_atr * min_mother_atr)

                        

                        if is_inside and expansion_mother:

                            cur_vwap = vwap[idx]

                            st_ok_buy = (slow_trend[idx] == 1) if use_st else True

                            st_ok_sell = (slow_trend[idx] == -1) if use_st else True

                            

                            # BUY: 9 EMA > 21 EMA + Close > VWAP + Supertrend Bullish + Breakout Mother High

                            if e9[idx] > e21[idx] and c["close"] > cur_vwap and st_ok_buy and c["close"] > mother_c["high"]:

                                in_trade = True

                                pos_side = "BUY"

                                entry_p = c["close"]

                                entry_c = c

                                entry_idx = idx

                                sl_dist = max(cur_atr * sl_atr_mult, 12.0)

                                sl = round(entry_p - sl_dist, 2)

                                tp = round(entry_p + (sl_dist * target_r), 2)

                                continue

                                

                            # SELL: 9 EMA < 21 EMA + Close < VWAP + Supertrend Bearish + Breakdown Mother Low

                            elif e9[idx] < e21[idx] and c["close"] < cur_vwap and st_ok_sell and c["close"] < mother_c["low"]:

                                in_trade = True

                                pos_side = "SELL"

                                entry_p = c["close"]

                                entry_c = c

                                entry_idx = idx

                                sl_dist = max(cur_atr * sl_atr_mult, 12.0)

                                sl = round(entry_p + sl_dist, 2)

                                tp = round(entry_p - (sl_dist * target_r), 2)

                                continue

                else:

                    bars_held = idx - entry_idx

                    if pos_side == "BUY":

                        if c["low"] <= sl:

                            pnl = round(sl - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["high"] >= tp:

                            pnl = round(tp - entry_p, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "BUY", "bars_held": bars_held

                            })

                            in_trade = False

                    elif pos_side == "SELL":

                        if c["high"] >= sl:

                            pnl = round(entry_p - sl, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": sl,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "STOP_LOSS", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False

                        elif c["low"] <= tp:

                            pnl = round(entry_p - tp, 2)

                            trades.append({

                                "entry_time": entry_c["time"], "entry_price": entry_p,

                                "exit_time": c["time"], "exit_price": tp,

                                "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),

                                "reason": "TARGET", "side": "SELL", "bars_held": bars_held

                            })

                            in_trade = False

    # Enrich Trades

    inr_multiplier = 75.0 if symbol in ("^NSEI", "NIFTY") else 1.0

    for idx, t in enumerate(trades):

        t["id"] = idx + 1

        t["inr_pnl"] = round(t["pnl"] * inr_multiplier, 2)

        

        en_dt = datetime.datetime.fromtimestamp(t["entry_time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

        ex_dt = datetime.datetime.fromtimestamp(t["exit_time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

        t["entry_dt_ist"] = en_dt.strftime("%Y-%m-%d %H:%M")

        t["exit_dt_ist"] = ex_dt.strftime("%Y-%m-%d %H:%M")

        t["day_str"] = en_dt.strftime("%Y-%m-%d")

        t["month_str"] = en_dt.strftime("%Y-%m")

        t["week_str"] = f"{en_dt.year}-W{en_dt.isocalendar()[1]:02d}"

        t["weekday_num"] = en_dt.weekday() # 0 = Mon, 4 = Fri

        t["hour_num"] = en_dt.hour

        

        dur_mins = max(5, int((t["exit_time"] - t["entry_time"]) / 60))

        if dur_mins < 60:

            t["duration_str"] = f"{dur_mins}m"

        elif dur_mins < 1440:

            h = dur_mins // 60

            m = dur_mins % 60

            t["duration_str"] = f"{h}h {m}m" if m > 0 else f"{h}h"

        else:

            d = dur_mins // 1440

            h = (dur_mins % 1440) // 60

            t["duration_str"] = f"{d}d {h}h"



    # Summary Metrics Calculation

    wins = [t for t in trades if t["pnl"] > 0]

    losses = [t for t in trades if t["pnl"] <= 0]

    tot_gain = sum(t["pnl"] for t in wins)

    tot_loss = abs(sum(t["pnl"] for t in losses))

    pf = round(tot_gain / tot_loss, 2) if tot_loss > 0 else (99.0 if tot_gain > 0 else 0.0)

    net_pts = round(sum(t["pnl"] for t in trades), 2)

    win_rate = round((len(wins) / len(trades) * 100.0), 2) if trades else 0.0

    avg_trade = round(net_pts / len(trades), 2) if trades else 0.0



    avg_win = round(tot_gain / len(wins), 2) if wins else 0.0

    avg_loss = round(tot_loss / len(losses), 2) if losses else 0.0

    largest_win = round(max((t["pnl"] for t in wins), default=0.0), 2)

    largest_loss = round(min((t["pnl"] for t in losses), default=0.0), 2)



    # Streaks

    max_w_streak = 0

    max_l_streak = 0

    cur_w = 0

    cur_l = 0

    for t in trades:

        if t["pnl"] > 0:

            cur_w += 1

            cur_l = 0

            if cur_w > max_w_streak: max_w_streak = cur_w

        else:

            cur_l += 1

            cur_w = 0

            if cur_l > max_l_streak: max_l_streak = cur_l



    # Equity Curve Points & Benchmark

    equity_curve = []

    cum = 0.0

    peak = 0.0

    max_dd = 0.0

    for t in trades:

        cum += t["pnl"]

        if cum > peak:

            peak = cum

        dd = peak - cum

        if dd > max_dd:

            max_dd = dd

        equity_curve.append({

            "time": t["exit_time"],

            "cum_pnl": round(cum, 2),

            "dd": round(dd, 2),

            "trade_pnl": t["pnl"],

            "trade_id": t["id"]

        })



    # Benchmark Buy-and-Hold curve (Holding Nifty 50)

    benchmark_curve = []

    init_price = candles[0]["close"] if candles else 1.0

    for t in trades:

        bench_pts = round(t["exit_price"] - init_price, 2)

        benchmark_curve.append({

            "time": t["exit_time"],

            "bench_pts": bench_pts

        })



    # Last 30 Active Market Sessions (Image 1 Restore)

    strip_30_days = []

    for t in trades[-30:]:

        dt = datetime.datetime.fromtimestamp(t["exit_time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

        strip_30_days.append({

            "id": t["id"],

            "date": dt.strftime("%d %b"),

            "full_date": dt.strftime("%d %b %Y"),

            "pnl": t["pnl"],

            "pct": t["pnl_pct"],

            "inr": t["inr_pnl"],

            "up": t["pnl"] > 0,

            "entry_time": t["entry_time"],

            "exit_time": t["exit_time"]

        })



    # Returns Distribution Histogram Bins (-0.5% to +0.4%+)

    ret_bins = [

        {"bin": "<-0.4%", "min": -999.0, "max": -0.4, "count": 0, "is_win": False},

        {"bin": "-0.4%", "min": -0.4, "max": -0.3, "count": 0, "is_win": False},

        {"bin": "-0.3%", "min": -0.3, "max": -0.2, "count": 0, "is_win": False},

        {"bin": "-0.2%", "min": -0.2, "max": -0.1, "count": 0, "is_win": False},

        {"bin": "-0.1%", "min": -0.1, "max": 0.0, "count": 0, "is_win": False},

        {"bin": "+0.1%", "min": 0.0, "max": 0.1, "count": 0, "is_win": True},

        {"bin": "+0.2%", "min": 0.1, "max": 0.2, "count": 0, "is_win": True},

        {"bin": "+0.3%", "min": 0.2, "max": 0.3, "count": 0, "is_win": True},

        {"bin": "+0.4%", "min": 0.3, "max": 0.4, "count": 0, "is_win": True},

        {"bin": ">+0.4%", "min": 0.4, "max": 999.0, "count": 0, "is_win": True}

    ]

    for t in trades:

        pct = t["pnl_pct"]

        for b in ret_bins:

            if b["min"] <= pct < b["max"]:

                b["count"] += 1

                break



    avg_loss_pct = round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0.0

    avg_win_pct = round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0.0



    # Trades Distribution Donut & Expectancy

    trades_distribution = {

        "winners": len(wins),

        "losers": len(losses),

        "breakevens": 0,

        "total": len(trades),

        "win_rate": win_rate,

        "loss_rate": round(100.0 - win_rate, 2) if trades else 0.0,

        "breakeven_rate": 0.0

    }



    expectancy_pts = round(net_pts / len(trades), 2) if trades else 0.0

    expectancy_inr = round(expectancy_pts * inr_multiplier, 2)

    expectancy_pct = round((expectancy_pts / initial_capital_pts) * 100.0, 3)



    # Outliers PnL (top 5% most extreme trades)

    sorted_by_abs = sorted(trades, key=lambda x: abs(x["pnl"]), reverse=True)

    top_5_pct_cnt = max(1, int(len(trades) * 0.05))

    outliers_trades = sorted_by_abs[:top_5_pct_cnt]

    outliers_pnl_pts = round(sum(x["pnl"] for x in outliers_trades), 2)

    outliers_inr = round(outliers_pnl_pts * inr_multiplier, 2)

    outliers_pct = round((outliers_pnl_pts / initial_capital_pts) * 100.0, 2)



    # Time Patterns

    weekdays_labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    by_weekday = {w: {"pnl": 0.0, "trades": 0, "wins": 0} for w in weekdays_labels}

    for t in trades:

        w_idx = t["weekday_num"]

        if 0 <= w_idx < 5:

            w_name = weekdays_labels[w_idx]

            by_weekday[w_name]["pnl"] = round(by_weekday[w_name]["pnl"] + t["pnl"], 1)

            by_weekday[w_name]["trades"] += 1

            if t["pnl"] > 0:

                by_weekday[w_name]["wins"] += 1



    by_session = {

        "Morning (9:15-11)": {"pnl": 0.0, "trades": 0},

        "Midday (11-13:30)": {"pnl": 0.0, "trades": 0},

        "Afternoon (13:30-15:30)": {"pnl": 0.0, "trades": 0}

    }

    for t in trades:

        h = t["hour_num"]

        if h < 11:

            by_session["Morning (9:15-11)"]["pnl"] = round(by_session["Morning (9:15-11)"]["pnl"] + t["pnl"], 1)

            by_session["Morning (9:15-11)"]["trades"] += 1

        elif h < 13 or (h == 13 and int(t["entry_dt_ist"][14:16]) <= 30):

            by_session["Midday (11-13:30)"]["pnl"] = round(by_session["Midday (11-13:30)"]["pnl"] + t["pnl"], 1)

            by_session["Midday (11-13:30)"]["trades"] += 1

        else:

            by_session["Afternoon (13:30-15:30)"]["pnl"] = round(by_session["Afternoon (13:30-15:30)"]["pnl"] + t["pnl"], 1)

            by_session["Afternoon (13:30-15:30)"]["trades"] += 1



    # Monthly Matrix

    monthly_matrix = {"2024": {}, "2025": {}, "2026": {}}

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for y in monthly_matrix:

        for m in month_names:

            monthly_matrix[y][m] = {"pnl": 0.0, "trades": 0, "wins": 0}



    for t in trades:

        dt = datetime.datetime.fromtimestamp(t["exit_time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

        y_str = str(dt.year)

        m_str = dt.strftime("%b")

        if y_str in monthly_matrix and m_str in monthly_matrix[y_str]:

            cell = monthly_matrix[y_str][m_str]

            cell["pnl"] = round(cell["pnl"] + t["pnl"], 1)

            cell["trades"] += 1

            if t["pnl"] > 0:

                cell["wins"] += 1



    # Sharpe Ratio

    returns = [t["pnl_pct"] for t in trades]

    if len(returns) > 1:

        mean_ret = sum(returns) / len(returns)

        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)

        std_ret = math.sqrt(variance)

        sharpe = round((mean_ret / std_ret) * math.sqrt(252), 2) if std_ret > 0 else 0.0

    else:

        sharpe = 0.0



    # Markers (TradingView Image 2 Callout Badges)

    markers = []

    for t in trades:

        is_buy = t.get("side", "BUY") == "BUY"

        entry_price_val = t.get("entry_price", 0.0)

        entry_str = f"{entry_price_val:.2f}" if isinstance(entry_price_val, (int, float)) else str(entry_price_val)

        call_put = "BUY CALL" if is_buy else "BUY PUT"

        

        # Exact TradingView Image 2 Style Entry Badge: Solid Blue #2563eb

        markers.append({

            "time": t["entry_time"],

            "position": "belowBar" if is_buy else "aboveBar",

            "color": "#2563eb",

            "shape": "arrowUp" if is_buy else "arrowDown",

            "text": f"{call_put} | {entry_str}",

            "id": f"entry_{t['id']}",

            "trade_id": t["id"],

            "size": 2

        })

        is_win = t.get("pnl", 0.0) >= 0

        sign = "+" if is_win else ""

        pnl_val = t.get("pnl", 0.0)

        pnl_str = f"{sign}{pnl_val:.1f} pts" if isinstance(pnl_val, (int, float)) else str(pnl_val)

        

        # Exact TradingView Image 2 Style Exit Badge: Emerald #10b981 on win, Rose #f43f5e on loss

        markers.append({

            "time": t["exit_time"],

            "position": "aboveBar" if is_buy else "belowBar",

            "color": "#10b981" if is_win else "#f43f5e",

            "shape": "circle",

            "text": f"EXIT {pnl_str}",

            "id": f"exit_{t['id']}",

            "trade_id": t["id"],

            "size": 2

        })



    net_inr = round(net_pts * inr_multiplier, 2)

    net_pct = round((net_pts / initial_capital_pts) * 100.0, 2)

    max_dd_inr = round(max_dd * inr_multiplier, 2)

    max_dd_pct = round((max_dd / initial_capital_pts) * 100.0, 2)

    recovery_factor = round(net_pts / max_dd, 2) if max_dd > 0 else 99.0



    first_dt = datetime.datetime.fromtimestamp(candles[0]["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

    last_dt = datetime.datetime.fromtimestamp(candles[-1]["time"], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)

    period_label = f"{first_dt.strftime('%b %d, %Y')} – {last_dt.strftime('%b %d, %Y')} ({len(candles):,} Candles)"



    strategy_meta = {

        "inside_candle_vwap_ema": {

            "name": "🕯️ Inside Candle + VWAP + EMA Ribbon (Win Rate: 53.4%)",

            "rules": "Inside Candle volatility contraction breakout; confirmed by VWAP, EMA 9/21 cross, and Supertrend (10,3)",

            "stop": f"Stop Loss: {params.get('ic_sl_atr', 1.1)}x ATR Dynamic Stop",

            "target": f"Profit Target: {params.get('ic_target_r', 1.0)}R Multiple",

            "squareoff": "MIS Auto-Exit: 15:15 IST",

            "overlay_type": "ema"

        },

        "dual_supertrend_vwap": {

            "name": "🏆 Dual Supertrend (7,2 + 10,3) + VWAP Pulse",

            "rules": "Macro Supertrend (10,3) + VWAP + EMA 50 trend alignment; Fast Supertrend (7,2) pullback flip trigger",

            "stop": f"Stop Loss: {params.get('dual_st_sl_atr', 1.6)}x ATR Dynamic Stop",

            "target": f"Profit Target: {params.get('dual_st_target_r', 1.8)}R Multiple",

            "squareoff": "MIS Auto-Exit: 15:15 IST",

            "overlay_type": "supertrend"

        },

        "triple_momentum_fusion": {

            "name": "🚀 Triple Momentum Fusion (Win Rate: 53.8%, +5,565 pts)",

            "rules": "15-Bar Donchian Breakout + Supertrend (10,3) + 3-EMA Ribbon (9/21/50) + VWAP Anchor",

            "stop": f"Stop Loss: {params.get('tmf_sl_atr', 1.5)}x ATR Dynamic Stop",

            "target": f"Profit Target: {params.get('tmf_target_r', 1.8)}R Multiple",

            "squareoff": "MIS Auto-Exit: 15:15 IST",

            "overlay_type": "ema"

        },

        "adaptive_dual_orb": {

            "name": "⚡ Adaptive Dual ORB + Supertrend + VWAP (Win Rate: 54.5%, +8,734 pts)",

            "rules": "15-min Opening Range Breakout (09:15-09:30) with Long & Short bias confirmed by Supertrend & VWAP",

            "stop": f"Stop Loss: {params.get('dual_orb_sl_atr', 1.2)}x ATR Dynamic Stop",

            "target": f"Profit Target: {params.get('dual_orb_target_r', 1.8)}R Multiple",

            "squareoff": "MIS Auto-Exit: 15:15 IST",

            "overlay_type": "orb"

        },

        "orb": {

            "name": "15-min Opening Range Breakout (ORB)",

            "rules": "Breakout of 09:15–09:30 candle range before 14:00",

            "stop": f"Stop: {params.get('stop_type', 'or_mid').replace('_', ' ').upper()}",

            "target": f"Profit Target: {params.get('target_r', 2.0)}R Multiple",

            "squareoff": "MIS Auto-Exit: 15:15 IST",

            "overlay_type": "orb"

        },

        "ema_cross": {

            "name": f"{params.get('fast_ema', 9)} / {params.get('slow_ema', 21)} EMA Trend Crossover",

            "rules": f"Fast EMA ({params.get('fast_ema', 9)}) crosses Slow EMA ({params.get('slow_ema', 21)})",

            "stop": "Opposite EMA Cross",

            "target": "Trend Reversal",

            "squareoff": "Continuous Trend Following",

            "overlay_type": "ema"

        },

        "supertrend": {

            "name": f"Supertrend ({params.get('atr_period', 10)}, {params.get('multiplier', 3.0)})",

            "rules": "Trend direction flips from Bearish to Bullish",

            "stop": "Supertrend Trailing Band",

            "target": "Trend Flip to Bearish",

            "squareoff": "Trailing Stop",

            "overlay_type": "supertrend"

        },

        "bollinger": {

            "name": f"Bollinger Bands ({params.get('bb_period', 20)}, {params.get('bb_mult', 2.0)})",

            "rules": "Close penetrates Lower Band (Oversold Dip)",

            "stop": "Band Expansion / Lower Stop",

            "target": "Middle SMA (20) Baseline",

            "squareoff": "Mean Reversion Rebound",

            "overlay_type": "bollinger"

        },

        "rsi": {

            "name": f"RSI ({params.get('rsi_period', 14)}) Mean Reversion",

            "rules": f"RSI crosses back above {params.get('rsi_buy', 30)} (Oversold bounce)",

            "stop": "Recent Swing Low",

            "target": f"RSI reaches {params.get('rsi_sell', 70)} (Overbought)",

            "squareoff": "Momentum Exhaustion",

            "overlay_type": "rsi"

        },

        "macd": {

            "name": "MACD (12, 26, 9) Momentum Surge",

            "rules": "MACD line crosses Signal line upward in negative territory",

            "stop": "MACD Line flips Bearish",

            "target": "Signal Line downward divergence",

            "squareoff": "Bearish Signal Cross",

            "overlay_type": "macd"

        },

        "custom": {

            "name": f"Custom EMA + Dynamic Target/Stop",

            "rules": f"EMA ({params.get('custom_fast', 9)}/{params.get('custom_slow', 21)}) Crossover",

            "stop": f"Stop Loss: {params.get('custom_stop_pct', 0.75)}%",

            "target": f"Target: +{params.get('custom_target_pct', 1.5)}%",

            "squareoff": "Bracket Order Exit",

            "overlay_type": "custom"

        }

    }.get(strategy_type, {})



    return {

        "trades": trades,

        "markers": markers,

        "equity_curve": equity_curve,

        "benchmark_curve": benchmark_curve,

        "monthly_matrix": monthly_matrix,

        "strip_30_days": strip_30_days,

        "total_trades": len(trades),

        "wins": len(wins),

        "losses": len(losses),

        "win_rate": win_rate,

        "profit_factor": pf,

        "net_pnl_pts": net_pts,

        "net_inr": net_inr,

        "net_pct": net_pct,

        "avg_trade_pts": avg_trade,

        "avg_win_pts": avg_win,

        "avg_loss_pts": avg_loss,

        "avg_win_pct": avg_win_pct,

        "avg_loss_pct": avg_loss_pct,

        "largest_win_pts": largest_win,

        "largest_loss_pts": largest_loss,

        "max_w_streak": max_w_streak,

        "max_l_streak": max_l_streak,

        "max_drawdown_pts": round(max_dd, 2),

        "max_dd_inr": max_dd_inr,

        "max_dd_pct": max_dd_pct,

        "recovery_factor": recovery_factor,

        "sharpe_ratio": sharpe,

        "period_label": period_label,

        "candle_count": len(candles),

        "returns_distribution": ret_bins,

        "trades_distribution": trades_distribution,

        "expectancy": {

            "pts": expectancy_pts,

            "inr": expectancy_inr,

            "pct": expectancy_pct

        },

        "outliers": {

            "pts": outliers_pnl_pts,

            "inr": outliers_inr,

            "pct": outliers_pct,

            "trades": outliers_trades

        },

        "time_patterns": {

            "by_weekday": by_weekday,

            "by_session": by_session

        },

        "strategy_meta": strategy_meta_override if strategy_meta_override else strategy_meta,

        "parsed_inputs": parsed_inputs_override or [],

        "indicators": indicators_override if 'indicators_override' in locals() else {}

    }



def get_html_page():
    local_path = os.path.join(SCRIPT_DIR, "tradex_nse_backtest_engine.html")
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return f.read()
    desktop_path = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "tradex_nse_backtest_engine.html")
    if os.path.exists(desktop_path):
        with open(desktop_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<!DOCTYPE html><html><body>Error loading interface</body></html>"

HTML_PAGE = get_html_page()




class DashboardServer(http.server.BaseHTTPRequestHandler):

    def do_GET(self):

        url_parts = urllib.parse.urlparse(self.path)

        path = url_parts.path

        query = urllib.parse.parse_qs(url_parts.query)



        if path in ("/", "/index.html"):

            self.send_response(200)

            self.send_header("Content-Type", "text/html; charset=utf-8")

            self.end_headers()

            self.wfile.write(get_html_page().encode("utf-8"))



        elif path == "/static/lightweight-charts.js":

            js_path = os.path.join(STATIC_DIR, "lightweight-charts.js")

            if os.path.exists(js_path):

                self.send_response(200)

                self.send_header("Content-Type", "application/javascript")

                self.end_headers()

                with open(js_path, "rb") as f:

                    self.wfile.write(f.read())

            else:

                self.send_response(404)

                self.end_headers()



        elif path == "/api/pine/strategies":

            strats = load_all_pine_strategies()

            for s_id, s_data in strats.items():

                if "inputs" not in s_data:

                    parsed = parse_pine_script(s_data.get("code", ""))

                    s_data["inputs"] = parsed.get("inputs", [])

                    s_data["initial_capital"] = parsed.get("initial_capital", 500000.0)

                    s_data["default_qty"] = parsed.get("default_qty", 75)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps(strats).encode("utf-8"))



        elif path == "/api/live/quote":

            sym = query.get("symbol", ["^NSEI"])[0]

            tf = query.get("timeframe", ["5m"])[0]

            _, quote = fetch_live_intraday(sym, tf)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"quote": quote}).encode("utf-8"))

            return



        elif path == "/api/live/poll":

            sym = query.get("symbol", ["^NSEI"])[0]

            tf = query.get("timeframe", ["5m"])[0]

            bars, quote = fetch_live_intraday(sym, tf)

            if quote and quote.get("price", 0) > 0:
                PAPER_TRADER.check_position_limits(quote["price"])

            paper_state = PAPER_TRADER.get_state(quote["price"])

            res_data = {

                "quote": quote,

                "latest_bar": bars[-1] if bars else None,

                "recent_bars": bars[-5:] if bars else [],

                "paper_state": paper_state

            }

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps(res_data).encode("utf-8"))

            return



        elif path == "/api/candles":

            sym = query.get("symbol", ["^NSEI"])[0]

            tf = query.get("timeframe", ["5m"])[0]

            yr = query.get("year", ["all"])[0]

            start_date = query.get("start_date", [None])[0]

            end_date = query.get("end_date", [None])[0]

            start_ts = None

            end_ts = None

            if start_date and end_date:

                try:

                    sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")

                    ed = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)

                    start_ts = int(sd.replace(tzinfo=datetime.timezone.utc).timestamp()) - 19800

                    end_ts = int(ed.replace(tzinfo=datetime.timezone.utc).timestamp()) - 19800

                except Exception:

                    pass



            candles = get_market_data(sym, tf, yr, start_ts=start_ts, end_ts=end_ts)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"candles": candles}).encode("utf-8"))



        elif path == "/api/backtest":

            sym = query.get("symbol", ["^NSEI"])[0]

            tf = query.get("timeframe", ["5m"])[0]

            yr = query.get("year", ["all"])[0]

            strat = query.get("strategy", ["orb"])[0]

            start_date = query.get("start_date", [None])[0]

            end_date = query.get("end_date", [None])[0]

            start_ts = None

            end_ts = None

            if start_date and end_date:

                try:

                    sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")

                    ed = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)

                    start_ts = int(sd.replace(tzinfo=datetime.timezone.utc).timestamp()) - 19800

                    end_ts = int(ed.replace(tzinfo=datetime.timezone.utc).timestamp()) - 19800

                except Exception:

                    pass



            candles = get_market_data(sym, tf, yr, start_ts=start_ts, end_ts=end_ts)

            params = {k: v[0] for k, v in query.items()}

            params["timeframe"] = tf

            res = run_strategy(candles, strat, params, symbol=sym)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps(res).encode("utf-8"))



        else:

            self.send_response(404)

            self.end_headers()



    def do_POST(self):

        url_parts = urllib.parse.urlparse(self.path)

        path = url_parts.path



        content_len = int(self.headers.get("Content-Length", 0))

        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        try:

            body = json.loads(post_data)

        except Exception:

            body = {}



        if path == "/api/live/paper/order":

            action = body.get("action", "BUY")

            price = float(body.get("price", 0.0))

            reason = body.get("reason", "Manual Order")

            sl = float(body.get("stop_loss", 0.0))

            tp = float(body.get("take_profit", 0.0))

            record = PAPER_TRADER.execute_order(action, price, reason, sl, tp)

            state = PAPER_TRADER.get_state(price)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"order": record, "state": state}).encode("utf-8"))

            return



        elif path == "/api/live/paper/close":

            price = float(body.get("price", 0.0))

            record = PAPER_TRADER.close_position(price, reason=body.get("reason", "Manual Flatten"))

            state = PAPER_TRADER.get_state(price)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"closed": record, "state": state}).encode("utf-8"))

            return



        elif path == "/api/live/paper/reset":

            PAPER_TRADER.reset()

            state = PAPER_TRADER.get_state()

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"success": True, "state": state}).encode("utf-8"))

            return



        elif path == "/api/live/paper/toggle_auto":

            PAPER_TRADER.auto_execute = not PAPER_TRADER.auto_execute

            state = PAPER_TRADER.get_state()

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"auto_execute": PAPER_TRADER.auto_execute, "state": state}).encode("utf-8"))

            return



        elif path == "/api/live/evaluate":

            code_text = body.get("code", "")

            params = body.get("params", {})

            sym = body.get("symbol", "^NSEI")

            tf = body.get("timeframe", "5m")

            candles = get_market_data(sym, tf)

            # Run strategy

            res = run_strategy(candles, "pine_custom", {**params, "custom_pine_code": code_text}, symbol=sym)

            trades = res.get("trades", [])

            last_trade = trades[-1] if trades else None

            

            # Determine current signal based on latest bar & indicators

            latest_bar = candles[-1] if candles else {}

            latest_price = latest_bar.get("close", 0.0)

            

            signal = "NEUTRAL"

            reason = "No active trigger on current bar"

            sl = 0.0

            tp = 0.0

            

            if last_trade:

                # If last trade exit time is in the future or matches latest bar, signal is active

                exit_time = last_trade.get("exit_time", 0)

                entry_time = last_trade.get("entry_time", 0)

                if exit_time >= latest_bar.get("time", 0) - 300:

                    signal = last_trade.get("action", "NEUTRAL")

                    reason = f"Active {signal} from bar at entry price {last_trade.get('entry_price')}"

                    sl = last_trade.get("entry_price", latest_price) * (0.995 if signal == "BUY" else 1.005)

                    tp = last_trade.get("entry_price", latest_price) * (1.01 if signal == "BUY" else 0.99)

                    

                    # Auto execute paper trade if enabled

                    if PAPER_TRADER.auto_execute and (not PAPER_TRADER.position or PAPER_TRADER.position["action"] != signal):

                        PAPER_TRADER.execute_order(signal, latest_price, f"Live Signal: {reason}", sl, tp)



            paper_state = PAPER_TRADER.get_state(latest_price)

            eval_payload = {

                "signal": signal,

                "price": latest_price,

                "reason": reason,

                "stop_loss": round(sl, 2),

                "take_profit": round(tp, 2),

                "latest_bar": latest_bar,

                "trade_count": len(trades),

                "paper_state": paper_state

            }

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps(eval_payload).encode("utf-8"))

            return



        if path == "/api/pine/save":

            code = body.get("code", "")

            s_id = body.get("id")

            name = body.get("name")

            strat = save_custom_pine_strategy(code, s_id, name)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"success": True, "strategy": strat}).encode("utf-8"))



        elif path == "/api/pine/parse":

            code = body.get("code", "")

            parsed = parse_pine_script(code)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps(parsed).encode("utf-8"))



        elif path == "/api/pine/run":

            code = body.get("code", "")

            params = body.get("params", {})

            sym = body.get("symbol", "^NSEI")

            tf = body.get("timeframe", "5m")

            yr = body.get("year", "all")

            start_date = body.get("start_date")

            end_date = body.get("end_date")

            start_ts = None

            end_ts = None

            if start_date and end_date:

                try:

                    sd = datetime.datetime.strptime(start_date, "%Y-%m-%d")

                    ed = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)

                    start_ts = int(sd.replace(tzinfo=datetime.timezone.utc).timestamp()) - 19800

                    end_ts = int(ed.replace(tzinfo=datetime.timezone.utc).timestamp()) - 19800

                except Exception:

                    pass



            candles = get_market_data(sym, tf, yr, start_ts=start_ts, end_ts=end_ts)

            res = run_strategy(candles, "pine_custom", {**params, "timeframe": tf, "custom_pine_code": code}, symbol=sym)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps(res).encode("utf-8"))



        elif path == "/api/pine/delete":

            s_id = body.get("id")

            success = delete_custom_pine_strategy(s_id)

            self.send_response(200)

            self.send_header("Content-Type", "application/json")

            self.send_header("Access-Control-Allow-Origin", "*")

            self.end_headers()

            self.wfile.write(json.dumps({"success": success}).encode("utf-8"))



        else:

            self.send_response(404)

            self.end_headers()



    def do_OPTIONS(self):

        self.send_response(204)

        self.send_header("Access-Control-Allow-Origin", "*")

        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        self.send_header("Access-Control-Allow-Headers", "Content-Type")

        self.end_headers()



    def log_message(self, format, *args):

        pass



def main():

    parser = argparse.ArgumentParser(description="Web3Bento Quant Studio Server")

    default_port = int(os.environ.get("PORT", 8080))
    parser.add_argument("--port", type=int, default=default_port)
    socketserver.TCPServer.allow_reuse_address = True

    args = parser.parse_args()



    for p in range(args.port, args.port + 20):

        try:

            server = socketserver.TCPServer(("0.0.0.0", p), DashboardServer)

            print("============================================================")

            print(" WEB3BENTO QUANT STUDIO RUNNING")

            print(f" URL: http://localhost:{p}")

            print("============================================================")

            server.serve_forever()

            break

        except OSError:

            continue



if __name__ == "__main__":

    main()

