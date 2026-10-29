import re
import json

def clean_html(filepath):
    print(f"Cleaning emojis and updating APEX NEW in {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Update dropdown options
    old_opt1 = '<option value="apex_symphony_v2" selected>👑 #1 Apex Symphony v2 [Auto 5m/15m]</option>'
    new_opt1 = '<option value="apex_symphony_v2" selected>APEX NEW (Auto 5m/15m)</option>'
    text = text.replace(old_opt1, new_opt1)

    old_opt2 = '<option value="apex_institutional_ribbon">⚡ #2 Apex Institutional 4-EMA Ribbon [5m]</option>'
    new_opt2 = '<option value="apex_institutional_ribbon">Apex Institutional 4-EMA Ribbon (5m)</option>'
    text = text.replace(old_opt2, new_opt2)

    # Clean any other occurrence in select
    text = text.replace('👑 #1 Apex Symphony v2 [Auto 5m/15m]', 'APEX NEW (Auto 5m/15m)')
    text = text.replace('⚡ #2 Apex Institutional 4-EMA Ribbon [5m]', 'Apex Institutional 4-EMA Ribbon (5m)')

    # 2. Update metaMap
    old_meta1 = 'apex_symphony_v2: { name: "👑 Apex Trend-Momentum Symphony v2"'
    new_meta1 = 'apex_symphony_v2: { name: "APEX NEW (Trend-Momentum Symphony)"'
    text = text.replace(old_meta1, new_meta1)

    old_meta2 = 'apex_institutional_ribbon: { name: "⚡ Apex Institutional 4-EMA Ribbon & Volatility Squeeze [5m]"'
    new_meta2 = 'apex_institutional_ribbon: { name: "Apex Institutional 4-EMA Ribbon & Volatility Squeeze (5m)"'
    text = text.replace(old_meta2, new_meta2)

    # 3. Clean emojis from modal categories & titles
    text = text.replace('<span>👑</span> Flagship Strategies', '<span>★</span> Flagship Strategies')
    text = text.replace('<span>👑</span> Multi-Factor Trend Composite (Apex Symphony v2)', 'Multi-Factor Trend Composite (APEX NEW)')
    text = text.replace('<span>⚡</span> 15m Quantum ORB + Trend Filter (MIS 15:15)', '15m Quantum ORB + Trend Filter (MIS 15:15)')
    text = text.replace('<span>🏆</span> Dual Supertrend (7,2 / 10,3) + VWAP Pulse', 'Dual Supertrend (7,2 / 10,3) + VWAP Pulse')
    text = text.replace('<span>⚡</span> Exponential Moving Average Cross (EMA 9 / 21)', 'Exponential Moving Average Cross (EMA 9 / 21)')
    text = text.replace('⚡ METHOD 1: INSTANT WI-FI ACCESS', 'METHOD 1: INSTANT WI-FI ACCESS')

    # Remove any remaining 👑 or ⚡
    text = text.replace('👑', '')
    text = text.replace('⚡', '')
    text = text.replace('🏆', '')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Successfully cleaned {filepath}")

clean_html(r'C:\Users\hi\OneDrive\Desktop\Trading Host\tradex_nse_backtest_engine.html')
clean_html(r'C:\Users\hi\OneDrive\Desktop\tradex_nse_backtest_engine.html')

# Clean custom_pine_strategies.json
for p in [r'C:\Users\hi\OneDrive\Desktop\Trading Host\custom_pine_strategies.json', r'C:\Users\hi\OneDrive\Desktop\Backtesting\custom_pine_strategies.json']:
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, dict) and 'name' in v:
                name = v['name']
                name = name.replace('👑', '').replace('⚡', '').replace('🏆', '').strip()
                if 'Apex Symphony v2' in name or 'Apex Trend-Momentum Symphony v2' in name:
                    name = 'APEX NEW (Auto 5m/15m)'
                v['name'] = name
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"Cleaned {p}")
    except Exception as e:
        print(f"Error on {p}: {e}")
