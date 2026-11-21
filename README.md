# BTC, ETH, SOL & BNB Fib Top Tracker

The Claude artifact "BTC & ETH Fib Top Tracker" (BTC Daily, BTC 4H, ETH Daily, ETH 4H), rebuilt on GitHub and shown on Cloudflare, plus SOL and BNB (Daily and 4H, added 14 Nov 2026 with the same engine, rules and layout).
Statistical projection, not financial advice. Spot only.

- **Data**: Binance spot BTCUSDT, ETHUSDT, SOLUSDT and BNBUSDT, 1D and 4H, from the shared repo `mbzazad-max/market-data` (your Binance upload), closed candles only.
  These are the same candles as your Google Drive files `BTCUSDT_D.xlsx`, `BTCUSDT_4H.xlsx`, `ETHUSDT_D.xlsx`, `ETHUSDT_4H.xlsx` (checked candle by candle on 14 Nov 2026: 0 differences).
  No TradingView or other calls: nothing new is fetched for this dashboard.
- **Logic**: the artifact's own engine, unchanged: `engine/fib_top_engine.py` and `engine/export_dash.py` (copied from `claude/fibtop/` in the Trading project, checked against `reference/ENGINE_SHA256SUMS` on every run).
  Zigzag swings (daily 10%, 4H 5%), bullish ABC, target = C + median extension × (B − A) per trend regime, zone = middle half, forecast log, early-rejection watch/warning, zone confluence, low strength badges.
- **Forecast logs**: `state/forecast_log*.json`, BTC and ETH continued from the artifact's logs; SOL and BNB start empty on 14 Nov 2026. Each build adds to them exactly as the artifact refresh did.
- **Page**: `public/index.html` = the artifact host's head + d3 7.9.0 + `shim.js` + the original page (`reference/index.original.html`, checked against `reference/PAGE_SHA256SUMS`) + `cloud.js`.
  `shim.js` stands in for the claude.ai Dashboard runtime the page was written for (`dash.data`, `dash.draw`, `dash.calc`, `dash.onData`, `dash.setLink`, `dash.colors` and the CSS tokens) and reads `public/data/<prefix><name>.json`. `cloud.js` adds the Refresh button and the freshness strip above the page.
  Changes to the page, made by `tools/page.js` and checked on every run: the SOL and BNB tabs are copies of the ETH Daily and ETH 4H tabs with only the coin, its data and its history start changed (`config/dashboard.json` `page_coins`); chart labels under $1,000 show dollars instead of $0.1k; and the data-source line on each tab, which now says "from Market-Data (your Binance upload)" instead of the Drive file name (`reference/PAGE_EDITS.json`, approved 14 Nov 2026).
- **Build**: `build/build.py <market-data dir>` runs the engine per tab (`config/dashboard.json`) and writes 6 files per tab (48 for 8 tabs) to `public/data/`, plus `public/freshness.json`. A tab whose last closed candle is already built is skipped. A tab that fails keeps its last good files and log and is listed in `freshness.json`.
- **Address**: none of its own (`workers_dev: false`). It opens at `/fib-extension/` on the home site (repo `dashboards`), which holds the one login lock. Controls at `/api/fib-extension/`.
- **Runs**: when Market-Data gets new BTCUSDT/ETHUSDT candles (Market-Data `dashboards.json`), once a day as a safety net (01:25 UTC), or when Refresh is pressed.

Tests:
- Parity, the artifact's refresh commands on the Drive files versus `build.py` on Market-Data, same last candle, same starting logs: `python3 tests/parity.py <market-data dir> <dir with d.json h4.json ethd.json eth4h.json from drive_to_json.py>`. 14 Nov 2026: all 24 files identical except the generated time.
- Render, all eight tabs: `node tests/render.js <node_modules dir with jsdom@24 and d3@7.9.0>`.
- Page and engine unchanged: `node tools/check_page.js`.

## USDT.D Daily tab (20 Nov 2026)

Owner's request: USDT.D (TradingView CRYPTOCAP:USDT.D via Market-Data: stored daily history from Mar 2015, then days made from closed 4H candles). Same engine, rules and layout as the other tabs (made from the ETH Daily tab by tools/page.js, page_coins usdtd). The engine rounds prices to whole numbers, so build.py feeds USDT.D x1000 and the USDT.D tab shows values / 1000 as %. A projected USDT.D top is a peak in USDT dominance, which has tended to line up with a crypto low. USDT.D 4H tab added 21 Nov 2026, once Market-Data held USDT.D 4H back to 1 Jan 2024 (about 6,330 candles, uploaded from the owner's PC). Forecast log starts 20 Nov 2026.

## Fib bottom tracker (21 Nov 2026)

Owner's request: the mirror of the tracker, so every tab also projects the next LOW. `build/bottoms.py` runs the unchanged engine on the inverted candles of each tab (price = K / value, high and low swapped; K fixed per tab, never change it once a log exists), where a falling A-B-C (A = swing high, B = swing low, C = lower high) reads as a rising one. The engine's projected top, zone, backtest, early-rejection warnings and forecast log become the projected low, the buy zone, the walk-forward record (within ±10% / ±5% of the real low), early bounce warnings and a bottom forecast log (`state/bottom_log_<tab>.json`). Output: `public/data/fibx_<tab>.json` (key `bottom`), drawn by `public/fibx.js` in a card under each tab's header (`tools/page.js` adds an empty `<div class="fx-root">` there and the script tag; the original markup is otherwise unchanged). First run, 21 Nov 2026: BTC Daily 58/74 within ±10% (78%), BTC 4H 72%, ETH Daily 72%, SOL Daily 71%, USDT.D Daily 80%.

## Cycle and level (21 Nov 2026)

A "🧭 Cycle and level" card above the bottom tracker on every tab: daily tabs follow 10% swings (local-to-swing turns), 4H tabs 5% swings (local); the cycle comes from the weekly read, computed in `build/bottoms.py` (`cycles()`) with the same rules as the BTC cycle and USDT.D tabs of the BTC & ETH dashboard (checked equal on 21 Nov 2026: BTC 50W 74,991, 100W 88,690, 200W 67,976; USDT.D 50W 7.42, 100W 6.09). Stored as `cycle` in `public/data/fibx_<tab>.json` and refreshed on every run: BTC's read, the coin's own read and USDT.D's, with what a projected top or low means under that read.

## Zone + early-sign test (21 Nov 2026)

`research/confluence_test.py` (run: `python3 -I research/confluence_test.py <market-data> [inv]`) replays every past setup that touched the zone and compares selling at the first zone touch with waiting for a pullback (WATCH) or an RSI(7) drop back under 70 after the touch. The zone alone ended closer to the actual top on every tab (BTC D median −6.5% vs −8.5% / −10.0%; same for bottoms), so no confluence signal was added; the result is shown on each tab's Cycle and level card from `public/data/fibx_confluence.json`.

## Hit record by market (21 Nov 2026)

`build/regimes.py` (a CI step after the bottom tracker) replays the walk-forward backtest for tops and bottoms on every tab and tags each past setup by BTC's weekly side at its C point (bull side = last closed weekly close above both the 50W and 100W SMA). Output `public/data/fibx_regime.json`, shown as a small table on the Cycle and level card with the current side in bold. Replay counts differ slightly from the engine's headline record (no 4H archive, no forecast-log merge).

## Time window (21 Nov 2026)

`build/regimes.py` also stores, per tab and per tracker, the bars from C to the top (or low) over all completed setups (median, 25/75/90th percentiles) and the current C (provisional or confirmed, or broken). The Cycle and level card shows how much time has passed since C, what share of past tops/lows had come by now and the middle-half window; past the 90% mark it says the turn may be in or close.
