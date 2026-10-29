import datetime
import json
import os
import sys
import time
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
YAHOO_HOST = "https://query2.finance.yahoo.com"

# In-memory cache for live requests to avoid rate limits
_LIVE_CACHE = {}
_CACHE_TTL = 3.0  # seconds

def get_ist_now():
    """Returns current datetime in Indian Standard Time (UTC+05:30)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist = utc_now + datetime.timedelta(hours=5, minutes=30)
    return ist

def get_market_session_status():
    """Calculates if NSE is currently open, in pre-market, or closed."""
    ist = get_ist_now()
    weekday = ist.weekday()  # 0=Monday, 4=Friday, 5=Sat, 6=Sun
    time_min = ist.hour * 60 + ist.minute

    if weekday >= 5:
        return {"status": "CLOSED", "label": "WEEKEND CLOSED", "is_open": False}
    
    # 09:00 - 09:15 Pre-open
    if 9 * 60 <= time_min < 9 * 60 + 15:
        return {"status": "PRE_MARKET", "label": "PRE-OPEN SESSION", "is_open": False}
    # 09:15 - 15:30 Regular Trading
    elif 9 * 60 + 15 <= time_min < 15 * 60 + 30:
        return {"status": "OPEN", "label": "MARKET OPEN (LIVE)", "is_open": True}
    # 15:30 - 16:00 Post-close
    elif 15 * 60 + 30 <= time_min < 16 * 60:
        return {"status": "POST_MARKET", "label": "POST-MARKET CLOSING", "is_open": False}
    else:
        return {"status": "CLOSED", "label": "MARKET CLOSED", "is_open": False}

def normalize_ticker(symbol):
    sym = symbol.strip().upper()
    if sym in ("NIFTY", "NIFTY 50", "NIFTY50", "^NSEI"):
        return "^NSEI"
    if sym in ("BANKNIFTY", "BANK NIFTY", "^NSEBANK"):
        return "^NSEBANK"
    if sym.startswith("^") or sym.endswith(".NS"):
        return sym
    return f"{sym}.NS"

def fetch_live_intraday(symbol="^NSEI", interval="5m", range_str="5d"):
    """Fetches high-resolution live intraday bars and quote metadata from Yahoo Finance."""
    ticker = normalize_ticker(symbol)
    cache_key = f"{ticker}_{interval}_{range_str}"
    now = time.time()
    
    if cache_key in _LIVE_CACHE:
        entry = _LIVE_CACHE[cache_key]
        if now - entry["time"] < _CACHE_TTL:
            return entry["bars"], entry["quote"]

    url = f"{YAHOO_HOST}/v8/finance/chart/{urllib.request.quote(ticker)}?interval={interval}&range={range_str}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = data["chart"]["result"][0]
            meta = res["meta"]
            ts = res.get("timestamp", [])
            q = res["indicators"]["quote"][0]
            
            bar_seconds = 300 if interval == "5m" else 900 if interval == "15m" else 86400 if interval == "1d" else 60
            bar_map = {}
            for i in range(len(ts)):
                if q["open"][i] is not None and q["close"][i] is not None:
                    raw_t = ts[i]
                    b_time = (raw_t // bar_seconds) * bar_seconds
                    o = round(q["open"][i], 2)
                    h = round(q["high"][i], 2)
                    l = round(q["low"][i], 2)
                    c = round(q["close"][i], 2)
                    v = int(q["volume"][i] or 0)
                    if b_time not in bar_map:
                        bar_map[b_time] = {"time": b_time, "open": o, "high": h, "low": l, "close": c, "volume": v}
                    else:
                        existing = bar_map[b_time]
                        existing["high"] = max(existing["high"], h)
                        existing["low"] = min(existing["low"], l)
                        existing["close"] = c
                        existing["volume"] += v

            bars = sorted(bar_map.values(), key=lambda x: x["time"])
            price = meta.get("regularMarketPrice", bars[-1]["close"] if bars else 0.0)
            prev_close = meta.get("chartPreviousClose", meta.get("previousClose", bars[0]["open"] if bars else price))
            change = round(price - prev_close, 2)
            pct_change = round((change / prev_close * 100), 2) if prev_close else 0.0
            
            session = get_market_session_status()
            ist_str = get_ist_now().strftime("%d-%b-%Y %H:%M:%S IST")
            
            quote = {
                "symbol": ticker,
                "display_name": "NIFTY 50" if ticker == "^NSEI" else "BANK NIFTY" if ticker == "^NSEBANK" else ticker.replace(".NS", ""),
                "price": round(price, 2),
                "prev_close": round(prev_close, 2),
                "change": change,
                "pct_change": pct_change,
                "day_high": round(meta.get("regularMarketDayHigh", max((b["high"] for b in bars), default=price)), 2),
                "day_low": round(meta.get("regularMarketDayLow", min((b["low"] for b in bars), default=price)), 2),
                "market_status": session["status"],
                "market_label": session["label"],
                "is_open": session["is_open"],
                "server_time_ist": ist_str,
                "bar_count": len(bars),
                "latest_bar_ts": bars[-1]["time"] if bars else int(now)
            }
            
            # Calculate seconds to next bar
            bar_seconds = 300 if interval == "5m" else 900 if interval == "15m" else 60
            # Ensure active forming bar exists on exact timeframe grid
            forming_time = (int(now) // bar_seconds) * bar_seconds
            if bars:
                if bars[-1]["time"] < forming_time:
                    prev_c = bars[-1]["close"]
                    forming_bar = {
                        "time": forming_time,
                        "open": prev_c,
                        "high": max(prev_c, price),
                        "low": min(prev_c, price),
                        "close": price,
                        "volume": 0
                    }
                    bars.append(forming_bar)
                else:
                    bars[-1]["close"] = price
                    bars[-1]["high"] = max(bars[-1]["high"], price)
                    bars[-1]["low"] = min(bars[-1]["low"], price)
                    bars[-1]["time"] = forming_time

            quote["latest_bar_ts"] = bars[-1]["time"] if bars else forming_time
            quote["seconds_to_next_bar"] = bar_seconds - (int(now) % bar_seconds)
            quote["bar_interval_seconds"] = bar_seconds
            
            _LIVE_CACHE[cache_key] = {"bars": bars, "quote": quote, "time": now}
            return bars, quote
    except Exception as e:
        print(f"[LIVE_FEED_ERROR] {ticker}: {e}", file=sys.stderr)
        # Fallback quote if network glitch
        session = get_market_session_status()
        quote = {
            "symbol": ticker,
            "display_name": ticker,
            "price": 0.0,
            "prev_close": 0.0,
            "change": 0.0,
            "pct_change": 0.0,
            "day_high": 0.0,
            "day_low": 0.0,
            "market_status": session["status"],
            "market_label": session["label"],
            "is_open": session["is_open"],
            "server_time_ist": get_ist_now().strftime("%d-%b-%Y %H:%M:%S IST"),
            "bar_count": 0,
            "latest_bar_ts": int(now),
            "seconds_to_next_bar": 300
        }
        return [], quote

def blend_historical_with_live(historical_candles, live_bars):
    """Seamlessly weaves local baseline history with live real-time candles."""
    if not live_bars:
        return historical_candles
    if not historical_candles:
        return live_bars

    candle_map = {c["time"]: c for c in historical_candles}
    for b in live_bars:
        candle_map[b["time"]] = b  # Updates forming candle or appends newer
        
    return sorted(candle_map.values(), key=lambda x: x["time"])


# ---------------------------------------------------------------------
# Live Paper Trading Simulator Manager
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# Telegram Real-time Trade Alert Dispatcher
# ---------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8736862150:AAHqqWc0kXYqtgpWDkAA4PIKQ8H-2iMcej0")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1149546127")

def send_telegram_alert(text):
    """Dispatches real-time trade alerts to Telegram asynchronously in background thread."""
    def _send():
        try:
            import urllib.request
            import urllib.parse
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = urllib.parse.urlencode({
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"User-Agent": "TradeX/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                pass
        except Exception as e:
            print(f"[TELEGRAM_DISPATCH_ERROR] {e}", file=sys.stderr)

    import threading
    threading.Thread(target=_send, daemon=True).start()

class LivePaperTrader:
    def __init__(self, initial_capital=500000.0, lot_size=75):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.lot_size = lot_size
        self.position = None  # None or {"action": "BUY"|"SELL", "entry_price": 0.0, "qty": 75, "entry_time": 0, "stop_loss": 0.0, "take_profit": 0.0}
        self.trade_history = []
        self.auto_execute = True

    def get_state(self, current_price=0.0):
        unrealized_pts = 0.0
        unrealized_inr = 0.0
        if self.position and current_price > 0:
            if self.position["action"] == "BUY":
                unrealized_pts = current_price - self.position["entry_price"]
            else:
                unrealized_pts = self.position["entry_price"] - current_price
            unrealized_inr = unrealized_pts * self.position["qty"]

        realized_inr = sum(t.get("pnl_inr", 0.0) for t in self.trade_history)
        net_equity = self.capital + unrealized_inr

        enriched_trades = []
        for t in self.trade_history:
            tr = dict(t)
            if "entry_time" not in tr:
                if tr.get("entry_time_ist"):
                    try:
                        parts = list(map(int, tr["entry_time_ist"].split(":")))
                        dt = get_ist_now().replace(hour=parts[0], minute=parts[1], second=parts[2] if len(parts) > 2 else 0, microsecond=0)
                        tr["entry_time"] = int(dt.timestamp())
                    except Exception:
                        tr["entry_time"] = int(time.time()) - 300
                else:
                    tr["entry_time"] = int(time.time()) - 300
            if "exit_time" not in tr:
                if tr.get("exit_time_ist"):
                    try:
                        parts = list(map(int, tr["exit_time_ist"].split(":")))
                        dt = get_ist_now().replace(hour=parts[0], minute=parts[1], second=parts[2] if len(parts) > 2 else 0, microsecond=0)
                        tr["exit_time"] = int(dt.timestamp())
                    except Exception:
                        tr["exit_time"] = int(time.time())
                else:
                    tr["exit_time"] = int(time.time())
            enriched_trades.append(tr)

        return {
            "initial_capital": self.initial_capital,
            "capital": round(self.capital, 2),
            "net_equity": round(net_equity, 2),
            "realized_inr": round(realized_inr, 2),
            "unrealized_pts": round(unrealized_pts, 2),
            "unrealized_inr": round(unrealized_inr, 2),
            "position": self.position,
            "lot_size": self.lot_size,
            "trade_count": len(self.trade_history),
            "trades": enriched_trades[-20:],  # last 20 trades
            "auto_execute": self.auto_execute
        }

    def execute_order(self, action, price, reason="Manual Order", sl=0.0, tp=0.0):
        now_ts = int(time.time())
        ist_str = get_ist_now().strftime("%H:%M:%S")

        # If already in opposite position, close it first
        if self.position and self.position["action"] != action:
            self.close_position(price, reason=f"Reverse to {action}")

        # If not in position, open new
        if not self.position and action in ("BUY", "SELL"):
            self.position = {
                "action": action,
                "entry_price": round(price, 2),
                "qty": self.lot_size,
                "entry_time": now_ts,
                "entry_time_ist": ist_str,
                "stop_loss": round(sl, 2) if sl > 0 else (round(price * 0.995, 2) if action == "BUY" else round(price * 1.005, 2)),
                "take_profit": round(tp, 2) if tp > 0 else (round(price * 1.01, 2) if action == "BUY" else round(price * 0.99, 2)),
                "reason": reason
            }
            order_record = {
                "id": len(self.trade_history) + 1,
                "type": "OPEN",
                "action": action,
                "price": round(price, 2),
                "qty": self.lot_size,
                "time": now_ts,
                "time_ist": ist_str,
                "reason": reason,
                "status": "FILLED"
            }

            # Send Telegram Execution Alert
            action_tag = "BUY CALL (LONG)" if action == "BUY" else "BUY PUT (SHORT)"
            sl_val = self.position["stop_loss"]
            tp_val = self.position["take_profit"]
            sl_pts = abs(round(price - sl_val, 2))
            tp_pts = abs(round(tp_val - price, 2))
            
            tg_msg = (
                f"🟢 *TRADE EXECUTED [ENTRY]*\n\n"
                f"• *Strategy:* APEX NEW\n"
                f"• *Instrument:* NIFTY 50\n"
                f"• *Action:* {action_tag}\n"
                f"• *Entry Price:* ₹{price:.2f}\n"
                f"• *Lots / Qty:* 1 Lot ({self.lot_size} qty)\n"
                f"• *Stop Loss:* ₹{sl_val:.2f} (-{sl_pts:.2f} pts)\n"
                f"• *Take Profit:* ₹{tp_val:.2f} (+{tp_pts:.2f} pts)\n"
                f"• *Trigger:* {reason}\n"
                f"• *Time:* {ist_str} IST\n"
                f"• *Status:* FILLED ✅"
            )
            send_telegram_alert(tg_msg)
            return order_record

        return None

    def close_position(self, exit_price, reason="Exit"):
        if not self.position:
            return None

        pos = self.position
        now_ts = int(time.time())
        ist_str = get_ist_now().strftime("%H:%M:%S")

        if pos["action"] == "BUY":
            pnl_pts = exit_price - pos["entry_price"]
        else:
            pnl_pts = pos["entry_price"] - exit_price

        pnl_inr = pnl_pts * pos["qty"]
        self.capital += pnl_inr

        record = {
            "id": len(self.trade_history) + 1,
            "type": "CLOSE",
            "action": pos["action"],
            "entry_price": pos["entry_price"],
            "exit_price": round(exit_price, 2),
            "pnl_pts": round(pnl_pts, 2),
            "pnl_inr": round(pnl_inr, 2),
            "qty": pos["qty"],
            "entry_time": pos.get("entry_time", now_ts - 300),
            "exit_time": now_ts,
            "entry_time_ist": pos.get("entry_time_ist", ""),
            "exit_time_ist": ist_str,
            "reason": reason,
            "capital_after": round(self.capital, 2)
        }
        self.trade_history.append(record)

        # Send Telegram Completion Alert
        dur_mins = max(1, (now_ts - pos.get("entry_time", now_ts)) // 60)
        dur_str = f"{dur_mins}m" if dur_mins < 60 else f"{dur_mins // 60}h {dur_mins % 60}m"
        action_name = "BUY CALL" if pos["action"] == "BUY" else "BUY PUT"
        pnl_sign = "+" if pnl_pts >= 0 else ""
        icon = "🏁" if pnl_pts >= 0 else "🛑"
        win_label = "PROFIT TARGET / WIN" if pnl_pts >= 0 else "STOP LOSS / DRAWDOWN"

        tg_msg = (
            f"{icon} *TRADE COMPLETED [EXIT]*\n\n"
            f"• *Strategy:* APEX NEW\n"
            f"• *Instrument:* NIFTY 50\n"
            f"• *Position Closed:* {action_name}\n"
            f"• *Entry Price:* ₹{pos['entry_price']:.2f} ({pos.get('entry_time_ist', '')})\n"
            f"• *Exit Price:* ₹{exit_price:.2f} ({ist_str} IST)\n"
            f"• *Outcome:* {win_label}\n"
            f"• *Exit Reason:* {reason}\n"
            f"• *PnL (Points):* `{pnl_sign}{pnl_pts:.2f} pts`\n"
            f"• *PnL (INR):* `{pnl_sign}₹{pnl_inr:,.2f}`\n"
            f"• *Duration:* {dur_str}\n"
            f"• *Account Balance:* ₹{self.capital:,.2f}"
        )
        send_telegram_alert(tg_msg)

        self.position = None
        return record

    def check_position_limits(self, current_price):
        """Checks if active position hit SL, TP, or ratchet trailing stop."""
        if not self.position or current_price <= 0:
            return None

        pos = self.position
        action = pos["action"]
        sl = pos["stop_loss"]
        tp = pos["take_profit"]

        if action == "BUY":
            if current_price >= tp:
                return self.close_position(current_price, reason=f"Target Hit (+{round(tp - pos['entry_price'], 2)} pts)")
            elif current_price <= sl:
                return self.close_position(current_price, reason=f"Stop Loss Hit (-{round(pos['entry_price'] - sl, 2)} pts)")
        elif action == "SELL":
            if current_price <= tp:
                return self.close_position(current_price, reason=f"Target Hit (+{round(pos['entry_price'] - tp, 2)} pts)")
            elif current_price >= sl:
                return self.close_position(current_price, reason=f"Stop Loss Hit (-{round(sl - pos['entry_price'], 2)} pts)")

        return None

def reset(self):
        self.capital = self.initial_capital
        self.position = None
        self.trade_history = []
        return True


# Global paper trader instance
PAPER_TRADER = LivePaperTrader()
