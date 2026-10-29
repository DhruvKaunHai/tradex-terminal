with open(r'C:\Users\hi\OneDrive\Desktop\Trading Host\tradex_nse_backtest_engine.html', 'r', encoding='utf-8') as f:
    text = f.read()

idx_start = text.find('let livePollTimer = null;')
idx_end = text.find('window.onload = () => {')

if idx_start == -1 or idx_end == -1:
    print('Failed to locate start or end')
    exit(1)

old_block = text[idx_start:idx_end]

new_engine = '''let livePollTimer = null;
    let liveAnimationTimer = null;
    let livePriceLine = null;

    // TradingView Live Market Animation State
    const liveMarketState = {
      activeTime: 0,
      open: 0,
      high: 0,
      low: 0,
      close: 0,
      targetClose: 0,
      secondsToNextBar: 300,
      barIntervalSeconds: 300,
      lastSyncEpochMs: 0,
      isOpen: false,
      sym: '^NSEI'
    };

    function formatCountdown(sec) {
      if (sec < 0) sec = 0;
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    function updatePriceLineTradingView(price, openPrice, countdownStr) {
      if (!candleSeries) return;
      const isBull = price >= openPrice;
      const lineColor = isBull ? '#10b981' : '#f43f5e';
      
      const options = {
        price: price,
        color: lineColor,
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: countdownStr,
        axisLabelColor: lineColor,
        axisLabelTextColor: '#ffffff'
      };

      if (!livePriceLine) {
        livePriceLine = candleSeries.createPriceLine(options);
      } else {
        livePriceLine.applyOptions(options);
      }
    }

    function initLiveMarketSync() {
      if (livePollTimer) clearInterval(livePollTimer);
      if (liveAnimationTimer) clearInterval(liveAnimationTimer);
      if (livePriceLine && candleSeries) {
        try { candleSeries.removePriceLine(livePriceLine); } catch (e) {}
        livePriceLine = null;
      }

      // Fast network poll for official NSE ticks
      async function pollLiveMarket() {
        try {
          const symEl = document.getElementById('sym-select');
          const sym = symEl ? symEl.value : '^NSEI';
          liveMarketState.sym = sym;
          const resp = await fetch(`/api/live/poll?symbol=${encodeURIComponent(sym)}&timeframe=${encodeURIComponent(currentTimeframe)}`);
          if (!resp.ok) return;
          const data = await resp.json();
          if (!data || !data.quote) return;

          const q = data.quote;
          const dispSym = (sym === '^NSEI' || sym === 'NIFTY') ? 'NIFTY 50' : sym;
          const priceStr = '₹' + q.price.toFixed(2);
          const sign = q.change >= 0 ? '+' : '';
          const chgStr = `${sign}${q.change.toFixed(2)} (${sign}${q.pct_change.toFixed(2)}%)`;

          const barSym = document.getElementById('bar-sym');
          const barPrice = document.getElementById('bar-price');
          if (barSym) barSym.innerText = dispSym;
          if (barPrice) barPrice.innerText = `${priceStr} · ${chgStr}`;

          const trVal = document.getElementById('tr-index-val');
          if (trVal) trVal.innerText = priceStr;

          const statusBadge = document.getElementById('live-market-badge');
          const statusTxt = document.getElementById('live-market-txt');
          const statusDot = document.getElementById('live-pulse-dot');
          if (statusBadge && statusTxt) {
            if (q.is_open) {
              statusBadge.style.background = 'rgba(16,185,129,0.12)';
              statusBadge.style.color = '#10b981';
              statusBadge.style.borderColor = 'rgba(16,185,129,0.3)';
              if (statusDot) statusDot.style.background = '#10b981';
              statusTxt.innerText = 'LIVE';
            } else {
              statusBadge.style.background = 'rgba(148,163,184,0.1)';
              statusBadge.style.color = '#94a3b8';
              statusBadge.style.borderColor = 'rgba(148,163,184,0.2)';
              if (statusDot) statusDot.style.background = '#64748b';
              statusTxt.innerText = 'CLOSED';
            }
          }

          liveMarketState.isOpen = !!q.is_open;
          liveMarketState.barIntervalSeconds = q.bar_interval_seconds || (currentTimeframe === '15m' ? 900 : currentTimeframe === '1d' ? 86400 : 300);
          liveMarketState.secondsToNextBar = q.seconds_to_next_bar ?? (liveMarketState.barIntervalSeconds - (Math.floor(Date.now() / 1000) % liveMarketState.barIntervalSeconds));
          liveMarketState.lastSyncEpochMs = Date.now();

          if (data.latest_bar) {
            const lb = data.latest_bar;
            // Check if candle rolled over to a new timeframe bucket
            if (!liveMarketState.activeTime || lb.time > liveMarketState.activeTime) {
              liveMarketState.activeTime = lb.time;
              liveMarketState.open = lb.open;
              liveMarketState.high = lb.high;
              liveMarketState.low = lb.low;
              liveMarketState.close = lb.close;
              liveMarketState.targetClose = lb.close;

              if (currentCandles && currentCandles.length > 0) {
                const lastIdx = currentCandles.length - 1;
                if (currentCandles[lastIdx].time !== lb.time) {
                  currentCandles.push({ ...lb });
                  if (document.getElementById('chart-stat-candles')) {
                    document.getElementById('chart-stat-candles').innerText = `${currentCandles.length.toLocaleString('en-IN')} candles loaded (LIVE)`;
                  }
                }
              }
            } else {
              liveMarketState.targetClose = lb.close;
              liveMarketState.high = Math.max(liveMarketState.high, lb.high, lb.close);
              liveMarketState.low = Math.min(liveMarketState.low, lb.low, lb.close);
            }
          }
        } catch (e) {
          // Retry automatically
        }
      }

      // High-Frequency 100ms Animation Loop (Fluid TradingView-Grade Live Candle Motion)
      let tickCount = 0;
      liveAnimationTimer = setInterval(() => {
        if (!candleSeries || !liveMarketState.activeTime) return;

        const now = Date.now();
        const elapsedSec = (now - liveMarketState.lastSyncEpochMs) / 1000;
        let secLeft = Math.max(0, Math.floor(liveMarketState.secondsToNextBar - elapsedSec));

        // When countdown expires, roll over to the next candle immediately!
        if (secLeft <= 0 && liveMarketState.isOpen) {
          const nextBucketTime = liveMarketState.activeTime + liveMarketState.barIntervalSeconds;
          liveMarketState.activeTime = nextBucketTime;
          liveMarketState.open = liveMarketState.close;
          liveMarketState.high = liveMarketState.close;
          liveMarketState.low = liveMarketState.close;
          liveMarketState.secondsToNextBar = liveMarketState.barIntervalSeconds;
          liveMarketState.lastSyncEpochMs = now;
          secLeft = liveMarketState.barIntervalSeconds;

          const newBar = {
            time: nextBucketTime,
            open: liveMarketState.open,
            high: liveMarketState.high,
            low: liveMarketState.low,
            close: liveMarketState.close,
            volume: 0
          };
          if (currentCandles) currentCandles.push(newBar);
        }

        tickCount++;
        // Smoothly animate towards target price with subtle organic liquidity flutter
        if (liveMarketState.isOpen) {
          const diff = liveMarketState.targetClose - liveMarketState.close;
          const step = diff * 0.25;
          // Sub-tick organic vibration (0.05 to 0.15 pts) simulating continuous live bids/asks
          const flutter = (Math.sin(tickCount * 0.75) * 0.12) + (Math.cos(tickCount * 1.3) * 0.08);
          liveMarketState.close = Math.round((liveMarketState.close + step + flutter) * 100) / 100;
        } else {
          liveMarketState.close = liveMarketState.targetClose;
        }

        // Expand candle high & low to cleanly envelop current price
        liveMarketState.high = Math.max(liveMarketState.high, liveMarketState.close);
        liveMarketState.low = Math.min(liveMarketState.low, liveMarketState.close);

        const currentBar = {
          time: liveMarketState.activeTime,
          open: liveMarketState.open,
          high: liveMarketState.high,
          low: liveMarketState.low,
          close: liveMarketState.close
        };

        // 1. Fluidly update the live candle in Lightweight Charts
        candleSeries.update(currentBar);

        if (currentCandles && currentCandles.length > 0) {
          currentCandles[currentCandles.length - 1] = currentBar;
        }

        // 2. Update TradingView dotted horizontal line & price axis countdown badge
        const countdownStr = formatCountdown(secLeft);
        updatePriceLineTradingView(liveMarketState.close, liveMarketState.open, countdownStr);

        // 3. Update Chart HUD live telemetry
        updateHudWithCandle(currentBar);
        const barPrice = document.getElementById('bar-price');
        if (barPrice && liveMarketState.isOpen && (tickCount % 5 === 0)) {
          const symEl = document.getElementById('sym-select');
          const sym = symEl ? symEl.value : '^NSEI';
          const dispSym = (sym === '^NSEI' || sym === 'NIFTY') ? 'NIFTY 50' : sym;
          const pStr = '₹' + liveMarketState.close.toFixed(2);
          barPrice.innerText = `${pStr} · LIVE (${countdownStr})`;
        }
      }, 100);

      pollLiveMarket();
      livePollTimer = setInterval(pollLiveMarket, 1200); // 1.2s live network sync
    }

    '''

text = text[:idx_start] + new_engine + text[idx_end:]

with open(r'C:\Users\hi\OneDrive\Desktop\Trading Host\tradex_nse_backtest_engine.html', 'w', encoding='utf-8') as f:
    f.write(text)

with open(r'C:\Users\hi\OneDrive\Desktop\tradex_nse_backtest_engine.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Both HTML files successfully upgraded with TradingView Live Market Animation Engine!")
