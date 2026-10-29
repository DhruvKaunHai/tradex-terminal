def patch_html(filepath):
    print(f"Patching {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Disable default series price line and lastValue in initChart
    old_init = '''if (typeof chart.addCandlestickSeries === 'function') {
        candleSeries = chart.addCandlestickSeries({
          upColor: '#10b981', downColor: '#f43f5e', borderVisible: false,
          wickUpColor: '#10b981', wickDownColor: '#f43f5e'
        });
      } else {
        candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
          upColor: '#10b981', downColor: '#f43f5e', borderVisible: false,
          wickUpColor: '#10b981', wickDownColor: '#f43f5e'
        });
      }'''

    new_init = '''if (typeof chart.addCandlestickSeries === 'function') {
        candleSeries = chart.addCandlestickSeries({
          upColor: '#10b981', downColor: '#f43f5e', borderVisible: false,
          wickUpColor: '#10b981', wickDownColor: '#f43f5e',
          lastValueVisible: false,
          priceLineVisible: false
        });
      } else {
        candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
          upColor: '#10b981', downColor: '#f43f5e', borderVisible: false,
          wickUpColor: '#10b981', wickDownColor: '#f43f5e',
          lastValueVisible: false,
          priceLineVisible: false
        });
      }'''

    text = text.replace(old_init, new_init)

    # 2. Update the live animation loop to:
    # - Run EXACTLY every 1 second (1000ms, not less or more)
    # - Fall behind by 1 second (1-sec delayed buffer)
    # - Zero micro-flutter / zero flickering
    # - Exactly ONE clean price badge with countdown
    idx_start = text.find('let livePollTimer = null;')
    idx_end = text.find('window.onload = () => {')

    if idx_start == -1 or idx_end == -1:
        print("Failed to locate live animation loop bounds!")
        return False

    new_engine = '''let livePollTimer = null;
    let liveAnimationTimer = null;
    let livePriceLine = null;

    // TradingView Live Market Animation State (Strict 1-Second Cadence, 1-Sec Lag)
    const liveMarketState = {
      activeTime: 0,
      open: 0,
      high: 0,
      low: 0,
      close: 0,
      targetClose: 0,
      priceBuffer: [], // Delayed by 1 second
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

      // Fast network poll for official NSE ticks (every 1s)
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

          // Push into 1-sec lag buffer
          liveMarketState.priceBuffer.push({ epochMs: Date.now(), price: q.price });
          if (liveMarketState.priceBuffer.length > 20) liveMarketState.priceBuffer.shift();

          if (data.latest_bar) {
            const lb = data.latest_bar;
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

      // STRICT 1-SECOND CADENCE ENGINE (Exactly 1000ms, not less or more, 1-sec lag)
      liveAnimationTimer = setInterval(() => {
        if (!candleSeries || !liveMarketState.activeTime) return;

        const now = Date.now();
        const elapsedSec = (now - liveMarketState.lastSyncEpochMs) / 1000;
        
        // 1-second lag: countdown and price fall behind by exactly 1 sec
        let secLeft = Math.max(0, Math.floor(liveMarketState.secondsToNextBar - elapsedSec - 1));

        // When countdown reaches 0, roll over to the next candle cleanly
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

        // Apply 1-second delayed price from buffer (Zero flicker, rock-solid steady ticks)
        const lagTargetTime = now - 1000; // 1 second behind
        let lagPrice = liveMarketState.targetClose;
        for (let i = liveMarketState.priceBuffer.length - 1; i >= 0; i--) {
          if (liveMarketState.priceBuffer[i].epochMs <= lagTargetTime) {
            lagPrice = liveMarketState.priceBuffer[i].price;
            break;
          }
        }

        if (lagPrice && lagPrice > 0) {
          liveMarketState.close = lagPrice;
        }

        liveMarketState.high = Math.max(liveMarketState.high, liveMarketState.close);
        liveMarketState.low = Math.min(liveMarketState.low, liveMarketState.close);

        const currentBar = {
          time: liveMarketState.activeTime,
          open: liveMarketState.open,
          high: liveMarketState.high,
          low: liveMarketState.low,
          close: liveMarketState.close
        };

        // 1. Update the live candle once per second
        candleSeries.update(currentBar);

        if (currentCandles && currentCandles.length > 0) {
          currentCandles[currentCandles.length - 1] = currentBar;
        }

        // 2. Update TradingView dotted horizontal line & single price scale tag
        const countdownStr = formatCountdown(secLeft);
        updatePriceLineTradingView(liveMarketState.close, liveMarketState.open, countdownStr);

        // 3. Update Chart HUD live telemetry
        updateHudWithCandle(currentBar);
      }, 1000); // STRICT 1-SECOND FREQUENCY (NOT LESS OR MORE)

      pollLiveMarket();
      livePollTimer = setInterval(pollLiveMarket, 1000); // 1-second network sync
    }

    '''

    text = text[:idx_start] + new_engine + text[idx_end:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Successfully patched {filepath}")
    return True

patch_html(r'C:\Users\hi\OneDrive\Desktop\Trading Host\tradex_nse_backtest_engine.html')
patch_html(r'C:\Users\hi\OneDrive\Desktop\tradex_nse_backtest_engine.html')
