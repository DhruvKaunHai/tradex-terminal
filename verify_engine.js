const fs = require('fs');
const vm = require('vm');

async function testEngineHtml() {
  const html = fs.readFileSync('C:\\Users\\hi\\OneDrive\\Desktop\\Trading Host\\tradex_nse_backtest_engine.html', 'utf8');

  // Verify badge in brand-section
  if (!html.includes('<span class="brand-name">TradeX</span>\n      </div>\n      <div id="live-market-badge"')) {
    console.error('FAIL: live-market-badge not placed properly in brand-section');
  } else {
    console.log('PASS: live-market-badge is inside brand-section');
  }

  // Verify old badge removed from controls-strip
  const tfGroupIdx = html.indexOf('id="tf-group"');
  const fxBtnIdx = html.indexOf('id="btn-fx-indicators"');
  const between = html.substring(tfGroupIdx, fxBtnIdx);
  if (between.includes('live-market-badge')) {
    console.error('FAIL: old badge still between tf-group and fx-indicators');
  } else {
    console.log('PASS: controls-strip is clean and uncluttered');
  }

  // Fetch candles
  const candlesRes = await fetch('http://127.0.0.1:8080/api/candles?symbol=%5ENSEI&tf=5m&year=2026');
  const { candles } = await candlesRes.json();
  console.log('Loaded candles:', candles.length);

  // Extract script
  const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!scriptMatch) {
    console.error('No script found');
    process.exit(1);
  }

  const scriptContent = scriptMatch[1];
  const sandbox = {
    console,
    currentTimeframe: '5m',
    currentPeriodFilter: '2026',
    stratParams: {},
    Math, Map, Array, Object, parseFloat, parseInt, isNaN, String, Boolean, Date
  };
  vm.createContext(sandbox);

  function extractFn(name) {
    const idx = scriptContent.indexOf('function ' + name);
    if (idx === -1) return '';
    let openBraces = 0, foundFirst = false, end = idx;
    for (let i = idx; i < scriptContent.length; i++) {
      if (scriptContent[i] === '{') { openBraces++; foundFirst = true; }
      else if (scriptContent[i] === '}') {
        openBraces--;
        if (foundFirst && openBraces === 0) { end = i + 1; break; }
      }
    }
    return scriptContent.substring(idx, end);
  }

  const fns = ['getIstInfo', 'jsCalcSupertrend', 'jsCalcEma', 'jsCalcRsi', 'jsCalcAtr', 'jsCalcIntradayVwap', 'runStrategyClient'];
  for (const fn of fns) {
    const code = extractFn(fn);
    vm.runInContext(code, sandbox);
  }

  sandbox.candles = candles;

  // 1. Test apex_symphony_v2
  const resV2 = vm.runInContext("runStrategyClient(candles, 'apex_symphony_v2', {}, '^NSEI')", sandbox);
  console.log('apex_symphony_v2 result:', {
    total_trades: resV2.total_trades,
    net_pnl_pts: resV2.net_pnl_pts,
    win_rate: resV2.win_rate,
    profit_factor: resV2.profit_factor,
    meta_name: resV2.strategy_meta ? resV2.strategy_meta.name : 'NONE'
  });

  // 2. Test apex_institutional_ribbon
  const resRibbon = vm.runInContext("runStrategyClient(candles, 'apex_institutional_ribbon', {}, '^NSEI')", sandbox);
  console.log('apex_institutional_ribbon result:', {
    total_trades: resRibbon.total_trades,
    net_pnl_pts: resRibbon.net_pnl_pts,
    win_rate: resRibbon.win_rate,
    profit_factor: resRibbon.profit_factor,
    meta_name: resRibbon.strategy_meta ? resRibbon.strategy_meta.name : 'NONE'
  });
}

testEngineHtml();
