#!/usr/bin/env python3
"""Fib BOTTOM tracker (owner, 21 Nov 2026): the mirror of the Fib Top Tracker, for every tab.

The artifact's engine (engine/fib_top_engine.py, unchanged and checksum-checked) only reads BULLISH A-B-C swings and
projects the next TOP. Here it runs on INVERTED candles (K / price, with high and low swapped), where a falling A-B-C
(A = swing high, B = swing low, C = lower high) looks like a rising one. Its projected "top" in that space is the
projected next LOW in price; its zone is the buy zone; its forecast log, walk-forward backtest, early-rejection
warnings and low-strength badges all carry over (an early "rejection" becomes an early bounce above the buy zone).
Every number is mapped back with price = K / value. K is fixed per tab (config "invert_k"), so the log stays
consistent from run to run.

usage: python3 build/bottoms.py <market-data dir> [--force]
Writes public/data/fibx_<tab id>.json (key "bottom") and state/bottom_log_<tab id>.json. A tab that fails keeps its
last good file and log; the run exits 0 so the dashboard still deploys.
"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'build'))
import build as B   # load_rows, CFG, ENGINE (the tab list and the candle rules are shared with build.py)

PUB = os.path.join(ROOT, 'public', 'data')
STATE = os.path.join(ROOT, 'state')
# K per tab: price = K / value. Chosen so inverted values stay in the hundreds of thousands to millions (the engine
# rounds prices to whole numbers). Never change a K once a log exists: the log stores inverted values.
K_DEFAULT = {'BTC': 1e10, 'ETH': 1e9, 'SOL': 1e7, 'BNB': 1e8, 'USDT.D': 1e9}
STATUS = {
    'pullback': ('Bounce forming', 'Price is bouncing off swing low B; C (a lower high) is still provisional.'),
    'rallying': ('Decline under way', 'C (a lower high) is confirmed and price is falling towards the projected low.'),
    'in_zone': ('Inside the buy zone', 'The low so far is inside the projected buy zone.'),
    'above_zone': ('Below the buy zone', 'The low so far is already below the projected buy zone.'),
    'broken': ('Structure broken', 'Price broke above swing high A. No valid falling setup until a new lower high forms.'),
    'early_watch': ('Early bounce watch', 'Price stalled above the buy zone and has bounced off its low since C.'),
    'early_rejection': ('Early bounce warning', 'Price stalled above the buy zone and has bounced clearly off its low: the low may already be in, above the zone.'),
}


def coin(tab):
    s = tab['symbol'].split(':')[-1]
    return 'USDT.D' if 'USDT.D' in s else s.replace('USDT', '')


def run_engine(tab, rows, K, logp):
    inv = [(t, K / o, K / l, K / h, K / c) for t, o, h, l, c in rows]     # high <-> low swap
    with tempfile.TemporaryDirectory() as tmp:
        inp = os.path.join(tmp, 'in.json')
        json.dump({'closed_only': True, 'bars': {k: [r[i] for r in inv] for i, k in enumerate('tohlc')}}, open(inp, 'w'))
        log = os.path.join(tmp, 'log.json')
        if os.path.exists(logp): shutil.copy(logp, log)
        env = dict(os.environ, FIB_SYMBOL=tab['symbol'])
        env.pop('FIB_CONFIRM', None); env.pop('FIB_RULE_NOTE', None)
        st = os.path.join(tmp, 'state.json')
        p = subprocess.run([sys.executable, B.ENGINE, inp, log, st, tab['profile']], env=env, capture_output=True, text=True, cwd=tmp)
        if p.returncode: raise RuntimeError('engine failed: ' + (p.stderr.strip().splitlines() or ['?'])[-1])
        s = json.load(open(st))
        shutil.copy(log, logp)
        return s


def mapped(s, K, scale, rows=None, profile='D'):
    """The engine state for the inverted series, turned back into prices (and / scale for USDT.D)."""
    P = lambda v: None if v is None else round(K / v / scale, 6 if scale != 1 else 2)
    su, bt, lv = s.get('setup'), s['backtest'], s['live']
    out = dict(status=s['status'], status_label=STATUS.get(s['status'], (s['status'], ''))[0],
               note=STATUS.get(s['status'], ('', ''))[1], live_date=lv['date'], live_close=P(lv['close']),
               timeframe=s['timeframe'], zigzag=s['zigzag'], hit_tol=s['hit_tolerance'])
    if su:
        out.update(a_date=su['a'], A=P(su['A']), b_date=su['b'], B=P(su['B']), c_date=su['c'], C=P(su['C']),
                   c_confirmed=su['c_confirmed'], target=P(su['target']),
                   zone=[P(su['zone'][1]), P(su['zone'][0])],          # lowest .. highest price
                   ratio=round(su['ratio'], 3),
                   regime=('price below its trend (inverted 200-bar SMA)' if su['regime'] == 'above' else 'price above its trend'),
                   calib_n=su['calib']['n'], reach_1_pct=round(su['calib']['reach1'], 3),
                   levels=sorted([dict(ratio=float(r), price=P(v)) for r, v in su['levels'].items()], key=lambda x: -x['price']),
                   low_so_far=P(su['top_so_far']) if su.get('top_so_far') else None,
                   post_c_low=P(su['post_c_high']) if su.get('post_c_high') else None, post_c_low_date=su.get('post_c_high_date'),
                   bounce_from_low=(round(su['post_c_high'] / lv['close'] - 1, 4) if su.get('post_c_high') else None),
                   to_target_pct=round(lv['close'] / su['target'] - 1, 4),      # price target / price - 1 (negative = below)
                   rsi7_inverted=su.get('rsi7'), rsi_state={'overbought': 'oversold (RSI7 under 30)', 'hooked': 'hooked back above 30', 'neutral': 'not oversold since C'}.get(su.get('rsi_state')),
                   support=[dict(price=P(x['price']), touches=x['touches'], last=x['last'], in_zone=x['in_zone'], dist=round(lv['close'] / x['price'] - 1, 4)) for x in (su.get('resistance') or [])],
                   confluence=su.get('confluence'))
    if s['status'] == 'broken' and rows:
        # what restarts it: the last swing high, the lowest low since, and the bounce that would confirm that low as B
        hi = [x for x in s['pivots'] if x['k'] == 'L']     # inverted lows = price highs
        last_hi = hi[-1] if hi else None
        if last_hi:
            t0 = next((i for i, r in enumerate(rows) if B.fmt(r[0], profile) == last_hi['d']), None)
            if t0 is not None:
                lo_i = min(range(t0, len(rows)), key=lambda i: rows[i][3])
                th = s['zigzag']
                out.update(last_high=P(last_hi['v']), last_high_date=last_hi['d'], low_since=round(rows[lo_i][3] / scale, 6 if scale != 1 else 2),
                           low_since_date=B.fmt(rows[lo_i][0], profile), confirm_bounce_at=round(rows[lo_i][3] * (1 + th) / scale, 6 if scale != 1 else 2))
    out['backtest'] = dict(n=bt['n'], within_tol=bt['within_tol'], within_pct=round(bt['within_tol'] / bt['n'], 3) if bt['n'] else None,
                           within_half_pct=round(bt['within_half'] / bt['n'], 3) if bt['n'] else None, median_err=round(bt['median_err'], 4),
                           recent_n=bt.get('recent_n'), recent_within=bt.get('recent_within'),
                           lower_low_pct=round(bt['higher_high'] / bt['setups'], 3) if bt['setups'] else None, setups=bt['setups'],
                           early={k: dict(fired=v['fired'], correct=v['correct'], precision=(round(v['precision'], 3) if v['precision'] is not None else None)) for k, v in bt['early'].items()},
                           recent=[dict(date=w['date'], target=P(w['target']), low=P(w['top']), err=round(-w['err'] / (1 + w['err']), 4)) for w in bt['recent']][::-1])
    ls = s['live_stats']
    out['live_stats'] = dict(issued=ls['issued'], open=ls['open'], scored=ls['scored'], hits=ls['hits'], invalidated=ls['invalidated'])
    out['forecasts'] = [dict(opened=f['opened'], a=f['a'], b=f['b'], c=f['c'], A=P(f['A']), B=P(f['B']), C=P(f['C']), target=P(f['target']),
                             zone=[P(f['zone'][1]), P(f['zone'][0])], state=f['state'], low=P(f.get('top')), low_date=f.get('top_date'),
                             hit=f.get('hit'), closed=f.get('closed'), reason=f.get('reason', ''), zone_touched=f.get('zone_touched'),
                             min_low=P(f.get('max_high'))) for f in s['forecasts']][:12]
    out['pivots'] = [dict(k={'H': 'L', 'L': 'H'}[x['k']], d=x['d'], v=P(x['v'])) for x in s['pivots']]
    return out


def main():
    md = sys.argv[1]
    force = '--force' in sys.argv
    built_p = os.path.join(STATE, 'built_bottoms.json')
    built = json.load(open(built_p)) if os.path.exists(built_p) else {}
    done, kept = [], []
    for tab in B.CFG['tabs']:
        try:
            rows = B.load_rows(md, tab, None)
            outp = os.path.join(PUB, 'fibx_' + tab['id'] + '.json')
            if not force and built.get(tab['id']) == rows[-1][0] and os.path.exists(outp):
                continue
            K = tab.get('invert_k') or K_DEFAULT[coin(tab)]
            s = run_engine(tab, rows, K, os.path.join(STATE, 'bottom_log_' + tab['id'] + '.json'))
            if s['live']['date'] != B.fmt(rows[-1][0], tab['profile']): raise RuntimeError('state is not for the last candle')
            prev = json.load(open(outp)) if os.path.exists(outp) else {}
            prev['bottom'] = dict(mapped(s, K, tab.get('scale', 1), rows, tab['profile']), invert_k=K, unit=('pct' if tab.get('scale', 1) != 1 else 'usd'),
                                  generated=dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC'))
            os.makedirs(PUB, exist_ok=True)
            json.dump(prev, open(outp, 'w'))
            built[tab['id']] = rows[-1][0]
            done.append('%s %s (%s)' % (tab['title'], prev['bottom']['live_date'], prev['bottom']['status_label']))
        except Exception as e:
            kept.append(tab['title'])
            print('::warning::Fib bottom %s kept its last good data: %s' % (tab['title'], e))
    json.dump(built, open(built_p, 'w'), indent=1, sort_keys=True)
    print('Fib bottoms: ' + ('; '.join(done) if done else 'nothing new') + ('. Kept: ' + ', '.join(kept) if kept else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
