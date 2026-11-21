/* Fib Top Tracker extras (owner, 21 Nov 2026): one extra card at the top of every tab, drawn from public/data/fibx_<tab>.json.
   Part 1: the Fib BOTTOM tracker (build/bottoms.py): the same engine on the mirror image of the chart, so it reads the
   falling A-B-C (A = swing high, B = swing low, C = lower high) and projects the next LOW and a buy zone.
   Later parts add their sections to the same card. Read-only; the original page is not changed (tools/page.js only adds
   an empty <div class="fx-root" data-fx="..."> under each tab's header and this script). */
(function () {
  'use strict';
  const TABS = { daily: 'btc_d', h4: 'btc_4h', ethd: 'eth_d', ethh4: 'eth_4h', sold: 'sol_d', solh4: 'sol_4h', bnbd: 'bnb_d', bnbh4: 'bnb_4h', usdtdd: 'usdtd_d', usdtdh4: 'usdtd_4h' };
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dd = (s) => { if (!s) return '—'; const d = new Date(s.slice(0, 10) + 'T00:00:00Z'); return d.getUTCDate() + ' ' + MON[d.getUTCMonth()] + ' ' + d.getUTCFullYear() + (s.length > 10 ? ' ' + s.slice(11) : ''); };
  const pc = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + (v * 100).toFixed(1) + '%');
  const P0 = (v) => (v == null ? '—' : Math.round(v * 100) + '%');
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

  function card(id, J) {
    const b = J.bottom; if (!b) return null;
    const pct = b.unit === 'pct', isU = id.startsWith('usdtd');
    const f = (v) => (v == null ? '—' : pct ? v.toFixed(2) + '%' : '$' + (v >= 1000 ? Math.round(v).toLocaleString('en-US') : v.toLocaleString('en-US', { maximumFractionDigits: 2 })));
    const tfw = b.timeframe === '4H' ? '4H' : 'daily', bar = b.timeframe === '4H' ? '4H candle' : 'daily candle';
    const c = el('section', 'ft-card');
    c.style.borderLeft = '3px solid var(--color-ok, #0d8a5c)';
    c.append(el('h2', null, `⤵ Fib bottom tracker <span class="ft-note" style="font-weight:400">· the mirror of this page: falling A-B-C → next projected ${tfw} low${isU ? ' (a USDT.D low has tended to line up with a crypto top)' : ''}</span>`));
    const pill = `<span class="ft-pill">${b.status_label}</span>`;
    if (b.status === 'broken') {
      c.append(el('p', 'ft-take', `No ${tfw} projected low right now. ${b.note} ${pill}`));
      if (b.last_high != null) c.append(el('p', 'ft-note', `Since the last swing high (${f(b.last_high)}, ${dd(b.last_high_date)}) price has not bounced ${Math.round(b.zigzag * 100)}% yet, so there is no swing low B. Lowest so far ${f(b.low_since)} (${dd(b.low_since_date)}): a bounce to <b>${f(b.confirm_bounce_at)}</b> would make it B; then a lower high (C) under ${f(b.last_high)} starts a new projected low.`));
    } else {
      c.append(el('p', 'ft-take', `Next projected ${tfw} low <b>${f(b.target)}</b>, likely buy zone <b>${f(b.zone[0])}</b> to <b>${f(b.zone[1])}</b> (${pc(b.to_target_pct)} from price). ${pill}`));
      c.append(el('p', 'ft-note', b.note));
      const tiles = el('div', 'ft-tiles');
      const tile = (lab, big, sub) => { const t = el('div', 'ft-tile'); t.append(el('p', 'ft-label', lab), el('p', 'ft-big', big), el('p', 'ft-sub', sub || '')); return t; };
      tiles.append(
        tile('Projected low', f(b.target), `Extension ${b.ratio} of the A to B fall`),
        tile('Buy zone', `${f(b.zone[0])} – ${f(b.zone[1])}`, 'Middle half of past outcomes'),
        tile('Low so far', b.low_so_far != null ? f(b.low_so_far) : (b.post_c_low != null ? f(b.post_c_low) : '—'), b.post_c_low_date ? `since C (${dd(b.post_c_low_date)}), bounce ${pc(b.bounce_from_low)}` : 'C not confirmed yet'),
        tile('Swings', `A ${f(b.A)}`, `B ${f(b.B)} (${dd(b.b_date)}) · C ${f(b.C)} (${dd(b.c_date)}, ${b.c_confirmed ? 'confirmed' : 'provisional'})`));
      c.append(tiles);
      if (b.levels && b.levels.length) c.append(el('p', 'ft-note', 'Fib extensions of the A to B fall from C: ' + b.levels.map((x) => `${x.ratio} ${f(x.price)}`).join(' · ') + '.'));
      if (b.support && b.support.length && b.support[0].price != null) c.append(el('p', 'ft-note', 'Support (past swing lows and highs) between price and the zone: ' + b.support.slice(0, 5).map((x) => `${f(x.price)} (${x.touches}×${x.in_zone ? ', in the zone' : ''})`).join(' · ') + '.'));
    }
    const bt = b.backtest || {};
    c.append(el('p', 'ft-note', `<b>Record</b> (walk-forward, every completed falling A-B-C): ${bt.within_tol}/${bt.n} projected lows within ±${Math.round(b.hit_tol * 100)}% of the real low (${P0(bt.within_pct)}; within ±${Math.round(b.hit_tol * 50)}%: ${P0(bt.within_half_pct)}; median miss ${pc(bt.median_err).replace('+', '')}). ` +
      `Price went below B in ${P0(bt.lower_low_pct)} of setups. Early bounce warning (price stalls above the zone and bounces ${Math.round(b.hit_tol * 70)}%): right ${bt.early && bt.early.warn ? bt.early.warn.correct + '/' + bt.early.warn.fired : '—'} times (the low was in above the zone). ` +
      `Live log: ${b.live_stats.issued} projections issued, ${b.live_stats.scored} scored, ${b.live_stats.hits} hits.`));
    const fc = (b.forecasts || []).slice(0, 5);
    if (fc.length) {
      const t = el('table'); t.style.cssText = 'width:100%;border-collapse:collapse;font-size:var(--cds-font-size-caption);font-variant-numeric:tabular-nums';
      t.innerHTML = '<thead><tr>' + ['Opened', 'Projected low', 'Buy zone', 'State', 'Real low'].map((h) => `<th style="text-align:left;color:var(--color-fg-muted);font-weight:500;padding:2px 6px;border-bottom:1px solid var(--color-border-line)">${h}</th>`).join('') + '</tr></thead><tbody>' +
        fc.map((x) => `<tr>${[dd(x.opened), f(x.target), `${f(x.zone[0])} – ${f(x.zone[1])}`, x.state + (x.reason && x.state !== 'open' ? ` <span style="color:var(--color-fg-muted)">(${x.reason})</span>` : ''), x.low != null ? `${f(x.low)} ${x.hit ? '✓' : '✗'}` : '—'].map((v) => `<td style="padding:2px 6px;border-bottom:1px solid var(--color-border-line)">${v}</td>`).join('')}</tr>`).join('') + '</tbody>';
      const d = el('details'); d.append(el('summary', 'ft-note', 'Latest bottom projections (forecast log, started 21 Nov 2026)')); const w = el('div', 'ft-scroll'); w.append(t); d.append(w); c.append(d);
    }
    c.append(el('p', 'ft-note', `Built ${b.generated} from the same closed ${bar}s and the same engine as the top tracker below, run on the mirror image of the chart (1 ÷ price). Statistical projection, not financial advice.`));
    return c;
  }

  // ---------- part 2: cycle and level ----------
  function cycleCard(id, J) {
    const Y = J.cycle; if (!Y || !Y.btc) return null;
    const isU = id.startsWith('usdtd'), h4 = id.endsWith('_4h');
    const usd = (v) => (v == null ? '—' : '$' + (v >= 1000 ? Math.round(v).toLocaleString('en-US') : v.toLocaleString('en-US', { maximumFractionDigits: 2 })));
    const pcv = (v) => (v == null ? '—' : v.toFixed(2) + '%');
    const bearish = (v) => /^Bear|Turning bear/.test(v);
    const c = el('section', 'ft-card'); c.style.borderLeft = '3px solid var(--color-accent, #2557d6)';
    c.append(el('h2', null, '🧭 Cycle and level <span class="ft-note" style="font-weight:400">· what a projection on this tab can and cannot tell you</span>'));
    const L = [];
    L.push(`<b>Level:</b> ${h4 ? '4H tabs follow 5% swings: local turns, several a month.' : 'daily tabs follow 10% swings: local-to-swing turns, a few a quarter.'} Neither tracker calls the cycle top or bottom by itself; the weekly read below does.`);
    const B = Y.btc, bw = `weekly close ${usd(B.week_close)} (week of ${dd(B.week)}); 50W ${usd(B.w50)}, 100W ${usd(B.w100)}, 200W ${usd(B.w200)}`;
    L.push(`<b>BTC cycle read: <span class="ft-pill">${B.verdict}</span></b> · ${bw}.`);
    if (isU) {
      const U = Y.usdtd;
      if (U) {
        L.push(`<b>USDT.D read: <span class="ft-pill">${U.verdict}</span></b> · weekly close ${pcv(U.week_close)}; 50W ${pcv(U.w50)}, 100W ${pcv(U.w100)}. (USDT.D up = crypto down.)`);
        L.push(bearish(U.verdict)
          ? `<b>Top tracker (this page):</b> a projected USDT.D top marks a crypto relief-rally low until USDT.D closes weeks below its 50W (${pcv(U.w50)}) and then its 100W (${pcv(U.w100)}); after the Nov 2022 peak that took until Jan 2023 and Oct 2023.<br><b>Bottom tracker:</b> a projected USDT.D low marks the top of a crypto relief rally inside the bear, not the cycle top.`
          : `<b>Top tracker (this page):</b> USDT.D is in the bull pattern for crypto, so a projected USDT.D top is a pause in a crypto uptrend.<br><b>Bottom tracker:</b> a projected USDT.D low is a crypto swing top until USDT.D closes weeks back above its 50W (${pcv(U.w50)}) and 100W (${pcv(U.w100)}).`);
      }
    } else {
      L.push(bearish(B.verdict)
        ? `<b>Top tracker (this page):</b> with BTC in a bear, a projected top is a relief-rally top, not the cycle top.<br><b>Bottom tracker:</b> a projected low is a swing low until BTC closes weeks back above its 50W (${usd(B.w50)}) and then its 100W (${usd(B.w100)}); the Nov 2022 low only showed itself as the cycle low that way (50W Mar 2023, 100W Oct 2023).`
        : `<b>Top tracker (this page):</b> a projected top is a swing top inside the bull until BTC closes weeks below its 50W (${usd(B.w50)}); the Nov 2021 top turned that way (50W lost Dec 2021).<br><b>Bottom tracker:</b> a projected low is a dip inside the bull (in 2023–25 BTC held its 50W about 9 weeks in 10).`);
      const O = Y.own;
      if (Y.coin !== 'BTC' && O) L.push(`<b>${Y.coin}'s own read: <span class="ft-pill">${O.verdict}</span></b> · weekly close ${usd(O.week_close)}; 50W ${usd(O.w50)}, 100W ${usd(O.w100)}, 200W ${usd(O.w200)}.`);
    }
    const cf = CONF && CONF.top && CONF.top[id], cb = CONF && CONF.bottom && CONF.bottom[id];
    if (cf && cf.zone && cf.pull && cf.rsi) {
      const f = (x) => (x > 0 ? '+' : '') + x.toFixed(1) + '%';
      L.push(`<b>Tested 21 Nov 2026: zone touch vs zone touch + early sign.</b> Selling at the first touch of the zone ended a median ${f(cf.zone.med)} from the actual top (${cf.zone.n} past setups); waiting for a ${h4 ? '2.5' : '5'}% pullback after the touch gave ${f(cf.pull.med)}, and waiting for RSI(7) to drop back under 70 gave ${f(cf.rsi.med)}. So the zone itself is the better level; a sign only helped in the rare runs that kept going far past the zone (sold more than ${h4 ? '10' : '20'}% under the top: ${cf.zone.bad}% at the zone vs ${cf.rsi.bad}% with the RSI sign).${cb && cb.zone ? ` Bottoms: same result (${f(cb.zone.med)} at the zone vs ${f(cb.pull.med)} after a bounce sign).` : ''} The trackers keep the zone as the call.`);
    }
    L.forEach((x) => c.append(el('p', 'ft-note', x)));
    c.append(el('p', 'ft-note', 'Weekly read = the same rules as the BTC cycle and USDT.D tabs of the BTC & ETH dashboard (closed Monday weeks; updates each Monday 11:00 Sydney).'));
    return c;
  }

  let CONF = null;
  function drawAll() {
    document.querySelectorAll('.fx-root[data-fx]').forEach((root) => {
      const id = root.dataset.fx;
      if (root.dataset.done) return; root.dataset.done = '1';
      fetch('data/fibx_' + id + '.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).then((J) => {
        if (!J) return; root.replaceChildren(...[cycleCard(id, J), card(id, J)].filter(Boolean));
      }).catch(() => {});
    });
  }
  window.__fibxTabs = TABS;
  const start = () => fetch('data/fibx_confluence.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null).then((x) => { CONF = x; drawAll(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
