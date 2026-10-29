# 🚀 NSE Quant Studio & TradingView Pine Terminal [Trading Host]

An institutional-grade, zero-dependency quantitative backtesting workstation and charting terminal with native **TradingView Pine Script v5** parity and **Real-Time Live Market Synchronization & Forward Testing**.

---

## 🌟 Highlights & Capabilities

- **100% Zero External Dependencies**: Runs entirely on Python's Standard Library (`http.server`, `socketserver`, `json`, `math`, `csv`, `datetime`, `urllib`). No `pip install` required!
- **⚡ Live Market Blending & Real-Time Tick Streaming**:
  - Automatically fetches live intraday candles (5m/15m) from Indian markets and seamlessly weaves them onto historical data.
  - Updates the active forming candle in real-time with zero lag.
  - Next candle countdown timer (`⏱ Next Candle in 02:45`) and Indian Standard Time (IST) clock.
- **⚡ Live Forward Tester & Paper Trading Simulator**:
  - Real-time Strategy Signal Radar (evaluates Apex Symphony v2 or custom Pine scripts against forming candles).
  - Virtual Paper Trading Account (₹5,00,000 capital, 1 lot 75 Qty NIFTY default).
  - Auto-Trade Signals mode or manual 1-click execution (`BUY MKT`, `SELL MKT`, `FLATTEN`).
  - Dynamic unrealized P&L in ₹ and points tracked tick-by-tick.
- **High-Density Historical Data**: Pre-loaded with **52,107 5-minute candles** spanning 2024 to 2026 across Indian market sessions (9:15 AM - 3:30 PM IST).
- **Offline High-FPS Charting**: Bundled with TradingView Lightweight Charts v4.1 for interactive candlestick panning, zooming, volume histogram, and EMA/Supertrend overlay rendering.
- **Apex Trend-Momentum Symphony v2**: The refined multi-engine strategy combining Adaptive Trend Phase, Dual-Oscillator Momentum, Dynamic Stop-Loss/Trailing, and Time-Window Session Filters.
- **TradingView Workflow Parity**:
  - **$f_x$ Indicators & Strategies Dialog**: Add, remove, preview, or inspect Pine strategies.
  - **Strategy Settings Dialog**: Grouped Inputs (Phase Engine, Filter Bands, Risk & Exits, Session Time Window) with live slider & number controls.
  - **Pine Script Editor Dock**: Syntax-highlighted code editor with line gutter and "Save & Add to Chart".
  - **Strategy Tester Dock**: Performance Overview, Detailed Metrics Table (Win Rate, Profit Factor, Max Drawdown, Expectancy), and complete List of Trades table.

---

## ⚡ Quick Start

### 1-Click Launch (Windows)
Double-click `start_terminal.bat`. Your browser will open at:
```
http://localhost:8080/
```

### Manual Command Line Launch
```bash
python server.py --port 8080
```

---

## 📂 Folder Structure

```
Trading Host/
├── server.py                   # Self-contained zero-dependency backend server
├── app.py                      # Server entry point alias
├── live_market.py              # Real-time market feed, blending & paper trading engine
├── pine_engine.py              # Pine Script v5 parser & quantitative backtest engine
├── custom_pine_strategies.json # Strategy database with Apex Symphony v2 & defaults
├── apex_trend_symphony.txt     # Raw Pine Script v5 code for Apex Symphony v2
├── start_terminal.bat          # 1-Click Windows batch launcher
├── start_terminal.ps1          # PowerShell launcher
├── Open Terminal.url           # Web shortcut to http://localhost:8080/
├── Dockerfile                  # Container definition for instant cloud deployment
├── requirements.txt            # Zero-dependency spec (standard library only)
├── HOW_TO_LAUNCH.txt           # Plain-text quick guide
├── README.md                   # This documentation
├── data/                       # Historical NIFTY datasets (5m & 15m JSON/CSV)
└── static/                     # Standalone Lightweight Charts library
```

---

## 🌐 Live Hosting Options

### 1. Instant Tunneling (Zero Setup)
```bash
# Using Cloudflare Quick Tunnels:
cloudflared tunnel --url http://localhost:8080
```

### 2. Free Cloud Platforms (Render / Railway)
- Repository: Push this folder to GitHub.
- Runtime: Python 3.
- Start Command: `python server.py --port $PORT`

### 3. Docker Deployment
```bash
docker build -t quant-terminal .
docker run -d -p 8080:8080 quant-terminal
```
