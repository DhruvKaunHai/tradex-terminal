with open(r'C:\Users\hi\OneDrive\Desktop\Trading Host\tradex_nse_backtest_engine.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Look for the junction between apex_institutional_ribbon and quantum_orb_momentum
target = '''            } else if (bearRibbon && ribbonExpanding && cmfShort && volSpreadOk && adxShortOk && breakoutShort) {
              inPos = true; posSide = "SELL"; entryC = c; entryP = c.close; entryIdx = i;
              initRisk = Math.min(80.0, Math.max(12.0, (e55[i] - entryP) + curAtr * 0.5));
              sl = Math.round((entryP + initRisk) * 100) / 100;
              tp = Math.round((entryP - initRisk * 3.5) * 100) / 100;
              trailed21 = false;
            }
          }
        }
      }
      } else if (strategyType === "quantum_orb_momentum") {'''

replacement = '''            } else if (bearRibbon && ribbonExpanding && cmfShort && volSpreadOk && adxShortOk && breakoutShort) {
              inPos = true; posSide = "SELL"; entryC = c; entryP = c.close; entryIdx = i;
              initRisk = Math.min(80.0, Math.max(12.0, (e55[i] - entryP) + curAtr * 0.5));
              sl = Math.round((entryP + initRisk) * 100) / 100;
              tp = Math.round((entryP - initRisk * 3.5) * 100) / 100;
              trailed21 = false;
            }
          }
        }
      } else if (strategyType === "quantum_orb_momentum") {'''

if target in text:
    print('Found double brace junction! Fixing...')
    text = text.replace(target, replacement)
    with open(r'C:\Users\hi\OneDrive\Desktop\Trading Host\tradex_nse_backtest_engine.html', 'w', encoding='utf-8') as f:
        f.write(text)
    with open(r'C:\Users\hi\OneDrive\Desktop\tradex_nse_backtest_engine.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Fixed both files!')
else:
    print('Target junction not matched directly. Checking context...')
    idx = text.find('quantum_orb_momentum')
    print(text[idx-100:idx+50])
