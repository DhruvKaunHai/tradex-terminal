import datetime
import json
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
YAHOO_HOST = "https://query2.finance.yahoo.com"

def test_fetch():
    interval = "5m"
    bar_seconds = 300
    ticker = "^NSEI"
    url = f"{YAHOO_HOST}/v8/finance/chart/{urllib.request.quote(ticker)}?interval={interval}&range=5d"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        res = data["chart"]["result"][0]
        meta = res["meta"]
        ts = res.get("timestamp", [])
        q = res["indicators"]["quote"][0]
        
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
        now = time.time()
        forming_time = (int(now) // bar_seconds) * bar_seconds

        # Ensure active forming bar exists on grid
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

        print('Aligned bars count:', len(bars))
        print('Last 3 bars:')
        for b in bars[-3:]:
            dt = datetime.datetime.fromtimestamp(b['time'], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
            print(b['time'], dt.strftime('%H:%M:%S'), b)
        print('Seconds to next bar:', bar_seconds - (int(now) % bar_seconds))

test_fetch()
