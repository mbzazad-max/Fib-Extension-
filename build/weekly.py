"""Weekly cycle-scale Fib projection, context only (owner, 21 Nov 2026).

The same ABC idea as the trackers on closed Monday weeks with a 25% zigzag: A = swing low, B = swing high, C = higher low,
projected top = C + median past (top - C) / (B - A) x (B - A), zone = 25th-75th percentile. Bottoms on the mirror image.
Few weekly setups exist (a dozen or two per coin), so this is shown as context, not as a call.
Output public/data/fibx_weekly.json keyed by coin. Usage: python3 build/weekly.py <market-data>
"""
import sys, os, json, datetime as dt, statistics as st, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B, bottoms as BT
spec = importlib.util.spec_from_file_location('E', B.ENGINE); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
TH, TOL = 0.25, 0.15
SRC = {'BTC': None, 'ETH': 'data/binance/ETHUSDT_1D.csv', 'SOL': 'data/binance/SOLUSDT_1D.csv',
       'BNB': 'data/binance/BNBUSDT_1D.csv', 'USDT.D': 'data/tv/CRYPTOCAP_USDT.D_1D.csv'}


def weeks(rows):
    W = []
    for t, h, l, c in rows:
        wk = t - dt.datetime.fromtimestamp(t, dt.UTC).weekday() * 86400
        if W and W[-1][0] == wk: W[-1][1] = max(W[-1][1], h); W[-1][2] = min(W[-1][2], l); W[-1][3] = c; W[-1][4] = t
        else: W.append([wk, h, l, c, t])
    if W[-1][4] != W[-1][0] + 6 * 86400: W = W[:-1]
    return W


def run(W, inv):
    f = (lambda v: 1e9 / v) if inv else (lambda v: v)
    t = [w[0] for w in W]
    h = [f(w[2]) if inv else w[1] for w in W]; l = [f(w[1]) if inv else w[2] for w in W]; c = [f(w[3]) for w in W]
    g = vars(E); g['TH'] = TH
    p = E.zigzag(h, l, TH, c, 'wick'); n = len(c)
    hist = []
    for j in range(len(p) - 3):
        (ka, a), (kb, b), (kc, cc), (kd, d) = p[j:j + 4]
        if ka != 'L' or l[cc] <= l[a]: continue
        hist.append(dict(a=a, b=b, c=cc, d=d, A=l[a], B=h[b], C=l[cc], T=h[d], r=(h[d] - l[cc]) / (h[b] - l[a])))
    wf = []
    for k, x in enumerate(hist):
        prior = [y['r'] for y in hist[:k]]
        if len(prior) < 5: continue
        tgt = x['C'] + st.median(prior) * (x['B'] - x['A'])
        wf.append(x['T'] / tgt - 1)
    if inv: wf = [-e / (1 + e) for e in wf]
    back = (lambda v: 1e9 / v) if inv else (lambda v: v)
    D = lambda i: dt.datetime.fromtimestamp(t[i], dt.UTC).strftime('%Y-%m-%d')
    lk, li = p[-1]
    if lk == 'H':
        bi = li; cc = min(range(bi + 1, n), key=lambda i: l[i]) if bi + 1 < n else bi; conf = False
    else:
        cc = li; bi = next(i for k, i in reversed(p[:-1]) if k == 'H'); conf = True
    ai = next((i for k, i in reversed(p) if k == 'L' and i < bi), None)
    cur = None
    if ai is not None and l[cc] > l[ai] and len(hist) >= 5:
        rs = [x['r'] for x in hist]; L = h[bi] - l[ai]
        z = sorted([back(l[cc] + E.pct(rs, .25) * L), back(l[cc] + E.pct(rs, .75) * L)])
        cur = dict(a=D(ai), A=back(l[ai]), b=D(bi), B=back(h[bi]), c=D(cc), C=back(l[cc]), c_confirmed=conf,
                   target=back(l[cc] + st.median(rs) * L), zone=z)
    elif ai is not None:
        cur = dict(broken=True, a=D(ai), A=back(l[ai]), low=back(l[cc]), low_date=D(cc))
    past = [dict(c=D(x['c']), C=back(x['C']), top=D(x['d']), T=back(x['T'])) for x in hist][-6:]
    return dict(setups=len(hist), tested=len(wf), within=sum(abs(e) <= TOL for e in wf), tol=TOL,
                median_err=round(st.median(abs(e) for e in wf), 3) if wf else None, now=cur, past=past,
                last_week=D(n - 1), close=back(c[-1]))


def main():
    md = sys.argv[1]; out = dict(made=dt.datetime.now(dt.UTC).strftime('%Y-%m-%d'), zigzag=TH, coins={})
    for k, path in SRC.items():
        try:
            if k == 'BTC':
                a, b = BT.daily_rows(md, 'data/tv/COINBASE_BTCUSD_1D.csv'), BT.daily_rows(md, 'data/binance/BTCUSDT_1D.csv')
                rows = a + [r for r in b if r[0] > a[-1][0]]
            else: rows = BT.daily_rows(md, path)
            W = weeks(rows); out['coins'][k] = dict(top=run(W, False), bottom=run(W, True))
            print(k, json.dumps(out['coins'][k])[:600])
        except Exception as e: print('::warning::weekly %s skipped: %s' % (k, e))
    json.dump(out, open(os.path.join(B.ROOT, 'public/data/fibx_weekly.json'), 'w'))


if __name__ == '__main__':
    main()
