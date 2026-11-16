/* BTC & ETH Fib Top Tracker on Cloudflare: a strip above the page with a Refresh button (asks GitHub to rebuild from
   the newest closed candles in Market-Data) and the freshness of each tab's candles. The page itself is unchanged. */
(function () {
  'use strict';
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var slug = location.pathname.split('/')[1] || '';
  var API = slug ? '/api/' + slug + '/' : 'api/';   // controls live at /api/<slug>/ on the home site, behind the owner's login
  var st = document.createElement('style');
  st.textContent = '.fx-bar{max-width:1200px;margin:0 auto;padding:12px 16px 0;display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;font-size:var(--cds-font-size-caption);color:var(--color-fg-muted)}' +
    '.fx-bar details{flex:1 1 320px;min-width:0;overflow-x:auto}.fx-bar summary{cursor:pointer}.fx-bar b{color:var(--color-fg)}' +
    '.fx-bar table{margin-top:6px;border-collapse:collapse;font-variant-numeric:tabular-nums}.fx-bar td,.fx-bar th{padding:2px 14px 2px 0;text-align:left;white-space:nowrap}' +
    '.fx-btn{font:inherit;padding:4px 12px;border:1px solid var(--color-border-line);border-radius:var(--cds-radius);background:var(--color-panel);color:var(--color-fg);cursor:pointer}' +
    '.fx-btn[disabled]{opacity:.5;cursor:default}.fx-pill{padding:1px 8px;border-radius:999px;border:1px solid var(--color-border-line)}' +
    '.fx-pill.ok{color:var(--color-ok);border-color:var(--color-ok)}.fx-pill.warn{color:var(--color-warn);border-color:var(--color-warn)}';
  document.head.appendChild(st);
  var bar = document.createElement('div'); bar.className = 'fx-bar';
  var info = document.createElement('details'); info.innerHTML = '<summary>Loading data status…</summary>';
  var pill = document.createElement('span'); pill.className = 'fx-pill'; pill.hidden = true;
  var btn = document.createElement('button'); btn.className = 'fx-btn'; btn.type = 'button'; btn.textContent = 'Refresh'; btn.hidden = true;
  btn.title = 'Ask GitHub to rebuild every tab from the newest closed candles';
  bar.appendChild(info); bar.appendChild(pill); bar.appendChild(btn);
  var page = document.querySelector('body > .ft');
  document.body.insertBefore(bar, page || document.body.firstChild);

  var t2s = function (s) { if (!s) return '—'; var d = new Date(s * 1000); return d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); };
  function state(text, kind) { pill.hidden = false; pill.className = 'fx-pill ' + (kind || ''); pill.textContent = text; }
  function showFresh(F) {
    var now = Date.now() / 1000;
    var rows = F.series.map(function (s) {
      var behind = s.last_close ? Math.max(0, Math.floor((now - s.last_close) / s.period_s)) : null;
      var kept = (F.kept || []).filter(function (k) { return k.id === s.id; })[0];
      var stt = behind === null ? 'no data yet' : behind === 0 ? 'current' : behind + ' candle' + (behind > 1 ? 's' : '') + ' behind';
      if (kept) stt += ' · kept last good data: ' + kept.why;
      return { s: s, when: t2s(s.last_close), st: stt, flag: behind === null || behind > 1 || !!kept };
    });
    var flagged = rows.filter(function (r) { return r.flag; }).length;
    info.innerHTML = '<summary>Built ' + esc(F.generated) + ' · ' + (flagged ? '<b>' + flagged + ' of ' + rows.length + ' tabs behind</b>' : 'all ' + rows.length + ' tabs current') + '</summary>' +
      '<table><thead><tr><th>Tab</th><th>Candles</th><th>Last closed candle (your time)</th><th>Status</th></tr></thead><tbody>' +
      rows.map(function (r) { return '<tr' + (r.flag ? ' style="font-weight:600"' : '') + '><td>' + esc(r.s.title) + '</td><td>' + esc(r.s.symbol + ' ' + r.s.tf) + '</td><td>' + esc(r.when) + '</td><td>' + esc(r.st) + '</td></tr>'; }).join('') +
      '</tbody></table><p style="margin:6px 0 0">' + esc(F.last_result) + ' Candles: Binance spot BTCUSDT and ETHUSDT from the shared Market-Data store (your Binance upload, the same candles as your Google Drive files), closed candles only. The engine, rules and forecast logs are the ones the artifact used.</p>';
  }
  fetch('freshness.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (F) { if (F) showFresh(F); else info.hidden = true; }).catch(function () { info.hidden = true; });

  var polling = null;
  function poll(startedAt) {
    clearTimeout(polling);
    fetch(API + 'status', { cache: 'no-store', redirect: 'manual', credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('no access'); return r.json(); }).then(function (s) {
      btn.hidden = false;
      if (s.status && s.status !== 'completed' && s.status !== 'none') { state('Running…', 'warn'); btn.disabled = true; polling = setTimeout(function () { poll(startedAt || Date.now()); }, 8000); return; }
      btn.disabled = false;
      if (!startedAt) return;
      if (s.conclusion === 'success') { state('Done ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), 'ok'); setTimeout(function () { location.reload(); }, 1500); }
      else state('Refresh failed, last good data kept', 'warn');
    }).catch(function () { btn.disabled = false; if (startedAt) state('Could not check progress', 'warn'); else btn.hidden = true; });
  }
  btn.addEventListener('click', function () {
    btn.disabled = true; state('Starting…', '');
    fetch(API + 'refresh', { method: 'POST', redirect: 'manual', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: '{}' })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status)); return j; }); })
      .then(function () { state('Running…', 'warn'); setTimeout(function () { poll(Date.now()); }, 5000); })
      .catch(function (e) { btn.disabled = false; state('Refresh not started: ' + e.message, 'warn'); });
  });
  poll(0);
})();

/* "← Dashboards" link back to the home site, same as the Data check page. Added on Cloudflare only; the page itself is unchanged. */
(function () {
  'use strict';
  var st = document.createElement('style');
  st.textContent = '.dash-back{display:inline-block;font-size:13px;line-height:1.4;color:var(--muted,var(--color-fg-muted,#586878));text-decoration:none;white-space:nowrap}' +
    '.dash-back:hover{text-decoration:underline}.dash-back-row{margin:0 0 6px}';
  document.head.appendChild(st);
  var a = document.createElement('a'); a.className = 'dash-back'; a.href = '/'; a.textContent = '← Dashboards';
  a.title = 'Back to the list of dashboards';
  var host = document.body.firstElementChild;
  while (host && (/^(SCRIPT|STYLE|LINK|META|NOSCRIPT|TITLE|TEMPLATE)$/.test(host.tagName) || getComputedStyle(host).display === 'none')) host = host.nextElementSibling;
  var row = document.createElement('div'); row.className = 'dash-back-row'; row.appendChild(a);
  if (host && host.classList.contains('fx-bar')) { a.style.marginRight = '6px'; host.insertBefore(a, host.firstChild); }
  else if (host) host.insertBefore(row, host.firstChild);
  else document.body.insertBefore(row, document.body.firstChild);
})();
