/* Render check: public/index.html (artifact host head + d3 + shim.js + the original page + cloud.js) opened with the
   built public/data/*.json. Clicks through all four tabs and fails on any page error, a drawing that stays empty, a
   wrong number on screen (compared with summary.json), or a chart missing.
   usage: node tests/render.js <node_modules dir that has jsdom and d3> */
'use strict';
const fs = require('fs'), path = require('path');
const NM = path.resolve(process.argv[2]);
const { JSDOM, VirtualConsole } = require(path.join(NM, 'jsdom'));
const PUB = path.resolve(__dirname, '..', 'public');
const TABS = [['daily', ''], ['h4', 'h4_'], ['ethd', 'eth_'], ['ethh4', 'eth_h4_']];
const usd = (v) => (v == null ? '—' : '$' + Math.round(v).toLocaleString('en-US'));
(async () => {
  const html = fs.readFileSync(path.join(PUB, 'index.html'), 'utf8')
    .replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>', () => '<script>' + fs.readFileSync(path.join(NM, 'd3/dist/d3.min.js'), 'utf8') + '</script>')
    .replace('<script src="shim.js"></script>', () => '<script>' + fs.readFileSync(path.join(PUB, 'shim.js'), 'utf8') + '</script>')
    .replace('<script src="cloud.js"></script>', () => '<script>' + fs.readFileSync(path.join(PUB, 'cloud.js'), 'utf8') + '</script>');
  const errors = [], fetched = [], vc = new VirtualConsole();
  vc.on('error', (...a) => errors.push(a.map(String).join(' '))); vc.on('jsdomError', (e) => errors.push('jsdom: ' + e.message));
  const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc, url: 'https://dashboards.example/fib-extension/', beforeParse(w) {
    w.fetch = async (u) => { const f = String(u); fetched.push(f);
      if (f.includes('/api/')) return { ok: false, status: 302, json: async () => ({}) };   // visitor without the owner login
      const p = path.join(PUB, decodeURIComponent(f.split('?')[0]));
      if (!fs.existsSync(p)) return { ok: false, status: 404, json: async () => ({}) };
      const b = fs.readFileSync(p, 'utf8'); return { ok: true, status: 200, json: async () => JSON.parse(b) }; };
    w.SVGElement.prototype.getComputedTextLength = function () { return (this.textContent || '').length * 7; };
    Object.defineProperty(w.HTMLElement.prototype, 'clientWidth', { get() { return 900; } });
  } });
  const w = dom.window, d = w.document, sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  await sleep(1500);
  const out = [], bad = [];
  for (const [id, pre] of TABS) {
    d.getElementById('tab-' + id).click(); await sleep(600);
    const sec = d.getElementById(id), s = JSON.parse(fs.readFileSync(path.join(PUB, 'data', pre + 'summary.json'), 'utf8'))[0];
    const t = (q) => { const e = sec.querySelector(q); return e ? e.textContent.trim() : null; };
    const broken = s.status === 'broken';
    const take = sec.querySelector('[data-when="' + (broken ? 'broken' : 'setup') + '"]');
    const v = { tab: id, shown: !sec.hidden, status: null, close: t('[data-draw="close"]'),
      take_shown: take && !take.hidden, other_hidden: sec.querySelector('[data-when="' + (broken ? 'setup' : 'broken') + '"]').hidden,
      target: broken ? t('[data-draw="blow"]') : t('[data-draw="target"]'), chart: sec.querySelectorAll('[data-draw="chart"] svg path').length,
      rsi: sec.querySelectorAll('[data-draw="rsichart"] svg path').length, log: sec.querySelectorAll('[data-draw="log"] tr').length,
      bt: sec.querySelectorAll('[data-draw="bt"] tr').length, ladder: sec.querySelectorAll('[data-draw="ladder"] tr').length,
      live: t('[data-draw="livedate"]') };
    v.status = take && take.querySelector('[data-draw="status"]').textContent.trim();
    const want = { status: s.status_label, close: usd(s.live_close), target: usd(broken ? s.broken_low : s.target), live: s.live_date };
    for (const k of Object.keys(want)) if (v[k] !== want[k]) bad.push(id + ' ' + k + ': page shows ' + v[k] + ', data says ' + want[k]);
    if (!v.shown || !v.take_shown || !v.other_hidden || v.chart < 2 || v.rsi < 1 || v.log < 1 || v.bt < 1 || v.ladder < 1) bad.push(id + ' incomplete: ' + JSON.stringify(v));
    const empty = [...sec.querySelectorAll('[data-draw]')].filter((e) => !e.closest('[hidden]') && !e.closest('[data-when]') && e.textContent.trim() === '—' && !['note', 'posthigh', 'posthighdate', 'drop', 'nearres'].includes(e.dataset.draw));
    v.dash_left = empty.map((e) => e.dataset.draw).filter((x, i, a) => a.indexOf(x) === i);
    out.push(v);
  }
  const bar = d.querySelector('.fx-bar summary');
  const res = { tabs: out, bar: bar && bar.textContent, refresh_hidden_without_login: d.querySelector('.fx-btn').hidden, errors, fetched: fetched.length };
  if (errors.length) bad.push('page errors: ' + errors.join(' | '));
  if (!bar || !/Built/.test(bar.textContent)) bad.push('freshness strip missing');
  console.log(JSON.stringify(res, null, 1));
  w.close();
  if (bad.length) { console.error('RENDER FAILED:\n' + bad.join('\n')); process.exit(1); }
  console.log('RENDER OK: all four tabs drawn, numbers match the data, no page errors.');
})();
