import sys

def fix_indent(filepath):
    print(f"Fixing indentation in {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    bad_block = '''        def check_position_limits(self, current_price):
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

        return None'''

    good_block = '''    def check_position_limits(self, current_price):
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

        return None'''

    if bad_block in code:
        code = code.replace(bad_block, good_block)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        print("Indentation fixed successfully!")
    else:
        print("Could not find exact bad block, checking...")

fix_indent(r"C:\Users\hi\OneDrive\Desktop\Trading Host\live_market.py")
fix_indent(r"C:\Users\hi\OneDrive\Desktop\Backtesting\dashboard\live_market.py")
