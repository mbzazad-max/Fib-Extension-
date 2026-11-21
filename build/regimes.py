"""Fib tracker hit record split by market (owner, 21 Nov 2026).

Replays the engine's walk-forward backtest for every tab, for tops and (on the inverted series) bottoms, and tags each
past setup with BTC's weekly side at its C date: bull side = the last closed weekly close above both the 50W and the
100W SMA (the BTC cycle tab's Bull / Turning bull), bear side = below either (Bear / Turning bear). Writes
public/data/fibx_regime.json. Usage: python3 build/regimes.py <market-data>
"""
import sys, os, json, bisect, datetime as dt, statistics as st, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B, bottoms as BT
spec = importlib.util.spec_from_file_location('E', B.ENGINE); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


def btc_side(md):
    a, b = BT.daily_rows(md, 'data/tv/COINBASE_BTCUSD_1D.csv'), BT.daily_rows(md, 'data/binance/BTCUSDT_1D.csv')
    rows = a + [r for r in b if r[0] > a[-1][0]]
    weeks = []
    for t, h, l, c in rows:
        wk = t - dt.datetime.fromtimestamp(t, dt.UTC).weekday() * 86400
        if weeks and weeks[-1][0] == wk: weeks[-1][1] = c
        else: weeks.append([wk, c])
    ends, side = [], []
    for k in range(100, len(weeks)):
        wc = [w[1] for w in weeks[:k]]           # weeks fully closed before week k starts
        s50, s100 = sum(wc[-50:]) / 50, sum(wc[-100:]) / 100
        ends.append(weeks[k][0]); side.append('bull' if wc[-1] > s50 and wc[-1] > s100 else 'bear')
    def at(t):
        i = bisect.bisect_right(ends, t) - 1
        return side[i] if i >= 0 else None
    return at


def replay(rows, profile, inv):
    E.configure(profile)
    if inv: rows = [(t, 1e9 / o, 1e9 / l, 1e9 / h, 1e9 / c) for t, o, h, l, c in rows]
    t, o, h, l, c = [list(x) for x in zip(*rows)]
    n = len(c); sma = [None] * n; run = 0
    for i in range(n):
        run += c[i]
        if i >= 200: run -= c[i - 200]
        if i >= 199: sma[i] = run / 200
    p = E.zigzag(h, l, E.TH, c, E.CONFIRM); hist = []
    for j in range(len(p) - 3):
        (ka, a), (kb, b), (kc, cc), (kd, d) = p[j:j + 4]
        if ka != 'L' or l[cc] <= l[a] or sma[cc] is None: continue
        hist.append(dict(tc=t[cc], bars=d - cc, A=l[a], B=h[b], C=l[cc], T=h[d], r=(h[d] - l[cc]) / (h[b] - l[a]), up=c[cc] > sma[cc]))
    # time from C to the top: all completed setups; the current C as the engine picks it
    bars = sorted(x['bars'] for x in hist)
    lk, li = p[-1]
    if lk == 'H':
        cc = min(range(li + 1, n), key=lambda i: l[i]) if li + 1 < n else li; cconf = False
        top = None
    else:
        cc = li; cconf = True; top = max(range(cc, n), key=lambda i: h[i])
    bi = li if lk == 'H' else next(i for k, i in reversed(p[:-1]) if k == 'H')
    ai = next((i for k, i in reversed(p) if k == 'L' and i < bi), None)
    broken = ai is None or l[cc] <= l[ai]
    per = t[1] - t[0]
    TIME = dict(n=len(bars), p25=E.pct(bars, .25), med=st.median(bars), p75=E.pct(bars, .75), p90=E.pct(bars, .9), period=per, broken=broken,
                c_time=t[cc], c_confirmed=cconf, bars_since_c=n - 1 - cc, top_time=(t[top] if top is not None else None),
                last_time=t[-1], share_by_now=round(sum(b <= n - 1 - cc for b in bars) / len(bars), 3) if bars else None)
    out = []
    for k, x in enumerate(hist):
        prior = [y['r'] for y in hist[:k] if y['up'] == x['up']]
        if len(prior) < 15: continue
        tgt = x['C'] + st.median(prior) * (x['B'] - x['A'])
        out.append((x['tc'], x['T'] / tgt - 1))
    return out, TIME


def main():
    md = sys.argv[1]; at = btc_side(md); R = dict(made=dt.datetime.now(dt.UTC).strftime('%Y-%m-%d'), tabs={})
    for tab in B.CFG['tabs']:
        rows = B.load_rows(md, tab, None); tol = E.PROFILES[tab['profile']]['HIT_TOL']; T = {}
        for kind, inv in (('top', False), ('bottom', True)):
            g = {'bull': [0, 0], 'bear': [0, 0]}
            rp, TIME = replay(rows, tab['profile'], inv)
            for tc, e in rp:
                if inv: e = -e / (1 + e)              # error back in price terms
                s = at(tc)
                if s: g[s][0] += 1; g[s][1] += abs(e) <= tol
            T[kind + '_time'] = TIME
            T[kind] = {s: dict(n=v[0], hit=v[1], rate=round(v[1] / v[0], 3) if v[0] else None) for s, v in g.items()}
        T['now'] = at(rows[-1][0]); T['tol'] = tol
        R['tabs'][tab['id']] = T
        print(tab['id'], json.dumps(T))
    json.dump(R, open(os.path.join(B.ROOT, 'public/data/fibx_regime.json'), 'w'))


if __name__ == '__main__':
    main()
