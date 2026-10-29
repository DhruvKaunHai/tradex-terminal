import json

with open(r'C:\Users\hi\OneDrive\Desktop\Trading Host\custom_pine_strategies.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

if 'apex_ribbon_v3_5m' in data:
    data['apex_institutional_ribbon'] = data['apex_ribbon_v3_5m']
    with open(r'C:\Users\hi\OneDrive\Desktop\Trading Host\custom_pine_strategies.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print("Added apex_institutional_ribbon to custom_pine_strategies.json in Trading Host")

# Also check Backtesting dir
import os
bp = r'C:\Users\hi\OneDrive\Desktop\Backtesting\custom_pine_strategies.json'
if os.path.exists(bp):
    with open(bp, 'r', encoding='utf-8') as f:
        data2 = json.load(f)
    data2['apex_institutional_ribbon'] = data2.get('apex_ribbon_v3_5m', {})
    with open(bp, 'w', encoding='utf-8') as f:
        json.dump(data2, f, indent=2)
    print("Added apex_institutional_ribbon to custom_pine_strategies.json in Backtesting")
