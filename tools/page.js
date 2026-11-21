/* Makes the Cloudflare page from the original artifact page (reference/index.original.html):
   1. the approved text edits in reference/PAGE_EDITS.json (data-source line per tab);
   2. for each coin in config/dashboard.json "page_coins" (added 14 Nov 2026): a Daily and a 4H tab copied from the
      ETH Daily and ETH 4H tabs, with only the coin, its data (dataset prefix), its history start and its log start
      changed; the tab buttons, the page's prefix map, the chart label and the ladder calculation get the new coins;
   3. the title from config "title", and chart labels for prices under $1,000 in dollars (not $0.1k).
   Same layout, same drawings, same rules as the ETH tabs. */
'use strict';
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
function once(s, from, to, what) {
  if (s.split(from).length !== 2) throw new Error('page.js: not found exactly once: ' + (what || from.slice(0, 80)));
  return s.replace(from, () => to);
}
module.exports = function makePage() {
  let page = fs.readFileSync(path.join(ROOT, 'reference/index.original.html'), 'utf8');
  for (const e of JSON.parse(fs.readFileSync(path.join(ROOT, 'reference/PAGE_EDITS.json'), 'utf8')).edits) page = once(page, e.from, e.to);
  const cfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'config/dashboard.json'), 'utf8'));
  const coins = cfg.page_coins || [];
  if (!coins.length) return page;
  const a = page.indexOf('  <section class="ft-page" id="ethd"'), b = page.indexOf('  <section class="ft-page" id="ethh4"'), c = page.indexOf('</div>\n\n<script>');
  if (a < 0 || b < a || c < b) throw new Error('page.js: ETH tabs not found');
  const ethD = page.slice(a, b), ethH = page.slice(b, c);
  const conv = (src, k, S, since, from, h4, rep) => {
    let s = src;
    for (const [f, t] of rep || []) s = s.split(f).join(t);   // coin-specific text (USDT.D: its TradingView symbol and source)
    s = s.split(h4 ? 'id="ethh4' : 'id="ethd').join(h4 ? 'id="' + k + 'h4' : 'id="' + k + 'd');
    s = s.split(h4 ? 'tab-ethh4' : 'tab-ethd').join(h4 ? 'tab-' + k + 'h4' : 'tab-' + k + 'd');
    s = s.split(h4 ? 'data-tf="eth_h4"' : 'data-tf="eth"').join(h4 ? 'data-tf="' + k + '_h4"' : 'data-tf="' + k + '"');
    s = s.split(h4 ? 'data-source="eth_h4_' : 'data-source="eth_').join(h4 ? 'data-source="' + k + '_h4_' : 'data-source="' + k + '_');
    s = s.split('ETHUSDT').join(S + 'USDT');
    s = s.replace(/\bETH\b/g, S);
    s = s.split('since 2017').join('since ' + since);
    s = s.split('logged from 7 Nov 2026').join('logged from ' + from);
    if (/\bETH\b|ethd|ethh4|"eth_|data-tf="eth/.test(s)) throw new Error('page.js: ETH left in the ' + S + ' tab');
    return s;
  };
  let add = '', btn = '', pre = '', lad = '';
  for (const x of coins) {
    const dOnly = x.only === 'D';   // USDT.D: Daily tab only (too little 4H history)
    add += '\n' + conv(ethD, x.key, x.sym, x.since, x.logged_from, false, x.replace) + (dOnly ? '' : conv(ethH, x.key, x.sym, x.since, x.logged_from, true, x.replace));
    btn += '\n      <button type="button" role="tab" id="tab-' + x.key + 'd" data-tab="' + x.key + 'd" aria-selected="false" aria-controls="' + x.key + 'd">' + x.sym + ' Daily</button>' +
           (dOnly ? '' : '\n      <button type="button" role="tab" id="tab-' + x.key + 'h4" data-tab="' + x.key + 'h4" aria-selected="false" aria-controls="' + x.key + 'h4">' + x.sym + ' 4H</button>');
    pre += ', ' + x.key + ": '" + x.key + "_'" + (dOnly ? '' : ', ' + x.key + "_h4: '" + x.key + "_h4_'");
    lad += ", ['" + x.key + "_', '" + x.sym + " distance from price']" + (dOnly ? '' : ", ['" + x.key + "_h4_', '" + x.sym + " distance from price (4H)']");
  }
  page = once(page, '</div>\n\n<script>', add.replace(/^\n/, '') + '</div>\n\n<script>');
  page = once(page, 'aria-controls="ethh4">ETH 4H</button>', 'aria-controls="ethh4">ETH 4H</button>' + btn);
  page = once(page, "eth: 'eth_', eth_h4: 'eth_h4_' }", "eth: 'eth_', eth_h4: 'eth_h4_'" + pre + ' }');
  page = once(page, "const asset = (el) => (tf(el).startsWith('eth') ? 'ETH' : 'BTC');",
    "const asset = (el) => (" + JSON.stringify(Object.fromEntries([['eth', 'ETH']].concat(coins.map((x) => [x.key, x.sym])))) + "[tf(el).split('_')[0]] || 'BTC');");
  page = once(page, "['eth_h4_', 'ETH distance from price (4H)']]", "['eth_h4_', 'ETH distance from price (4H)']" + lad + ']');
  // chart axis labels: the original shows every price in thousands ($1.9k), which reads $0.1k for SOL and $0.7k for BNB.
  // Prices of $1,000 and more are labelled exactly as before; smaller ones in dollars ($82.5, $657).
  page = once(page, "const fmtK = (v) => '$' + d3.format(',.1~f')(v / 1000) + 'k';",
    "const fmtK = (v) => (Math.abs(v) >= 1000 ? '$' + d3.format(',.1~f')(v / 1000) + 'k' : '$' + d3.format(',.1~f')(v));");
  // USDT.D (20 Nov 2026): the engine gets USDT.D x pct_scale (it rounds prices to whole numbers); on that coin's tabs the
  // page's two price formatters show value / pct_scale as a percentage. shim.js sets window.__ftEl to the element being drawn.
  const pc = coins.filter((x) => x.pct_scale);
  if (pc.length) {
    const M = JSON.stringify(Object.fromEntries(pc.map((x) => [x.key, x.pct_scale])));
    const pk = "const __pk = () => { const e = window.__ftEl, p = e && e.closest && e.closest('[data-tf]'); return p ? (" + M + ")[p.dataset.tf.split('_')[0]] : 0; };\n    ";
    page = once(page, "    const usd = (v) => (v == null || isNaN(v) ? '—' : '$' + d3.format(',.0f')(v));",
      "    " + pk + "const usd = (v) => (v == null || isNaN(v) ? '—' : __pk() ? d3.format(',.2f')(v / __pk()) + '%' : '$' + d3.format(',.0f')(v));");
    page = once(page, "const fmtK = (v) => (Math.abs(v) >= 1000 ?",
      "const fmtK = (v) => ((" + M + ")[((window.__ftEl && window.__ftEl.closest && window.__ftEl.closest('[data-tf]')) || { dataset: { tf: '' } }).dataset.tf.split('_')[0]] ? d3.format(',.2f')(v / (" + M + ")[window.__ftEl.closest('[data-tf]').dataset.tf.split('_')[0]]) + '%' : Math.abs(v) >= 1000 ?");
  }
  if (cfg.title) page = once(page, '<h1 class="ft-title">BTC &amp; ETH Fib Top Tracker</h1>', '<h1 class="ft-title">' + cfg.title + '</h1>');
  // Extras (owner, 21 Nov 2026): an empty <div class="fx-root"> right under each tab's header, filled by public/fibx.js
  // (the Fib bottom tracker and the other additions); the original markup is otherwise untouched.
  const FX = { daily: 'btc_d', h4: 'btc_4h', ethd: 'eth_d', ethh4: 'eth_4h', sold: 'sol_d', solh4: 'sol_4h', bnbd: 'bnb_d', bnbh4: 'bnb_4h', usdtdd: 'usdtd_d', usdtdh4: 'usdtd_4h' };
  for (const [sec, id] of Object.entries(FX)) {
    const at = page.indexOf('<section class="ft-page" id="' + sec + '"');
    if (at < 0) continue;
    const h = page.indexOf('\n  </header>\n', at);
    if (h < 0) throw new Error('page.js: header of ' + sec + ' not found');
    const cut = h + '\n  </header>\n'.length;
    page = page.slice(0, cut) + '  <div class="fx-root" data-fx="' + id + '"></div>\n' + page.slice(cut);
  }
  page += '\n<script src="fibx.js"></script>';
  return page;
};
