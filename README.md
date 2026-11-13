# BTC & ETH Fib Top Tracker

The Claude artifact "BTC & ETH Fib Top Tracker" (four tabs: BTC Daily, BTC 4H, ETH Daily, ETH 4H), rebuilt on GitHub and shown on Cloudflare.
Statistical projection, not financial advice. Spot only.

- **Data**: Binance spot BTCUSDT and ETHUSDT, 1D and 4H, from the shared repo `mbzazad-max/market-data` (your Binance upload), closed candles only.
  These are the same candles as your Google Drive files `BTCUSDT_D.xlsx`, `BTCUSDT_4H.xlsx`, `ETHUSDT_D.xlsx`, `ETHUSDT_4H.xlsx` (checked candle by candle on 14 Nov 2026: 0 differences).
  No TradingView or other calls: nothing new is fetched for this dashboard.
- **Logic**: the artifact's own engine, unchanged: `engine/fib_top_engine.py` and `engine/export_dash.py` (copied from `claude/fibtop/` in the Trading project, checked against `reference/ENGINE_SHA256SUMS` on every run).
  Zigzag swings (daily 10%, 4H 5%), bullish ABC, target = C + median extension × (B − A) per trend regime, zone = middle half, forecast log, early-rejection watch/warning, zone confluence, low strength badges.
- **Forecast logs**: `state/forecast_log*.json`, continued from the artifact's logs. Each build adds to them exactly as the artifact refresh did.
- **Page**: `public/index.html` = the artifact host's head + d3 7.9.0 + `shim.js` + the original page (`reference/index.original.html`, checked against `reference/PAGE_SHA256SUMS`) + `cloud.js`.
  `shim.js` stands in for the claude.ai Dashboard runtime the page was written for (`dash.data`, `dash.draw`, `dash.calc`, `dash.onData`, `dash.setLink`, `dash.colors` and the CSS tokens) and reads `public/data/<prefix><name>.json`. `cloud.js` adds the Refresh button and the freshness strip above the page.
  The page's own words still say "from your Google Drive file …": the page is kept unchanged; the strip says where the candles come from here.
- **Build**: `build/build.py <market-data dir>` runs the engine per tab (`config/dashboard.json`) and writes 6 files per tab (24 in all) to `public/data/`, plus `public/freshness.json`. A tab whose last closed candle is already built is skipped. A tab that fails keeps its last good files and log and is listed in `freshness.json`.
- **Address**: none of its own (`workers_dev: false`). It opens at `/fib-extension/` on the home site (repo `dashboards`), which holds the one login lock. Controls at `/api/fib-extension/`.
- **Runs**: when Market-Data gets new BTCUSDT/ETHUSDT candles (Market-Data `dashboards.json`), once a day as a safety net (01:25 UTC), or when Refresh is pressed.

Tests:
- Parity, the artifact's refresh commands on the Drive files versus `build.py` on Market-Data, same last candle, same starting logs: `python3 tests/parity.py <market-data dir> <dir with d.json h4.json ethd.json eth4h.json from drive_to_json.py>`. 14 Nov 2026: all 24 files identical except the generated time.
- Render, all four tabs: `node tests/render.js <node_modules dir with jsdom@24 and d3@7.9.0>`.
- Page and engine unchanged: `node tools/check_page.js`.
