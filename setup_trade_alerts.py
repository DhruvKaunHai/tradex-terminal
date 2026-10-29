import os

def patch_live_trader_telegram(filepath):
    print(f"Patching {filepath} with Telegram alerts...")
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    # 1. Add Telegram Alert Function at top of class LivePaperTrader
    if "send_telegram_alert" not in code:
        tg_header = '''# ---------------------------------------------------------------------
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

'''
        idx_class = code.find("class LivePaperTrader:")
        if idx_class != -1:
            code = code[:idx_class] + tg_header + code[idx_class:]

    # 2. Update execute_order to dispatch Telegram Entry Alert
    old_exec = '''            order_record = {
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
            return order_record'''

    new_exec = '''            order_record = {
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
                f"🟢 *TRADE EXECUTED [ENTRY]*\\n\\n"
                f"• *Strategy:* APEX NEW\\n"
                f"• *Instrument:* NIFTY 50\\n"
                f"• *Action:* {action_tag}\\n"
                f"• *Entry Price:* ₹{price:.2f}\\n"
                f"• *Lots / Qty:* 1 Lot ({self.lot_size} qty)\\n"
                f"• *Stop Loss:* ₹{sl_val:.2f} (-{sl_pts:.2f} pts)\\n"
                f"• *Take Profit:* ₹{tp_val:.2f} (+{tp_pts:.2f} pts)\\n"
                f"• *Trigger:* {reason}\\n"
                f"• *Time:* {ist_str} IST\\n"
                f"• *Status:* FILLED ✅"
            )
            send_telegram_alert(tg_msg)
            return order_record'''

    code = code.replace(old_exec, new_exec)

    # 3. Update close_position to dispatch Telegram Exit Alert
    old_close = '''        self.trade_history.append(record)
        self.position = None
        return record'''

    new_close = '''        self.trade_history.append(record)

        # Send Telegram Completion Alert
        dur_mins = max(1, (now_ts - pos.get("entry_time", now_ts)) // 60)
        dur_str = f"{dur_mins}m" if dur_mins < 60 else f"{dur_mins // 60}h {dur_mins % 60}m"
        action_name = "BUY CALL" if pos["action"] == "BUY" else "BUY PUT"
        pnl_sign = "+" if pnl_pts >= 0 else ""
        icon = "🏁" if pnl_pts >= 0 else "🛑"
        win_label = "PROFIT TARGET / WIN" if pnl_pts >= 0 else "STOP LOSS / DRAWDOWN"

        tg_msg = (
            f"{icon} *TRADE COMPLETED [EXIT]*\\n\\n"
            f"• *Strategy:* APEX NEW\\n"
            f"• *Instrument:* NIFTY 50\\n"
            f"• *Position Closed:* {action_name}\\n"
            f"• *Entry Price:* ₹{pos['entry_price']:.2f} ({pos.get('entry_time_ist', '')})\\n"
            f"• *Exit Price:* ₹{exit_price:.2f} ({ist_str} IST)\\n"
            f"• *Outcome:* {win_label}\\n"
            f"• *Exit Reason:* {reason}\\n"
            f"• *PnL (Points):* `{pnl_sign}{pnl_pts:.2f} pts`\\n"
            f"• *PnL (INR):* `{pnl_sign}₹{pnl_inr:,.2f}`\\n"
            f"• *Duration:* {dur_str}\\n"
            f"• *Account Balance:* ₹{self.capital:,.2f}"
        )
        send_telegram_alert(tg_msg)

        self.position = None
        return record'''

    code = code.replace(old_close, new_close)

    # 4. Add check_position_limits to LivePaperTrader
    if "def check_position_limits" not in code:
        check_fn = '''    def check_position_limits(self, current_price):
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

'''
        idx_reset = code.find("def reset(self):")
        if idx_reset != -1:
            code = code[:idx_reset] + check_fn + code[idx_reset:]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Finished patching {filepath}")

patch_live_trader_telegram(r"C:\Users\hi\OneDrive\Desktop\Trading Host\live_market.py")
if os.path.exists(r"C:\Users\hi\OneDrive\Desktop\Backtesting\dashboard\live_market.py"):
    patch_live_trader_telegram(r"C:\Users\hi\OneDrive\Desktop\Backtesting\dashboard\live_market.py")
