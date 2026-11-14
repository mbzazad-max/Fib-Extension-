/* The page must be the original BTC & ETH Fib Top Tracker artifact page, unchanged, and the engine the artifact's own.
   1. reference/index.original.html must match reference/PAGE_SHA256SUMS (files/index.html of the artifact, version 11).
   2. engine/*.py must match reference/ENGINE_SHA256SUMS (claude/fibtop/ in the Trading project, 14 Nov 2026).
   3. public/index.html must be exactly: reference/artifact_wrapper.html (the head claude.ai's artifact host puts around
      every page) + d3 7.9.0 and shim.js (the Dashboard runtime the page expects) + the original page with only the text
      changes listed in reference/PAGE_EDITS.json (the data-source line per tab, approved 14 Nov 2026) + cloud.js.
   usage: node tools/check_page.js   (exit 1 on any difference) */
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const ROOT = path.resolve(__dirname, '..');
const sha = (p) => crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, p))).digest('hex');
const sums = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8').trim().split('\n').map((l) => l.trim().split(/\s+/));
let bad = 0;
for (const [want, name] of sums('reference/PAGE_SHA256SUMS')) if (sha('reference/' + name) !== want) { console.error('reference/' + name + ' changed'); bad++; }
for (const [want, name] of sums('reference/ENGINE_SHA256SUMS')) if (sha('engine/' + name) !== want) { console.error('engine/' + name + ' changed'); bad++; }
const HEAD = '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n<script src="shim.js"></script>\n';
let page = fs.readFileSync(path.join(ROOT, 'reference/index.original.html'), 'utf8');
for (const e of JSON.parse(fs.readFileSync(path.join(ROOT, 'reference/PAGE_EDITS.json'), 'utf8')).edits) {
  if (page.split(e.from).length !== 2) { console.error('PAGE_EDITS: not found exactly once: ' + e.from); process.exit(1); }
  page = page.replace(e.from, () => e.to);
}
const expected = fs.readFileSync(path.join(ROOT, 'reference/artifact_wrapper.html'), 'utf8') + HEAD + page + '\n<script src="cloud.js"></script>\n';
if (process.argv[2] === '--write') fs.writeFileSync(path.join(ROOT, 'public/index.html'), expected);
if (fs.readFileSync(path.join(ROOT, 'public/index.html'), 'utf8') !== expected) { console.error('public/index.html is not the original page plus d3, shim.js and cloud.js'); bad++; }
if (bad) process.exit(1);
console.log('Page = original + ' + JSON.parse(fs.readFileSync(path.join(ROOT, 'reference/PAGE_EDITS.json'), 'utf8')).edits.length + ' approved text edits; engine unchanged: ' + sums('reference/PAGE_SHA256SUMS')[0][0] + ' / ' + sums('reference/ENGINE_SHA256SUMS').map((x) => x[0].slice(0, 12)).join(', '));
