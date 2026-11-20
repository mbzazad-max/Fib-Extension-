/* BTC & ETH Fib Top Tracker on Cloudflare: a small stand-in for the claude.ai Dashboard runtime the page was written for.
   The page (unchanged) calls dash.data / dash.draw / dash.calc / dash.onData / dash.setLink / dash.colors and uses the
   runtime's CSS tokens. Here:
   - dash.data(id) reads data/<id>.json, the files built on GitHub by the same engine the artifact refresh runs;
   - dash.draw(name, fn) runs fn on every [data-draw=name] that is not under [hidden], after the page's scripts, and again
     when data arrives, the window width changes or a hidden section is shown (a tab switch);
   - dash.onData(fn) runs before each round of drawings; dash.calc makes a derived dataset (the ladder);
   - the tokens (colors, sizes, gaps, fonts) are the Dashboard defaults, light and dark.
   Read-only: nothing can be written from the page. */
(function () {
  'use strict';
  var css = [
    ':root{--cds-gap-xs:.375rem;--cds-gap-sm:.5rem;--cds-gap-md:.75rem;--cds-gap-lg:1.25rem;',
    '--cds-pad-xs:.25rem;--cds-pad-sm:.375rem;--cds-pad-md:.75rem;--cds-pad-lg:1rem;--cds-radius:.5rem;',
    '--cds-font-size-caption:.75rem;--cds-font-size-body:.875rem;--cds-font-size-heading:.9375rem;--cds-font-size-title:1.375rem;',
    '--cds-font-weight-medium:500;--cds-dur-slow:.45s;',
    '--font-anthropic-sans:"Anthropic Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;',
    '--font-anthropic-serif:"Anthropic Serif",ui-serif,Georgia,"Times New Roman",serif;',
    '--color-bg:#faf9f5;--color-panel:#ffffff;--color-fg:#141413;--color-fg-muted:#6b6a64;--color-border-line:#e1e0d9;',
    '--color-ok:#006c10;--color-warn:#895902;--color-bad:#a42528;',
    '--cds-border:rgb(0 0 0 / .08);--cds-surface-popover:#ffffff;--cds-shadow-popover:0 8px 24px #0000001f,0 2px 6px #00000014;--cds-text-secondary:#6b6a64;',
    '--cds-chart-axis:#c3c2b7;--cds-chart-grid:rgb(11 11 11 / .1);--cds-chart-reference:#898781;--cds-chart-muted:#c3c2b7;--cds-chart-status-critical:#d03b3b;',
    '--fx-accent:#d97757;color-scheme:light}',
    '@media (prefers-color-scheme:dark){:root{--color-bg:#1a1a19;--color-panel:#20201f;--color-fg:#f0efec;--color-fg-muted:#a3a29b;--color-border-line:#383835;',
    '--color-ok:#53c556;--color-warn:#e49c06;--color-bad:#f17778;--cds-border:rgb(255 255 255 / .1);--cds-surface-popover:#303030;',
    '--cds-shadow-popover:0 8px 24px #00000052,0 2px 6px #0003;--cds-text-secondary:#a3a29b;--cds-chart-axis:#383835;--cds-chart-grid:rgb(255 255 255 / .1);',
    '--cds-chart-reference:#97958d;--cds-chart-muted:#5f5e5a;--cds-chart-status-critical:#dc3c3d;color-scheme:dark}}',
    'html,body{background:var(--color-bg)!important;color:var(--color-fg)!important}',
    'body{font-family:var(--font-anthropic-sans)!important;font-size:var(--cds-font-size-body)!important;line-height:1.45}',
    'body>.ft{max-width:1200px;margin:0 auto;padding:16px 16px 40px}',
    '.ft{grid-template-columns:minmax(0,1fr)}.ft-top>*{min-width:0}.ft-tabs{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}.ft-tabs button{flex:0 0 auto;white-space:nowrap}'
  ].join('');
  var st = document.createElement('style'); st.textContent = css; (document.head || document.documentElement).appendChild(st);

  var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var colors = [dark ? '#e08a6d' : '#d97757', '#3b7dd8', '#2f9e74', '#b0559e', '#c99a2e', '#5c6bc0', '#d4573b', '#4f9da6'];

  var store = {}, calcs = {}, draws = [], ons = [], started = false;
  function get(id) {
    if (calcs[id]) return calc(id);
    var s = store[id];
    if (!s) {
      s = store[id] = { status: 'loading', data: null };
      fetch('data/' + encodeURIComponent(id) + '.json', { cache: 'no-store' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (d) { s.status = 'ok'; s.data = d; schedule(); }, function (e) { s.status = 'error'; s.error = String(e); schedule(); });
    }
    return s.status === 'ok' ? { status: 'ok', data: s.data } : { status: s.status, data: [] };
  }
  function calc(id) {
    var c = calcs[id], ins = c.inputs.map(get);
    var bad = ins.filter(function (x) { return x.status !== 'ok'; })[0];
    if (bad) return { status: bad.status, data: [] };
    try { return { status: 'ok', data: c.fn.apply(null, ins.map(function (x) { return x.data; })) }; }
    catch (e) { return { status: 'error', data: [] }; }
  }
  var hiddenUnder = function (el) { return !!el.closest('[hidden]'); };
  var busy = false, pending = 0;
  function pass() {
    pending = 0; busy = true;
    try {
      ons.forEach(function (fn) { try { fn(); } catch (e) { console.error(e); } });
      draws.forEach(function (d) {
        document.querySelectorAll('[data-draw="' + d.name + '"]').forEach(function (el) {
          if (hiddenUnder(el)) return;
          try { window.__ftEl = el; d.fn(el); } catch (e) { console.error('drawing ' + d.name + ': ' + (e && e.message)); }
        });
      });
    } finally { if (mo) mo.takeRecords(); busy = false; }
  }
  function schedule() { if (!started || pending) return; pending = setTimeout(pass, 0); }

  window.dash = {
    data: get,
    draw: function (name, fn) {
      if (typeof fn === 'function') draws.push({ name: name, fn: fn });
      else if (fn && typeof fn.update === 'function') draws.push({ name: name, fn: function (el) { if (!el.__m) el.__m = { v: fn.mount ? fn.mount(el) : null }; fn.update(el, el.__m.v); } });
      schedule();
    },
    onData: function (fn) { ons.push(fn); schedule(); },
    calc: function (id, def) { calcs[id] = def; },
    setLink: function (id) { try { history.replaceState(null, '', '#' + id); } catch (e) { /* ignore */ } },
    params: function () { return {}; },
    setParams: function () {},
    colors: colors
  };

  var mo = null;
  function start() {
    started = true;
    if (window.MutationObserver) {
      mo = new MutationObserver(function () { if (!busy) schedule(); });
      mo.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
    }
    var w = window.innerWidth;
    window.addEventListener('resize', function () { if (window.innerWidth !== w) { w = window.innerWidth; clearTimeout(start.t); start.t = setTimeout(schedule, 120); } });
    pass();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else setTimeout(start, 0);
})();
