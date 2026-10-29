import os
import json
import re
import datetime
import math

PINE_STORAGE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "custom_pine_strategies.json"))

# -------------------------------------------------------------
# 1. ADVANCED PINE SCRIPT v5 PARSER (TradingView Spec)
# -------------------------------------------------------------
def parse_pine_script(code):
    strategy_match = re.search(r'strategy\s*\(\s*["\']([^"\']+)["\']', code)
    strat_name = strategy_match.group(1) if strategy_match else "Custom Pine Strategy"
    
    overlay_match = re.search(r'overlay\s*=\s*(true|false)', code, re.IGNORECASE)
    overlay = overlay_match.group(1).lower() == "true" if overlay_match else True
    
    init_cap_match = re.search(r'initial_capital\s*=\s*([0-9\.]+)', code)
    init_capital = float(init_cap_match.group(1)) if init_cap_match else 500000.0

    qty_match = re.search(r'default_qty_value\s*=\s*([0-9\.]+)', code)
    default_qty = int(qty_match.group(1)) if qty_match else 75

    # Match groups like: grp_st = "1. Supertrend Settings"
    groups = {}
    for gm in re.finditer(r'(\w+)\s*=\s*["\']([^"\']+)["\']', code):
        if gm.group(1).startswith('grp_'):
            groups[gm.group(1)] = gm.group(2)

    inputs = []
    lines = code.split('\n')
    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('//'):
            continue
        
        m = re.match(r'(\w+)\s*=\s*input(?:\.(string|float|int|bool|session))?\s*\((.*)\)', line_clean)
        if m:
            var_name = m.group(1)
            in_type = m.group(2) or "float"
            args_str = m.group(3)
            
            title = var_name.replace("_", " ").title()
            title_m = re.search(r'(?:title\s*=\s*)?["\']([^"\']+)["\']', args_str)
            if title_m:
                title = title_m.group(1)
                
            group = "General Inputs"
            grp_m = re.search(r'group\s*=\s*(\w+|["\'][^"\']+["\'])', args_str)
            if grp_m:
                grp_raw = grp_m.group(1).strip('"\'')
                group = groups.get(grp_raw, grp_raw)

            step = 0.1 if in_type == "float" else 1
            step_m = re.search(r'step\s*=\s*([0-9\.]+)', args_str)
            if step_m:
                step = float(step_m.group(1))

            minval = None
            min_m = re.search(r'minval\s*=\s*([0-9\.\-]+)', args_str)
            if min_m:
                minval = float(min_m.group(1)) if in_type == "float" else int(float(min_m.group(1)))

            maxval = None
            max_m = re.search(r'maxval\s*=\s*([0-9\.\-]+)', args_str)
            if max_m:
                maxval = float(max_m.group(1)) if in_type == "float" else int(float(max_m.group(1)))

            options = None
            opt_m = re.search(r'options\s*=\s*\[(.*?)\]', args_str)
            if opt_m:
                options = [x.strip().strip('"\'') for x in opt_m.group(1).split(',') if x.strip()]

            first_arg = args_str.split(',')[0].strip()
            def_val = first_arg.strip('"\'')
            if in_type == "bool":
                def_val = def_val.lower() == "true"
            elif in_type == "int":
                try: def_val = int(def_val)
                except: def_val = 0
            elif in_type == "float":
                try: def_val = float(def_val)
                except: def_val = 0.0

            inputs.append({
                "var": var_name,
                "title": title,
                "type": in_type,
                "default": def_val,
                "group": group,
                "step": step,
                "minval": minval,
                "maxval": maxval,
                "options": options
            })

    return {
        "name": strat_name,
        "overlay": overlay,
        "initial_capital": init_capital,
        "default_qty": default_qty,
        "inputs": inputs
    }

# -------------------------------------------------------------
# 2. DEFAULT TEMPLATES PRE-SEEDED
# -------------------------------------------------------------
DEFAULT_PINE_TEMPLATES = {
    "pine_apex_symphony": {
        "id": "pine_apex_symphony",
        "name": "👑 Apex Trend-Momentum Symphony v2 [NSE Quant Studio]",
        "category": "Institutional Apex",
        "code": """// This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
// © NSE Quant Studio — #1 Apex Trend-Momentum Symphony v2 (5m & 15m Auto-Adaptive + Visual Callout Engine)

//@version=5
strategy("Apex Trend-Momentum Symphony v2 [NSE Quant Studio]", shorttitle="Apex Symphony v2", overlay=true, initial_capital=500000, default_qty_type=strategy.fixed, default_qty_value=75, currency=currency.INR, commission_type=strategy.commission.cash_per_order, commission_value=0.0, calc_on_every_tick=false, process_orders_on_close=true, max_labels_count=500, max_lines_count=500)

// ============================================================================
// 1. TIMEFRAME PROFILE & STRATEGY INPUTS
// ============================================================================
grp_prof     = "0. Timeframe Optimization Profile"
profileMode  = input.string("Auto (5m & 15m+ Optimized)", "Parameter Profile Mode", options=["Auto (5m & 15m+ Optimized)", "Force 5m Scalper Profile", "Force 15m Swing Profile", "Custom Manual Inputs"], group=grp_prof)

grp_st       = "1. Supertrend Settings (Manual Override)"
stPeriodIn   = input.int(14, "Supertrend ATR Length (5m=14, 15m=10)", minval=1, group=grp_st)
stMultIn     = input.float(3.5, "Supertrend Multiplier (5m=3.5, 15m=3.0)", minval=0.5, step=0.1, group=grp_st)

grp_ema      = "2. 3-EMA Trend Ribbon (Manual Override)"
emaFastIn    = input.int(9, "Fast EMA Length (5m=9, 15m=8)", minval=1, group=grp_ema)
emaSlowIn    = input.int(21, "Slow EMA Length (21)", minval=1, group=grp_ema)
emaMacIn     = input.int(50, "Macro EMA Length (5m=50, 15m=55)", minval=1, group=grp_ema)

grp_mom      = "3. Intraday VWAP, RSI & ADX Chop Filter"
rsiLen       = input.int(14, "RSI Length", minval=1, group=grp_mom)
rsiLongIn    = input.float(58.0, "RSI Long Threshold (5m=58, 15m=52)", minval=50.0, maxval=80.0, step=0.5, group=grp_mom)
rsiShortIn   = input.float(42.0, "RSI Short Threshold (5m=42, 15m=48)", minval=20.0, maxval=50.0, step=0.5, group=grp_mom)
adxLen       = input.int(14, "ADX Chop Filter Length", minval=1, group=grp_mom)
adxMinIn     = input.float(16.0, "Minimum ADX Trend Strength (0 = Off)", minval=0.0, maxval=50.0, step=1.0, group=grp_mom)
maxLegIn     = input.int(2, "Max Entries Per Supertrend Wave", minval=1, maxval=20, group=grp_mom)
vwapMode     = input.string("Equal-Weighted (Nifty Spot)", "Intraday Anchor Mode", options=["Equal-Weighted (Nifty Spot)", "Volume-Weighted VWAP"], group=grp_mom)

grp_risk     = "4. Two-Stage Ratchet, Target & Trailing Stop"
atrLen       = input.int(14, "Stop ATR Length", minval=1, group=grp_risk)
slAtrIn      = input.float(1.8, "Initial Stop Loss x ATR (5m=1.8, 15m=1.6)", minval=0.2, step=0.1, group=grp_risk)
minAtrFloor  = input.float(15.0, "Minimum ATR Floor (Nifty Pts)", minval=0.0, step=1.0, group=grp_risk)
beTrigIn     = input.float(1.0, "Stage-1 Breakeven Trigger (x R)", minval=0.0, step=0.1, group=grp_risk)
beOffIn      = input.float(0.25, "Stage-1 Breakeven Lock Offset (+x R)", minval=0.0, step=0.05, group=grp_risk)
lock2TrigIn  = input.float(2.0, "Stage-2 Profit-Lock Trigger (x R)", minval=0.0, step=0.1, group=grp_risk)
lock2OffIn   = input.float(1.10, "Stage-2 Profit-Lock Offset (+x R)", minval=0.0, step=0.05, group=grp_risk)
tpRIn        = input.float(3.5, "Profit Target Multiple (x R, 5m=3.5, 15m=4.5, 0=Off)", minval=0.0, step=0.1, group=grp_risk)
useStTrail   = input.bool(true, "Enable Live Supertrend Trailing Stop", group=grp_risk)

grp_vis      = "5. Visual Callout Engine & HUD (Image 2 Style)"
showCallouts = input.bool(true, "Show BUY CALL / BUY PUT & EXIT PnL Badges", group=grp_vis)
entryStyle   = input.string("Solid Blue (Image 2 Style)", "Entry Badge Color Theme", options=["Solid Blue (Image 2 Style)", "Green Call / Red Put"], group=grp_vis)
displayLots  = input.int(1, "Badge Display Qty (Lots)", minval=1, group=grp_vis)
lotSize      = input.int(75, "Nifty Lot Size (Units per Lot)", minval=1, group=grp_vis)
showRibbons  = input.bool(false, "Show Background EMA Ribbon Lines", group=grp_vis)
showStLine   = input.bool(true, "Show Supertrend Spine Line", group=grp_vis)
showTradeLvls= input.bool(true, "Show Active Entry / Stop / Target Lines", group=grp_vis)
showHud      = input.bool(true, "Show Quant Studio Telemetry HUD Table", group=grp_vis)
intradayOnly = input.bool(false, "Strict Intraday MIS Mode (Flat at 15:15 IST)", group=grp_vis)

// ============================================================================
// 2. AUTO-ADAPTIVE PARAMETER RESOLUTION (5m vs 15m+)
// ============================================================================
is5mChart = timeframe.isminutes and timeframe.multiplier <= 5
use5mProf = (profileMode == "Force 5m Scalper Profile") or (profileMode == "Auto (5m & 15m+ Optimized)" and is5mChart)
use15mProf= (profileMode == "Force 15m Swing Profile") or (profileMode == "Auto (5m & 15m+ Optimized)" and not is5mChart)

stPeriod    = use5mProf ? 14   : use15mProf ? 10   : stPeriodIn
stMult      = use5mProf ? 3.5  : use15mProf ? 3.0  : stMultIn
emaFastP    = use5mProf ? 9    : use15mProf ? 8    : emaFastIn
emaSlowP    = use5mProf ? 21   : use15mProf ? 21   : emaSlowIn
emaMacP     = use5mProf ? 50   : use15mProf ? 55   : emaMacIn
rsiLong     = use5mProf ? 58.0 : use15mProf ? 52.0 : rsiLongIn
rsiShort    = use5mProf ? 42.0 : use15mProf ? 48.0 : rsiShortIn
adxMin      = use5mProf ? 16.0 : use15mProf ? 16.0 : adxMinIn
maxLegTrades= use5mProf ? 2    : use15mProf ? 2    : maxLegIn
slAtrMult   = use5mProf ? 1.8  : use15mProf ? 1.6  : slAtrIn
beTriggerR  = use5mProf ? 1.0  : use15mProf ? 1.1  : beTrigIn
beOffsetR   = use5mProf ? 0.25 : use15mProf ? 0.20 : beOffIn
lock2TrigR  = use5mProf ? 2.0  : use15mProf ? 2.2  : lock2TrigIn
lock2OffR   = use5mProf ? 1.10 : use15mProf ? 1.20 : lock2OffIn
tpR         = use5mProf ? 3.5  : use15mProf ? 4.5  : tpRIn

// ============================================================================
// 3. CORE INDICATORS (SUPERTREND, 3-EMA, INTRADAY VWAP, RSI, ADX)
// ============================================================================
emaFast = ta.ema(close, emaFastP)
emaSlow = ta.ema(close, emaSlowP)
emaMac  = ta.ema(close, emaMacP)
rsiVal  = ta.rsi(close, rsiLen)

trVal   = ta.tr(true)
atr14   = ta.rma(trVal, atrLen)
curAtr  = math.max(nz(atr14, minAtrFloor), minAtrFloor)

// Wilder's ADX (14) Calculation (100% Native & Non-Repainting)
upMove   = high - nz(high[1], high)
dnMove   = nz(low[1], low) - low
plusDm   = (upMove > dnMove and upMove > 0) ? upMove : 0.0
minusDm  = (dnMove > upMove and dnMove > 0) ? dnMove : 0.0
adxAtr   = nz(ta.rma(trVal, adxLen), 1.0)
plusDi   = 100.0 * nz(ta.rma(plusDm, adxLen), 0.0) / math.max(adxAtr, 0.0001)
minusDi  = 100.0 * nz(ta.rma(minusDm, adxLen), 0.0) / math.max(adxAtr, 0.0001)
diSum    = plusDi + minusDi
dxVal    = diSum > 0 ? (100.0 * math.abs(plusDi - minusDi) / diSum) : 0.0
adxVal   = nz(ta.rma(dxVal, adxLen), 0.0)

// Exact Supertrend Engine
stAtr      = ta.rma(trVal, stPeriod)
hl2Val     = (high + low) / 2.0
basicUpper = hl2Val + (stMult * nz(stAtr, 0.0))
basicLower = hl2Val - (stMult * nz(stAtr, 0.0))

var float upperBand = na
var float lowerBand = na
var int   stTrend   = 1
var float stLine    = na
var int   legTrades = 0

if na(stAtr) or na(upperBand[1]) or bar_index <= stPeriod
    upperBand := basicUpper
    lowerBand := basicLower
    stTrend   := 1
    stLine    := basicLower
else
    upperBand := (basicUpper < upperBand[1] or close[1] > upperBand[1]) ? basicUpper : upperBand[1]
    lowerBand := (basicLower > lowerBand[1] or close[1] < lowerBand[1]) ? basicLower : lowerBand[1]
    if stTrend[1] == 1
        stTrend := close < lowerBand ? -1 : 1
    else
        stTrend := close > upperBand ? 1 : -1
    stLine := stTrend == 1 ? lowerBand : upperBand

if stTrend != stTrend[1]
    legTrades := 0

// Intraday VWAP (with automatic Nifty Spot zero-volume compatibility)
isNewDay = timeframe.change("D")
var float cumHlc3 = 0.0
var int   cumBars = 0
var float cumPv   = 0.0
var float cumVol  = 0.0
volSafe = nz(volume, 0.0)

if isNewDay or bar_index == 0
    cumHlc3 := hlc3
    cumBars := 1
    cumPv   := hlc3 * volSafe
    cumVol  := volSafe
else
    cumHlc3 += hlc3
    cumBars += 1
    cumPv   += hlc3 * volSafe
    cumVol  += volSafe

eqWeightedVwap  = cumHlc3 / cumBars
volWeightedVwap = cumVol > 0 ? (cumPv / cumVol) : eqWeightedVwap
intradayVwap    = (vwapMode == "Equal-Weighted (Nifty Spot)") ? eqWeightedVwap : volWeightedVwap

// IST Session Helper
istHour        = hour(time, "Asia/Kolkata")
istMinute      = minute(time, "Asia/Kolkata")
tInt           = istHour * 100 + istMinute
inEntryWindow  = not intradayOnly or (tInt >= 920 and tInt <= 1430)
isMisSquareoff = intradayOnly and (tInt >= 1515)

// ============================================================================
// 4. ENTRY & TWO-STAGE RATCHET EXIT ENGINE
// ============================================================================
var float entryPrice  = na
var float initRisk    = na
var float activeStop  = na
var float activeTp    = na
var int   ratchetStage= 0

inLong  = strategy.position_size > 0
inShort = strategy.position_size < 0
inPos   = strategy.position_size != 0

if inLong
    if beTriggerR > 0 and not na(entryPrice) and not na(initRisk) and high >= (entryPrice + initRisk * beTriggerR)
        longBeStop = math.round((entryPrice + initRisk * beOffsetR) * 100.0) / 100.0
        if na(activeStop) or longBeStop > activeStop
            activeStop   := longBeStop
            ratchetStage := math.max(ratchetStage, 1)
    if lock2TrigR > 0 and not na(entryPrice) and not na(initRisk) and high >= (entryPrice + initRisk * lock2TrigR)
        longL2Stop = math.round((entryPrice + initRisk * lock2OffR) * 100.0) / 100.0
        if na(activeStop) or longL2Stop > activeStop
            activeStop   := longL2Stop
            ratchetStage := math.max(ratchetStage, 2)
    if useStTrail and stTrend == 1 and not na(stLine) and (na(activeStop) or stLine > activeStop)
        activeStop := math.round(stLine * 100.0) / 100.0
    if tpR > 0 and not na(activeTp)
        strategy.exit("Long Exit", from_entry="Long", stop=activeStop, limit=activeTp)
    else
        strategy.exit("Long Exit", from_entry="Long", stop=activeStop)
    if isMisSquareoff
        strategy.close("Long")
    else if stTrend == -1 and emaFast < emaSlow
        strategy.close("Long")

if inShort
    if beTriggerR > 0 and not na(entryPrice) and not na(initRisk) and low <= (entryPrice - initRisk * beTriggerR)
        shortBeStop = math.round((entryPrice - initRisk * beOffsetR) * 100.0) / 100.0
        if na(activeStop) or shortBeStop < activeStop
            activeStop   := shortBeStop
            ratchetStage := math.max(ratchetStage, 1)
    if lock2TrigR > 0 and not na(entryPrice) and not na(initRisk) and low <= (entryPrice - initRisk * lock2TrigR)
        shortL2Stop = math.round((entryPrice - initRisk * lock2OffR) * 100.0) / 100.0
        if na(activeStop) or shortL2Stop < activeStop
            activeStop   := shortL2Stop
            ratchetStage := math.max(ratchetStage, 2)
    if useStTrail and stTrend == -1 and not na(stLine) and (na(activeStop) or stLine < activeStop)
        activeStop := math.round(stLine * 100.0) / 100.0
    if tpR > 0 and not na(activeTp)
        strategy.exit("Short Exit", from_entry="Short", stop=activeStop, limit=activeTp)
    else
        strategy.exit("Short Exit", from_entry="Short", stop=activeStop)
    if isMisSquareoff
        strategy.close("Short")
    else if stTrend == 1 and emaFast > emaSlow
        strategy.close("Short")

// Impulse Trigger: 5m uses Tri-Trigger (ST flip OR EMA cross OR RSI cross); 15m uses ST flip OR RSI cross
freshBullTrigger = use5mProf ? ((stTrend[1] == -1) or (emaFast[1] <= emaSlow[1]) or (rsiVal[1] <= rsiLong)) : ((stTrend[1] == -1) or (rsiVal[1] <= rsiLong))
freshBearTrigger = use5mProf ? ((stTrend[1] == 1)  or (emaFast[1] >= emaSlow[1]) or (rsiVal[1] >= rsiShort)) : ((stTrend[1] == 1)  or (rsiVal[1] >= rsiShort))
adxOk            = (adxMin <= 0.0) or (adxVal >= adxMin)

longCond  = bar_index >= 55 and inEntryWindow and (legTrades < maxLegTrades) and stTrend == 1  and emaFast > emaSlow and close > emaMac and close > intradayVwap and rsiVal > rsiLong  and adxOk and freshBullTrigger
shortCond = bar_index >= 55 and inEntryWindow and (legTrades < maxLegTrades) and stTrend == -1 and emaFast < emaSlow and close < emaMac and close < intradayVwap and rsiVal < rsiShort and adxOk and freshBearTrigger

flatNow = (strategy.position_size == 0) or (inLong and (isMisSquareoff or (stTrend == -1 and emaFast < emaSlow))) or (inShort and (isMisSquareoff or (stTrend == 1 and emaFast > emaSlow)))

bool enteredLongBar  = false
bool enteredShortBar = false

if flatNow and not isMisSquareoff
    if longCond
        entryPrice     := close
        initRisk       := curAtr * slAtrMult
        activeStop     := math.round((entryPrice - initRisk) * 100.0) / 100.0
        activeTp       := tpR > 0 ? (math.round((entryPrice + initRisk * tpR) * 100.0) / 100.0) : na
        ratchetStage   := 0
        legTrades      += 1
        enteredLongBar := true
        strategy.entry("Long", strategy.long)
        if tpR > 0 and not na(activeTp)
            strategy.exit("Long Exit", from_entry="Long", stop=activeStop, limit=activeTp)
        else
            strategy.exit("Long Exit", from_entry="Long", stop=activeStop)
    else if shortCond
        entryPrice      := close
        initRisk        := curAtr * slAtrMult
        activeStop      := math.round((entryPrice + initRisk) * 100.0) / 100.0
        activeTp        := tpR > 0 ? (math.round((entryPrice - initRisk * tpR) * 100.0) / 100.0) : na
        ratchetStage    := 0
        legTrades       += 1
        enteredShortBar := true
        strategy.entry("Short", strategy.short)
        if tpR > 0 and not na(activeTp)
            strategy.exit("Short Exit", from_entry="Short", stop=activeStop, limit=activeTp)
        else
            strategy.exit("Short Exit", from_entry="Short", stop=activeStop)

// ============================================================================
// 5. IMAGE 2 VISUAL CALLOUT ENGINE (BUY CALL / BUY PUT & EXIT PnL BADGES)
// ============================================================================
// Detect newly closed trades and render green/red EXIT PnL pills (exact Image 2 style)
closedCount = strategy.closedtrades
prevClosed  = nz(closedCount[1], 0)

if showCallouts and closedCount > prevClosed
    for idx = prevClosed to closedCount - 1
        exPrice  = strategy.closedtrades.exit_price(idx)
        enPrice  = strategy.closedtrades.entry_price(idx)
        trSize   = strategy.closedtrades.size(idx)
        ptsDiff  = trSize > 0 ? (exPrice - enPrice) : (enPrice - exPrice)
        isWin    = ptsDiff >= 0
        signStr  = isWin ? "+" : ""
        pillClr  = isWin ? #10b981 : #f43f5e
        exitTxt  = "EXIT\\n" + signStr + str.tostring(ptsDiff, "0.0") + " pts"
        wasLong  = trSize > 0
        yExitPos = wasLong ? (high + curAtr * 0.25) : (low - curAtr * 0.25)
        lblStyle = wasLong ? label.style_label_down : label.style_label_up
        label.new(bar_index, yExitPos, exitTxt, xloc=xloc.bar_index, yloc=yloc.price, color=pillClr, textcolor=color.white, style=lblStyle, size=size.small)

// Render Entry Callout Boxes on the entry bar (exact Image 2 style)
if showCallouts and enteredLongBar
    callClr = (entryStyle == "Solid Blue (Image 2 Style)") ? #2563eb : #059669
    callTxt = "BUY CALL\\nEntry: " + str.tostring(entryPrice, "0.00") + "\\nQty: " + str.tostring(displayLots)
    label.new(bar_index, low - curAtr * 0.35, callTxt, xloc=xloc.bar_index, yloc=yloc.price, color=callClr, textcolor=color.white, style=label.style_label_up, size=size.small)

if showCallouts and enteredShortBar
    putClr  = (entryStyle == "Solid Blue (Image 2 Style)") ? #2563eb : #e11d48
    putTxt  = "BUY PUT\\nEntry: " + str.tostring(entryPrice, "0.00") + "\\nQty: " + str.tostring(displayLots)
    label.new(bar_index, high + curAtr * 0.35, putTxt, xloc=xloc.bar_index, yloc=yloc.price, color=putClr, textcolor=color.white, style=label.style_label_down, size=size.small)

// Subtle directional triangles on entry bars
plotshape(enteredLongBar, title="Buy Call Marker", style=shape.triangleup, location=location.belowbar, color=#3b82f6, size=size.tiny)
plotshape(enteredShortBar, title="Buy Put Marker", style=shape.triangledown, location=location.abovebar, color=#f59e0b, size=size.tiny)

// Clean Chart Overlays
plot(showRibbons ? emaFast : na, "Fast EMA", color=color.new(#06b6d4, 55), linewidth=1)
plot(showRibbons ? emaSlow : na, "Slow EMA", color=color.new(#f59e0b, 55), linewidth=1)
plot(showRibbons ? emaMac  : na, "Macro EMA", color=color.new(#818cf8, 60), linewidth=2)
plot(showRibbons ? intradayVwap : na, "Intraday VWAP", color=color.new(#e879f9, 55), linewidth=1, style=plot.style_circles)

stColor = stTrend == 1 ? color.new(#10b981, 25) : color.new(#f43f5e, 25)
plot(showStLine ? stLine : na, "Supertrend Spine", color=stColor, linewidth=2)

// Active Trade Horizontal Level Lines (Image 2 Clean Style)
inTradeNow = strategy.position_size != 0
plot(showTradeLvls and inTradeNow ? entryPrice : na, "Active Entry Price", color=color.new(#60a5fa, 20), linewidth=1, style=plot.style_linebr)
plot(showTradeLvls and inTradeNow ? activeStop : na, "Active Ratchet / Trail Stop", color=color.new(#fbbf24, 0), linewidth=2, style=plot.style_linebr)
plot(showTradeLvls and inTradeNow and tpR > 0 ? activeTp : na, "Active Profit Target", color=color.new(#10b981, 20), linewidth=1, style=plot.style_linebr)

// ============================================================================
// 6. QUANT STUDIO TELEMETRY HUD TABLE
// ============================================================================
var table hud = table.new(position.top_right, 2, 9, bgcolor=color.new(#0e121b, 8), border_color=color.new(#ffffff, 82), border_width=1)

if barstate.islast and showHud
    totTrades = strategy.closedtrades
    wins      = strategy.wintrades
    winRate   = totTrades > 0 ? (wins / totTrades) * 100.0 : 0.0
    pf        = strategy.grossloss != 0 ? math.abs(strategy.grossprofit / strategy.grossloss) : 0.0
    netInr    = strategy.netprofit
    netPts    = netInr / math.max(lotSize, 1)
    maxDdPts  = strategy.max_drawdown / math.max(lotSize, 1)
    profLabel = use5mProf ? "5M SCALPER [AUTO]" : use15mProf ? "15M SWING [AUTO]" : "MANUAL CUSTOM"
    ratchTxt  = ratchetStage == 2 ? " [LOCK +1.1R]" : ratchetStage == 1 ? " [BE LOCK]" : " [INIT SL]"

    table.cell(hud, 0, 0, "👑 APEX SYMPHONY v2", text_color=#60a5fa, text_size=size.small, bgcolor=color.new(#1e293b, 10), text_halign=text.align_left)
    table.cell(hud, 1, 0, profLabel, text_color=#34d399, text_size=size.tiny, bgcolor=color.new(#1e293b, 10), text_halign=text.align_right)

    table.cell(hud, 0, 1, "Active Parameters", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 1, "ST(" + str.tostring(stPeriod) + "," + str.tostring(stMult, "0.0") + ") · EMA(" + str.tostring(emaFastP) + "/" + str.tostring(emaSlowP) + "/" + str.tostring(emaMacP) + ")", text_color=#e2e8f0, text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 2, "Regime · RSI · ADX", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 2, (stTrend == 1 ? "BULL" : "BEAR") + " · RSI " + str.tostring(rsiVal, "0.0") + " · ADX " + str.tostring(adxVal, "0.0"), text_color=(stTrend == 1 ? #10b981 : #f43f5e), text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 3, "Active Stop / Ratchet", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 3, inTradeNow ? (str.tostring(activeStop, "0.00") + ratchTxt) : "FLAT", text_color=#fbbf24, text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 4, "Net Profit (Nifty Pts)", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 4, (netPts >= 0 ? "+" : "") + str.tostring(netPts, "0.00") + " pts", text_color=(netPts >= 0 ? #10b981 : #f43f5e), text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 5, "Net Profit (1 Lot INR)", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 5, (netInr >= 0 ? "+INR " : "-INR ") + str.tostring(math.abs(netInr), "0"), text_color=(netInr >= 0 ? #10b981 : #f43f5e), text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 6, "Win Rate (Trades)", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 6, str.tostring(winRate, "0.0") + "% (" + str.tostring(totTrades) + ")", text_color=#f8fafc, text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 7, "Profit Factor", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 7, str.tostring(pf, "0.00"), text_color=(pf >= 1.5 ? #10b981 : #f8fafc), text_size=size.tiny, text_halign=text.align_right)

    table.cell(hud, 0, 8, "Max Drawdown", text_color=#94a3b8, text_size=size.tiny, text_halign=text.align_left)
    table.cell(hud, 1, 8, "-" + str.tostring(maxDdPts, "0.00") + " pts", text_color=#f43f5e, text_size=size.tiny, text_halign=text.align_right)"""
    },
    "pine_adaptive_dual_orb": {
        "id": "pine_adaptive_dual_orb",
        "name": "⚡ Adaptive Dual ORB + Supertrend + VWAP [Intraday]",
        "category": "Institutional",
        "code": """//@version=5
strategy("Adaptive Dual ORB + Supertrend + VWAP [Intraday]", overlay=true, initial_capital=100000, default_qty_type=strategy.fixed, default_qty_value=1, currency=currency.INR)

target_r     = input.float(1.0, title="Profit Target (R-Multiple)", step=0.1)
sl_atr_mult  = input.float(1.5, title="Stop Loss (ATR Multiplier)", step=0.1)
atr_period   = input.int(14, title="ATR Period")
st_period    = input.int(10, title="Supertrend ATR Period")
st_mult      = input.float(3.0, title="Supertrend Multiplier", step=0.5)

orb_session  = input.session("0915-0930", title="Opening Range Period (IST)")
trade_window = input.session("0930-1345", title="Allowed Entry Window (IST)")
exit_time    = input.session("1515-1520", title="Mandatory MIS Auto-Exit (IST)")

atr_val = ta.atr(atr_period)
min_atr = math.max(atr_val, 15.0)
vwap_val = ta.vwap(hlc3)
[st_value, st_direction] = ta.supertrend(st_mult, st_period)
is_st_bullish = (st_direction == -1)
is_st_bearish = (st_direction == 1)

var float or_high = na
var float or_low  = na
var bool  or_set  = false
is_new_day = ta.change(time("D")) != 0
in_orb_window = not na(time(timeframe.period, orb_session + ":1234567"))
in_entry_window = not na(time(timeframe.period, trade_window + ":1234567"))
is_exit_time = not na(time(timeframe.period, exit_time + ":1234567"))

if is_new_day
    or_high := na
    or_low  := na
    or_set  := false

if in_orb_window
    or_high := na(or_high) ? high : math.max(or_high, high)
    or_low  := na(or_low)  ? low  : math.min(or_low, low)
else
    if not na(or_high) and not na(or_low)
        or_set := true

in_pos = strategy.position_size != 0
long_condition = (not in_pos) and or_set and in_entry_window and (close > or_high) and (close > vwap_val) and is_st_bullish
short_condition = (not in_pos) and or_set and in_entry_window and (close < or_low) and (close < vwap_val) and is_st_bearish

if long_condition
    sl_dist = min_atr * sl_atr_mult
    strategy.entry("ORB_Long", strategy.long)
    strategy.exit("Exit_Long", from_entry="ORB_Long", stop=close - sl_dist, limit=close + (sl_dist * target_r))

if short_condition
    sl_dist = min_atr * sl_atr_mult
    strategy.entry("ORB_Short", strategy.short)
    strategy.exit("Exit_Short", from_entry="ORB_Short", stop=close + sl_dist, limit=close - (sl_dist * target_r))

if is_exit_time and in_pos
    strategy.close_all(comment="MIS_Auto_Squareoff")
"""
    },
    "pine_inside_candle": {
        "id": "pine_inside_candle",
        "name": "🕯️ Inside Candle + VWAP + 3-EMA Momentum Pulse",
        "category": "Institutional",
        "code": """//@version=5
strategy("Inside Candle + VWAP + 3-EMA Momentum Pulse", overlay=true, initial_capital=100000)

target_r     = input.float(1.0, title="Profit Target (R-Multiple)", step=0.1)
sl_atr_mult  = input.float(1.1, title="Stop Loss (ATR Multiplier)", step=0.1)
min_mom_atr  = input.float(0.6, title="Mother Candle Momentum (ATR)", step=0.1)
fast_ema_p   = input.int(9, title="Fast EMA Period")
slow_ema_p   = input.int(21, title="Slow EMA Period")
st_period    = input.int(10, title="Supertrend ATR Period")
st_mult      = input.float(3.0, title="Supertrend Multiplier", step=0.5)
trade_window = input.session("0925-1430", title="Allowed Entry Window (IST)")
exit_time    = input.session("1515-1520", title="Mandatory MIS Auto-Exit (IST)")

atr_val = ta.atr(14)
vwap_val = ta.vwap(hlc3)
ema_fast = ta.ema(close, fast_ema_p)
ema_slow = ta.ema(close, slow_ema_p)
[st_value, st_direction] = ta.supertrend(st_mult, st_period)

is_inside = (high[1] <= high[2]) and (low[1] >= low[2])
mother_range = high[2] - low[2]
has_momentum = mother_range >= (atr_val * min_mom_atr)

in_pos = strategy.position_size != 0
in_entry = not na(time(timeframe.period, trade_window + ":1234567"))
is_exit = not na(time(timeframe.period, exit_time + ":1234567"))

long_cond = not in_pos and in_entry and is_inside and has_momentum and (ema_fast > ema_slow) and (close > vwap_val) and (st_direction == -1) and (close > high[2])
short_cond = not in_pos and in_entry and is_inside and has_momentum and (ema_fast < ema_slow) and (close < vwap_val) and (st_direction == 1) and (close < low[2])

if long_cond
    sl_dist = math.max(atr_val * sl_atr_mult, 12.0)
    strategy.entry("IC_Long", strategy.long)
    strategy.exit("Exit_Long", from_entry="IC_Long", stop=close - sl_dist, limit=close + (sl_dist * target_r))

if short_cond
    sl_dist = math.max(atr_val * sl_atr_mult, 12.0)
    strategy.entry("IC_Short", strategy.short)
    strategy.exit("Exit_Short", from_entry="IC_Short", stop=close + sl_dist, limit=close - (sl_dist * target_r))

if is_exit and in_pos
    strategy.close_all(comment="MIS_Auto_Squareoff")
"""
    },
    "pine_triple_momentum": {
        "id": "pine_triple_momentum",
        "name": "🚀 Triple Momentum Fusion (Donchian + 3-EMA Ribbon + VWAP)",
        "category": "Institutional",
        "code": """//@version=5
strategy("Triple Momentum Fusion [Intraday]", overlay=true, initial_capital=100000)

target_r     = input.float(1.0, title="Profit Target (R-Multiple)", step=0.1)
sl_atr_mult  = input.float(1.8, title="Stop Loss (ATR Multiplier)", step=0.1)
donchian_p   = input.int(15, title="Donchian Channel Lookback (Bars)")
fast_ema_p   = input.int(9, title="Fast EMA Period")
mid_ema_p    = input.int(21, title="Medium EMA Period")
slow_ema_p   = input.int(50, title="Slow EMA Period")
st_period    = input.int(10, title="Supertrend ATR Period")
st_mult      = input.float(3.0, title="Supertrend Multiplier", step=0.5)
trade_window = input.session("0935-1400", title="Allowed Entry Window (IST)")
exit_time    = input.session("1515-1520", title="Mandatory MIS Auto-Exit (IST)")

ch_high = ta.highest(high[1], donchian_p)
ch_low  = ta.lowest(low[1], donchian_p)
vwap_val = ta.vwap(hlc3)
atr_val  = ta.atr(14)
e9  = ta.ema(close, fast_ema_p)
e21 = ta.ema(close, mid_ema_p)
e50 = ta.ema(close, slow_ema_p)
[st_value, st_direction] = ta.supertrend(st_mult, st_period)

in_pos = strategy.position_size != 0
in_entry = not na(time(timeframe.period, trade_window + ":1234567"))
is_exit  = not na(time(timeframe.period, exit_time + ":1234567"))

long_cond = not in_pos and in_entry and (close > ch_high) and (st_direction == -1) and (e9 > e21) and (close > e50) and (close > vwap_val)
short_cond = not in_pos and in_entry and (close < ch_low) and (st_direction == 1) and (e9 < e21) and (close < e50) and (close < vwap_val)

if long_cond
    sl_dist = math.max(atr_val * sl_atr_mult, 15.0)
    strategy.entry("TMF_Long", strategy.long)
    strategy.exit("Exit_Long", from_entry="TMF_Long", stop=close - sl_dist, limit=close + (sl_dist * target_r))

if short_cond
    sl_dist = math.max(atr_val * sl_atr_mult, 15.0)
    strategy.entry("TMF_Short", strategy.short)
    strategy.exit("Exit_Short", from_entry="TMF_Short", stop=close + sl_dist, limit=close - (sl_dist * target_r))

if is_exit and in_pos
    strategy.close_all(comment="MIS_Auto_Squareoff")
"""
    }
}

# -------------------------------------------------------------
# 3. STORAGE & PERSISTENCE
# -------------------------------------------------------------
def load_all_pine_strategies():
    strategies = dict(DEFAULT_PINE_TEMPLATES)
    if os.path.exists(PINE_STORAGE_FILE):
        try:
            with open(PINE_STORAGE_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
                for k, v in custom.items():
                    strategies[k] = v
        except Exception as e:
            print(f"[PineStorage] Error loading custom strategies: {e}")
    return strategies

def save_custom_pine_strategy(code, custom_id=None, name=None):
    parsed = parse_pine_script(code)
    strat_name = name or parsed.get("name") or "Custom Pine Strategy"
    
    if not custom_id:
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '', strat_name.lower().replace(" ", "_"))
        custom_id = f"pine_custom_{clean_name}_{int(datetime.datetime.now().timestamp())}"
        
    entry = {
        "id": custom_id,
        "name": strat_name,
        "category": "User Pine Scripts",
        "code": code,
        "created_at": datetime.datetime.now().isoformat()
    }
    
    custom = {}
    if os.path.exists(PINE_STORAGE_FILE):
        try:
            with open(PINE_STORAGE_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
        except Exception:
            custom = {}
            
    custom[custom_id] = entry
    with open(PINE_STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(custom, f, indent=2)
        
    return entry

def delete_custom_pine_strategy(custom_id):
    if not os.path.exists(PINE_STORAGE_FILE):
        return False
    try:
        with open(PINE_STORAGE_FILE, "r", encoding="utf-8") as f:
            custom = json.load(f)
        if custom_id in custom:
            del custom[custom_id]
            with open(PINE_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(custom, f, indent=2)
            return True
    except Exception as e:
        print(f"[PineStorage] Error deleting: {e}")
    return False

# -------------------------------------------------------------
# 4. FULL EXECUTION ENGINE (Apex Symphony v2, Multi-Strategy & Fallback)
# -------------------------------------------------------------
def run_pine_strategy(candles, pine_code, user_params=None, symbol="^NSEI"):
    if user_params is None:
        user_params = {}
        
    parsed = parse_pine_script(pine_code)
    active_params = {}
    for inp in parsed["inputs"]:
        var_name = inp["var"]
        if var_name in user_params:
            try:
                if inp["type"] == "float": active_params[var_name] = float(user_params[var_name])
                elif inp["type"] == "int": active_params[var_name] = int(user_params[var_name])
                elif inp["type"] == "bool":
                    v = str(user_params[var_name]).lower()
                    active_params[var_name] = v in ("true", "1", "yes")
                else: active_params[var_name] = user_params[var_name]
            except:
                active_params[var_name] = inp["default"]
        else:
            active_params[var_name] = inp["default"]

    n = len(candles)
    if n == 0:
        return {"trades": [], "strategy_meta": parsed, "parsed_inputs": parsed["inputs"], "active_params": active_params, "indicators": {}}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    opens = [c["open"] for c in candles]
    times = [c["time"] for c in candles]

    # Math Helpers: RMA & EMA
    def rma(vals, p):
        res = [0.0] * n
        if n < p: return res
        cur = sum(vals[:p]) / p
        res[p-1] = cur
        for i in range(p, n):
            cur = (cur * (p - 1) + vals[i]) / p
            res[i] = cur
        return res

    def ema(vals, p):
        res = [0.0] * n
        if n < p: return res
        k = 2.0 / (p + 1.0)
        cur = sum(vals[:p]) / p
        res[p-1] = cur
        for i in range(p, n):
            cur = (vals[i] * k) + (cur * (1.0 - k))
            res[i] = cur
        return res

    # True Range
    tr = [highs[0] - lows[0]]
    for i in range(1, n):
        t = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr.append(t)

    # Intraday VWAP (reset each day)
    vwap = [0.0] * n
    cur_d = None
    c_sum = 0.0
    c_cnt = 0
    for i in range(n):
        dt = datetime.datetime.fromtimestamp(times[i], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
        d_str = dt.strftime("%Y-%m-%d")
        if d_str != cur_d:
            cur_d = d_str
            c_sum = (highs[i] + lows[i] + closes[i]) / 3.0
            c_cnt = 1
        else:
            c_sum += (highs[i] + lows[i] + closes[i]) / 3.0
            c_cnt += 1
        vwap[i] = c_sum / c_cnt

    code_lower = pine_code.lower()
    is_apex = "apex" in code_lower or "symphony" in code_lower or "freshbulltrigger" in code_lower or "profilemode" in code_lower

    if is_apex:
        # Determine 5m vs 15m profile
        prof_mode = str(active_params.get("profileMode", "Auto (5m & 15m+ Optimized)"))
        # Determine 5m vs 15m profile dynamically
        tf_param = str(active_params.get("timeframe", "")).lower().strip()
        if tf_param == "15m":
            is_5m = False
        elif tf_param in ("5m", "1m", "3m"):
            is_5m = True
        elif n >= 2:
            diffs = [candles[j]["time"] - candles[j-1]["time"] for j in range(1, min(15, n))]
            min_diff = min(diffs) if diffs else 300
            is_5m = (min_diff <= 360) # <= 6 min candle interval -> 5m profile; > 6 min -> 15m profile
        else:
            is_5m = False

        use_5m_prof = (prof_mode == "Force 5m Scalper Profile") or (prof_mode == "Auto (5m & 15m+ Optimized)" and is_5m)
        use_15m_prof = (prof_mode == "Force 15m Swing Profile") or (prof_mode == "Auto (5m & 15m+ Optimized)" and not is_5m)

        if use_5m_prof:
            st_p = 14
            st_m = 3.5
            fast_p = 9
            slow_p = 21
            mac_p = 50
            rsi_long = 58.0
            rsi_short = 42.0
            adx_min = 16.0
            max_leg = 2
            sl_atr_mult = 1.8
            be_trig = 1.0
            be_off = 0.25
            lock2_trig = 2.0
            lock2_off = 1.10
            tp_r = 3.5
        elif use_15m_prof:
            st_p = 10
            st_m = 3.0
            fast_p = 8
            slow_p = 21
            mac_p = 55
            rsi_long = 52.0
            rsi_short = 48.0
            adx_min = 16.0
            max_leg = 2
            sl_atr_mult = 1.6
            be_trig = 1.1
            be_off = 0.20
            lock2_trig = 2.2
            lock2_off = 1.20
            tp_r = 4.5
        else:
            st_p = int(active_params.get("stPeriodIn", active_params.get("stPeriod", 14)))
            st_m = float(active_params.get("stMultIn", active_params.get("stMult", 3.5)))
            fast_p = int(active_params.get("emaFastIn", active_params.get("emaFastP", 9)))
            slow_p = int(active_params.get("emaSlowIn", active_params.get("emaSlowP", 21)))
            mac_p = int(active_params.get("emaMacIn", active_params.get("emaMacP", 50)))
            rsi_long = float(active_params.get("rsiLongIn", active_params.get("rsiLong", 58.0)))
            rsi_short = float(active_params.get("rsiShortIn", active_params.get("rsiShort", 42.0)))
            adx_min = float(active_params.get("adxMinIn", active_params.get("adxMin", 16.0)))
            max_leg = int(active_params.get("maxLegIn", active_params.get("maxLegTrades", 2)))
            sl_atr_mult = float(active_params.get("slAtrIn", active_params.get("slAtrMult", 1.8)))
            be_trig = float(active_params.get("beTrigIn", active_params.get("beTriggerR", 1.0)))
            be_off = float(active_params.get("beOffIn", active_params.get("beOffsetR", 0.25)))
            lock2_trig = float(active_params.get("lock2TrigIn", active_params.get("lock2TrigR", 2.0)))
            lock2_off = float(active_params.get("lock2OffIn", active_params.get("lock2OffR", 1.10)))
            tp_r = float(active_params.get("tpRIn", active_params.get("tpR", 3.5)))

        min_atr_floor = float(active_params.get("minAtrFloor", 15.0))
        use_st_trail = str(active_params.get("useStTrail", "true")).lower() in ("true", "1", "yes")
        intraday_only = str(active_params.get("intradayOnly", "false")).lower() in ("true", "1", "yes")
        rsi_len = int(active_params.get("rsiLen", 14))
        adx_len = int(active_params.get("adxLen", 14))

        # 1. EMAs
        ema_fast = ema(closes, fast_p)
        ema_slow = ema(closes, slow_p)
        ema_mac = ema(closes, mac_p)

        # 2. RSI with Wilder RMA
        deltas = [0.0] + [closes[i] - closes[i-1] for i in range(1, n)]
        gains = [max(d, 0.0) for d in deltas]
        losses = [max(-d, 0.0) for d in deltas]
        avg_gain = rma(gains, rsi_len)
        avg_loss = rma(losses, rsi_len)
        rsi_vals = [50.0] * n
        for i in range(rsi_len, n):
            if avg_loss[i] == 0:
                rsi_vals[i] = 100.0
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi_vals[i] = 100.0 - (100.0 / (1.0 + rs))

        # 3. Wilder ADX
        plus_dm = [0.0] * n
        minus_dm = [0.0] * n
        for i in range(1, n):
            up = highs[i] - highs[i-1]
            dn = lows[i-1] - lows[i]
            plus_dm[i] = up if (up > dn and up > 0) else 0.0
            minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        
        adx_atr = rma(tr, adx_len)
        plus_di_rma = rma(plus_dm, adx_len)
        minus_di_rma = rma(minus_dm, adx_len)
        dx_vals = [0.0] * n
        for i in range(adx_len, n):
            atr_val = max(adx_atr[i], 0.0001)
            p_di = 100.0 * plus_di_rma[i] / atr_val
            m_di = 100.0 * minus_di_rma[i] / atr_val
            di_sum = p_di + m_di
            dx_vals[i] = (100.0 * abs(p_di - m_di) / di_sum) if di_sum > 0 else 0.0
        adx_vals = rma(dx_vals, adx_len)

        # 4. Supertrend
        atr_vals = rma(tr, 14)
        st_atr = rma(tr, st_p)
        st_u = [0.0] * n
        st_l = [0.0] * n
        st_tr = [1] * n
        st_ln = [0.0] * n
        for i in range(n):
            hl2 = (highs[i] + lows[i]) / 2.0
            bu = hl2 + (st_m * st_atr[i])
            bl = hl2 - (st_m * st_atr[i])
            if i < st_p:
                st_u[i], st_l[i], st_tr[i], st_ln[i] = bu, bl, 1, bl
                continue
            st_u[i] = bu if (bu < st_u[i-1] or closes[i-1] > st_u[i-1]) else st_u[i-1]
            st_l[i] = bl if (bl > st_l[i-1] or closes[i-1] < st_l[i-1]) else st_l[i-1]
            if st_tr[i-1] == 1:
                if closes[i] < st_l[i]:
                    st_tr[i] = -1
                    st_ln[i] = st_u[i]
                else:
                    st_tr[i] = 1
                    st_ln[i] = st_l[i]
            else:
                if closes[i] > st_u[i]:
                    st_tr[i] = 1
                    st_ln[i] = st_l[i]
                else:
                    st_tr[i] = -1
                    st_ln[i] = st_u[i]

        apex_trades = []
        in_pos = False
        side = None
        entry_p = 0.0
        entry_idx = 0
        init_risk = 0.0
        active_stop = 0.0
        active_tp = 0.0
        ratchet_stage = 0
        leg_trades = 0

        for i in range(55, n):
            c = candles[i]
            dt = datetime.datetime.fromtimestamp(times[i], datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
            t_int = dt.hour * 100 + dt.minute
            in_entry_win = not intraday_only or (920 <= t_int <= 1430)
            is_mis_exit = intraday_only and (t_int >= 1515)

            if st_tr[i] != st_tr[i-1]:
                leg_trades = 0

            if in_pos:
                bars_held = i - entry_idx
                if is_mis_exit:
                    pnl = round((closes[i] - entry_p) if side == "BUY" else (entry_p - closes[i]), 2)
                    apex_trades.append({
                        "entry_time": times[entry_idx], "entry_price": entry_p,
                        "exit_time": times[i], "exit_price": closes[i],
                        "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                        "reason": "MIS_SQUAREOFF", "side": side, "bars_held": bars_held
                    })
                    in_pos = False
                    continue

                # Stage 1 Ratchet
                if be_trig > 0 and ratchet_stage < 1:
                    if side == "BUY" and highs[i] >= (entry_p + init_risk * be_trig):
                        long_be = round(entry_p + init_risk * be_off, 2)
                        if long_be > active_stop:
                            active_stop = long_be
                            ratchet_stage = 1
                    elif side == "SELL" and lows[i] <= (entry_p - init_risk * be_trig):
                        short_be = round(entry_p - init_risk * be_off, 2)
                        if short_be < active_stop:
                            active_stop = short_be
                            ratchet_stage = 1

                # Stage 2 Ratchet
                if lock2_trig > 0 and ratchet_stage < 2:
                    if side == "BUY" and highs[i] >= (entry_p + init_risk * lock2_trig):
                        long_l2 = round(entry_p + init_risk * lock2_off, 2)
                        if long_l2 > active_stop:
                            active_stop = long_l2
                            ratchet_stage = 2
                    elif side == "SELL" and lows[i] <= (entry_p - init_risk * lock2_trig):
                        short_l2 = round(entry_p - init_risk * lock2_off, 2)
                        if short_l2 < active_stop:
                            active_stop = short_l2
                            ratchet_stage = 2

                # Supertrend Trail
                if use_st_trail:
                    if side == "BUY" and st_tr[i] == 1 and st_ln[i] > active_stop:
                        active_stop = round(st_ln[i], 2)
                    elif side == "SELL" and st_tr[i] == -1 and st_ln[i] < active_stop:
                        active_stop = round(st_ln[i], 2)

                # Stop or Target Exits
                if side == "BUY":
                    if lows[i] <= active_stop:
                        pnl = round(active_stop - entry_p, 2)
                        reason = "LOCK2_STOP" if ratchet_stage == 2 else ("BE_STOP" if ratchet_stage == 1 else "STOP_LOSS")
                        apex_trades.append({
                            "entry_time": times[entry_idx], "entry_price": entry_p,
                            "exit_time": times[i], "exit_price": active_stop,
                            "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                            "reason": reason, "side": "BUY", "bars_held": bars_held
                        })
                        in_pos = False
                        continue
                    elif tp_r > 0 and highs[i] >= active_tp:
                        pnl = round(active_tp - entry_p, 2)
                        apex_trades.append({
                            "entry_time": times[entry_idx], "entry_price": entry_p,
                            "exit_time": times[i], "exit_price": active_tp,
                            "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                            "reason": "TAKE_PROFIT", "side": "BUY", "bars_held": bars_held
                        })
                        in_pos = False
                        continue
                    elif st_tr[i] == -1 and ema_fast[i] < ema_slow[i]:
                        pnl = round(closes[i] - entry_p, 2)
                        apex_trades.append({
                            "entry_time": times[entry_idx], "entry_price": entry_p,
                            "exit_time": times[i], "exit_price": closes[i],
                            "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                            "reason": "REVERSAL", "side": "BUY", "bars_held": bars_held
                        })
                        in_pos = False
                        continue

                elif side == "SELL":
                    if highs[i] >= active_stop:
                        pnl = round(entry_p - active_stop, 2)
                        reason = "LOCK2_STOP" if ratchet_stage == 2 else ("BE_STOP" if ratchet_stage == 1 else "STOP_LOSS")
                        apex_trades.append({
                            "entry_time": times[entry_idx], "entry_price": entry_p,
                            "exit_time": times[i], "exit_price": active_stop,
                            "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                            "reason": reason, "side": "SELL", "bars_held": bars_held
                        })
                        in_pos = False
                        continue
                    elif tp_r > 0 and lows[i] <= active_tp:
                        pnl = round(entry_p - active_tp, 2)
                        apex_trades.append({
                            "entry_time": times[entry_idx], "entry_price": entry_p,
                            "exit_time": times[i], "exit_price": active_tp,
                            "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                            "reason": "TAKE_PROFIT", "side": "SELL", "bars_held": bars_held
                        })
                        in_pos = False
                        continue
                    elif st_tr[i] == 1 and ema_fast[i] > ema_slow[i]:
                        pnl = round(entry_p - closes[i], 2)
                        apex_trades.append({
                            "entry_time": times[entry_idx], "entry_price": entry_p,
                            "exit_time": times[i], "exit_price": closes[i],
                            "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                            "reason": "REVERSAL", "side": "SELL", "bars_held": bars_held
                        })
                        in_pos = False
                        continue

            # Check Entry
            if not in_pos and in_entry_win and not is_mis_exit:
                if use_5m_prof:
                    fresh_bull = (st_tr[i-1] == -1) or (ema_fast[i-1] <= ema_slow[i-1]) or (rsi_vals[i-1] <= rsi_long)
                    fresh_bear = (st_tr[i-1] == 1) or (ema_fast[i-1] >= ema_slow[i-1]) or (rsi_vals[i-1] >= rsi_short)
                else:
                    fresh_bull = (st_tr[i-1] == -1) or (rsi_vals[i-1] <= rsi_long)
                    fresh_bear = (st_tr[i-1] == 1) or (rsi_vals[i-1] >= rsi_short)
                adx_ok = (adx_min <= 0.0) or (adx_vals[i] >= adx_min)
                cur_atr = max(atr_vals[i], min_atr_floor)

                long_cond = (leg_trades < max_leg and st_tr[i] == 1 and ema_fast[i] > ema_slow[i] and 
                             closes[i] > ema_mac[i] and closes[i] > vwap[i] and rsi_vals[i] > rsi_long and 
                             adx_ok and fresh_bull)
                short_cond = (leg_trades < max_leg and st_tr[i] == -1 and ema_fast[i] < ema_slow[i] and 
                              closes[i] < ema_mac[i] and closes[i] < vwap[i] and rsi_vals[i] < rsi_short and 
                              adx_ok and fresh_bear)

                if long_cond:
                    in_pos = True
                    side = "BUY"
                    entry_p = closes[i]
                    entry_idx = i
                    init_risk = cur_atr * sl_atr_mult
                    active_stop = round(entry_p - init_risk, 2)
                    active_tp = round(entry_p + init_risk * tp_r, 2) if tp_r > 0 else 0.0
                    ratchet_stage = 0
                    leg_trades += 1
                elif short_cond:
                    in_pos = True
                    side = "SELL"
                    entry_p = closes[i]
                    entry_idx = i
                    init_risk = cur_atr * sl_atr_mult
                    active_stop = round(entry_p + init_risk, 2)
                    active_tp = round(entry_p - init_risk * tp_r, 2) if tp_r > 0 else 0.0
                    ratchet_stage = 0
                    leg_trades += 1

        indicators = {
            "supertrend": [{"time": times[i], "value": round(st_ln[i], 2), "trend": st_tr[i]} for i in range(n)],
            "ema_fast": [{"time": times[i], "value": round(ema_fast[i], 2)} for i in range(n)],
            "ema_slow": [{"time": times[i], "value": round(ema_slow[i], 2)} for i in range(n)],
            "ema_mac": [{"time": times[i], "value": round(ema_mac[i], 2)} for i in range(n)],
            "vwap": [{"time": times[i], "value": round(vwap[i], 2)} for i in range(n)]
        }

        return {
            "trades": apex_trades,
            "strategy_meta": parsed,
            "parsed_inputs": parsed["inputs"],
            "active_params": active_params,
            "indicators": indicators
        }

    # Fallback to Generic / Moving Average Cross / Breakout
    generic_trades = []
    # Generic simple simulation for other scripts
    e_fast = ema(closes, 9)
    e_slow = ema(closes, 21)
    in_pos = False
    side = None
    entry_p = 0.0
    entry_idx = 0

    for i in range(25, n):
        if in_pos:
            bars_held = i - entry_idx
            if side == "BUY" and e_fast[i] < e_slow[i]:
                pnl = round(closes[i] - entry_p, 2)
                generic_trades.append({
                    "entry_time": times[entry_idx], "entry_price": entry_p,
                    "exit_time": times[i], "exit_price": closes[i],
                    "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                    "reason": "CROSS_EXIT", "side": "BUY", "bars_held": bars_held
                })
                in_pos = False
            elif side == "SELL" and e_fast[i] > e_slow[i]:
                pnl = round(entry_p - closes[i], 2)
                generic_trades.append({
                    "entry_time": times[entry_idx], "entry_price": entry_p,
                    "exit_time": times[i], "exit_price": closes[i],
                    "pnl": pnl, "pnl_pct": round(pnl / entry_p * 100.0, 2),
                    "reason": "CROSS_EXIT", "side": "SELL", "bars_held": bars_held
                })
                in_pos = False
        else:
            if e_fast[i] > e_slow[i] and e_fast[i-1] <= e_slow[i-1]:
                in_pos = True
                side = "BUY"
                entry_p = closes[i]
                entry_idx = i
            elif e_fast[i] < e_slow[i] and e_fast[i-1] >= e_slow[i-1]:
                in_pos = True
                side = "SELL"
                entry_p = closes[i]
                entry_idx = i

    return {
        "trades": generic_trades,
        "strategy_meta": parsed,
        "parsed_inputs": parsed["inputs"],
        "active_params": active_params,
        "indicators": {}
    }
