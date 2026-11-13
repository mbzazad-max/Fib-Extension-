#!/usr/bin/env python3
"""Parity test: the artifact's own refresh path versus this repo's build, on the same candles.

usage: python3 tests/parity.py <market-data dir> <drive dir>

<drive dir> holds the engine inputs the artifact's scheduled refresh makes from the Google Drive files
(drive_to_json.py output): d.json, h4.json, ethd.json, eth4h.json.
For every tab both paths start from the same forecast logs (state/), are cut at the same last closed candle,
and run the same engine. Path A = the artifact's commands (engine on the Drive JSON, then export_dash.py).
Path B = build/build.py on Market-Data. All 24 files must match, except the "generated" clock stamp.
It also checks that the candles themselves are identical wherever both sources have them.
"""
import csv, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config/dashboard.json')))
MD, DRIVE = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
DRIVE_FILE = {'btc_d': 'd.json', 'btc_4h': 'h4.json', 'eth_d': 'ethd.json', 'eth_4h': 'eth4h.json'}
fails = 0
with tempfile.TemporaryDirectory() as tmp:
    upto = {}
    for tab in CFG['tabs']:
        b = json.load(open(os.path.join(DRIVE, DRIVE_FILE[tab['id']])))['bars']
        D = {t: (b['o'][i], b['h'][i], b['l'][i], b['c'][i]) for i, t in enumerate(b['t'])}
        with open(os.path.join(MD, tab['file'])) as f:
            M = {int(r[0]): tuple(map(float, r[1:5])) for r in list(csv.reader(f))[1:]}
        common = sorted(set(D) & set(M))
        diff = [t for t in common if D[t] != M[t]]
        upto[tab['id']] = common[-1]
        print('%-9s candles: Drive %d, Market-Data %d, shared %d, different %d, compared up to %d' % (tab['title'], len(D), len(M), len(common), len(diff), common[-1]))
        fails += bool(diff)
        # path A: the artifact's refresh commands
        a = os.path.join(tmp, 'A', tab['id']); os.makedirs(a)
        keep = [i for i, t in enumerate(b['t']) if t <= common[-1]]
        json.dump({'closed_only': True, 'bars': {k: [b[k][i] for i in keep] for k in 'tohlc'}}, open(os.path.join(a, 'in.json'), 'w'))
        shutil.copy(os.path.join(ROOT, tab['log']), os.path.join(a, 'log.json'))
        env = dict(os.environ, FIB_SYMBOL=tab['symbol'])
        subprocess.run([sys.executable, os.path.join(ROOT, 'engine/fib_top_engine.py'), 'in.json', 'log.json', 'st.json', tab['profile']], cwd=a, env=env, check=True, capture_output=True)
        subprocess.run([sys.executable, os.path.join(ROOT, 'engine/export_dash.py'), 'st.json', 'out'], cwd=a, env=env, check=True, capture_output=True)
    # path B: build.py, one tab at a time so each tab is cut at its own candle
    for tab in CFG['tabs']:
        out, state = os.path.join(tmp, 'B_' + tab['id']), os.path.join(tmp, 'Bstate_' + tab['id'])
        shutil.copytree(os.path.join(ROOT, 'state'), state)   # fresh copy of the logs for every call
        if os.path.exists(os.path.join(state, 'built.json')): os.remove(os.path.join(state, 'built.json'))
        p = subprocess.run([sys.executable, os.path.join(ROOT, 'build/build.py'), MD, '--force', '--upto', str(upto[tab['id']]), '--out', out, '--state', state],
                           capture_output=True, text=True)
        if p.returncode: print(p.stdout, p.stderr); sys.exit(1)
    for tab in CFG['tabs']:
        for name in CFG['datasets']:
            A = json.load(open(os.path.join(tmp, 'A', tab['id'], 'out', name + '.json')))
            B = json.load(open(os.path.join(tmp, 'B_' + tab['id'], 'data', tab['prefix'] + name + '.json')))
            if name == 'summary':
                for x in (A, B): x[0].pop('generated')
            ok = A == B
            fails += not ok
            print('  %-9s %-10s %s' % (tab['title'], name, 'identical' if ok else 'DIFFERENT'))
print('PARITY OK: all 24 files identical (except the generated time)' if not fails else 'PARITY FAILED (%d)' % fails)
sys.exit(1 if fails else 0)
