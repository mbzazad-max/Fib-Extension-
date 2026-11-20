#!/usr/bin/env python3
"""Build the Fib Top Tracker's 24 data files from Market-Data closed candles.

usage: python3 build/build.py <market-data dir> [--force] [--upto UNIX] [--out DIR] [--state DIR]

For each tab in config/dashboard.json:
  1. read the Market-Data CSV (time = candle open, unix s UTC; closed candles only) and drop any
     candle that has not closed yet (or that opens after --upto, used by the parity test);
  2. skip the tab if its last closed candle is the one already built (unless --force);
  3. run the unchanged engine (engine/fib_top_engine.py, closed_only input, the tab's own forecast
     log) and engine/export_dash.py in a scratch folder;
  4. check the six files, then put them in <out>/data/<prefix><name>.json and save the log.
A tab that fails keeps its last good files and log, and is listed in <out>/freshness.json.
"""
import csv, datetime as dt, json, os, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config/dashboard.json')))
ENGINE = os.path.join(ROOT, 'engine/fib_top_engine.py')
EXPORT = os.path.join(ROOT, 'engine/export_dash.py')


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def load_csv(path, period, upto, min_rows=400):
    now = time.time()
    rows = []
    with open(path, newline='') as f:
        r = csv.reader(f)
        head = next(r)
        if head[:5] != ['time', 'open', 'high', 'low', 'close']:
            raise ValueError('unexpected header ' + ','.join(head))
        for x in r:
            t = int(x[0]); o, h, l, c = map(float, x[1:5])
            if t + period > now: continue           # still forming
            if upto is not None and t > upto: continue
            if not (l <= min(o, c) and h >= max(o, c) and l > 0):
                raise ValueError('bad candle at %d' % t)
            rows.append((t, o, h, l, c))
    for a, b in zip(rows, rows[1:]):
        if b[0] <= a[0]: raise ValueError('candles out of order at %d' % b[0])
    if len(rows) < min_rows: raise ValueError('only %d closed candles' % len(rows))
    return rows


def days_from_4h(path, upto):
    """Daily candles made from closed 4H candles (UTC days whose 20:00 candle has closed; high/low/close over the day)."""
    out = {}
    for t, o, h, l, c in load_csv(path, 14400, upto, min_rows=1):
        d = t - t % 86400
        if d not in out: out[d] = [d, o, h, l, c, False]
        x = out[d]; x[2] = max(x[2], h); x[3] = min(x[3], l); x[4] = c
        if t % 86400 == 72000: x[5] = True
    return [tuple(x[:5]) for k, x in sorted(out.items()) if x[5]]


def load_rows(md, tab, upto):
    """The tab's closed candles: its file, then (USDT.D daily) days made from 4H after the file's last day; x scale."""
    rows = load_csv(os.path.join(md, tab['file']), tab['period_s'], upto, min_rows=1)
    if tab.get('then_days_from_4h'):
        last = rows[-1][0]
        rows = rows + [r for r in days_from_4h(os.path.join(md, tab['then_days_from_4h']), upto) if r[0] > last]
    k = tab.get('scale', 1)
    if k != 1: rows = [(t, o * k, h * k, l * k, c * k) for t, o, h, l, c in rows]
    if len(rows) < 400: raise ValueError('only %d closed candles' % len(rows))
    return rows


def fmt(t, profile):
    return dt.datetime.fromtimestamp(t, dt.UTC).strftime('%Y-%m-%d' if profile == 'D' else '%Y-%m-%d %H:%M')


def build_tab(tab, rows, out, state):
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, 'in.json')
        json.dump({'closed_only': True, 'bars': {k: [r[i] for r in rows] for i, k in enumerate('tohlc')}}, open(inp, 'w'))
        log = os.path.join(tmp, 'log.json')
        src_log = os.path.join(state, os.path.basename(tab['log']))
        if os.path.exists(src_log): shutil.copy(src_log, log)
        env = dict(os.environ, FIB_SYMBOL=tab['symbol'])
        env.pop('FIB_CONFIRM', None); env.pop('FIB_RULE_NOTE', None)
        st = os.path.join(tmp, 'state.json'); od = os.path.join(tmp, 'out')
        for cmd in ([sys.executable, ENGINE, inp, log, st, tab['profile']], [sys.executable, EXPORT, st, od]):
            p = subprocess.run(cmd, env=env, capture_output=True, text=True, cwd=tmp)
            if p.returncode: raise RuntimeError(os.path.basename(cmd[1]) + ' failed: ' + (p.stderr.strip().splitlines() or ['?'])[-1])
        files = {}
        for name in CFG['datasets']:
            v = json.load(open(os.path.join(od, name + '.json')))
            if not isinstance(v, list) or not v: raise RuntimeError(name + '.json is empty')
            files[name] = v
        s = files['summary'][0]
        if s['live_date'] != fmt(rows[-1][0], tab['profile']): raise RuntimeError('summary is not for the last candle')
        if s['symbol'] != tab['symbol'] or s['timeframe'] != ('1D' if tab['profile'] == 'D' else '4H'):
            raise RuntimeError("summary symbol/timeframe mismatch: %s %s" % (s.get("symbol"), s.get("timeframe")))
        os.makedirs(os.path.join(out, 'data'), exist_ok=True)
        for name, v in files.items():   # same bytes export_dash.py wrote
            shutil.copy(os.path.join(od, name + '.json'), os.path.join(out, 'data', tab['prefix'] + name + '.json'))
        os.makedirs(state, exist_ok=True)
        shutil.copy(log, src_log)
        return s


def main():
    md = sys.argv[1]
    force = '--force' in sys.argv
    upto = int(arg('--upto')) if arg('--upto') else None
    out = arg('--out', os.path.join(ROOT, 'public'))
    state = arg('--state', os.path.join(ROOT, 'state'))
    built_p = os.path.join(state, 'built.json')
    built = json.load(open(built_p)) if os.path.exists(built_p) else {}
    fresh_p = os.path.join(out, 'freshness.json')
    old = json.load(open(fresh_p)) if os.path.exists(fresh_p) else {}
    series, kept, done, failed = [], [], [], []
    for tab in CFG['tabs']:
        info = dict(id=tab['id'], title=tab['title'], symbol=tab['symbol'], tf='1D' if tab['profile'] == 'D' else '4H',
                    series=tab['series'], source=tab.get('source', 'Binance spot via Market-Data'), period_s=tab['period_s'])
        try:
            rows = load_rows(md, tab, upto)
            info.update(rows=len(rows), last_close=rows[-1][0] + tab['period_s'])
            if not force and built.get(tab['id']) == rows[-1][0]:
                info['built_from'] = built.get(tab['id'])
                series.append(info); continue
            s = build_tab(tab, rows, out, state)
            built[tab['id']] = rows[-1][0]
            info.update(built_from=rows[-1][0], status=s['status'])
            done.append('%s %s (%s)' % (tab['title'], s['live_date'], s['status_label']))
        except Exception as e:  # keep the last good files and log for this tab
            why = str(e)
            kept.append(dict(id=tab['id'], why=why)); failed.append(tab['title'])
            info['built_from'] = built.get(tab['id'])
            print('::warning::%s kept its last good data: %s' % (tab['title'], why))
        series.append(info)
    if not done and not kept and old:
        print('Nothing new: every tab is already built from its last closed candle.')
        return 0
    os.makedirs(state, exist_ok=True)
    json.dump(built, open(built_p, 'w'), indent=1, sort_keys=True)
    res = ('Rebuilt: ' + '; '.join(done) + '.') if done else 'No tab rebuilt.'
    if failed: res += ' Kept last good data: ' + ', '.join(failed) + '.'
    F = dict(generated=dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC'), checked_at=int(time.time()),
             series=series, kept=kept, last_result=res)
    json.dump(F, open(fresh_p, 'w'), indent=1)
    print(res)
    return 1 if failed and not done and len(failed) == len(CFG['tabs']) else 0


if __name__ == '__main__':
    sys.exit(main())
