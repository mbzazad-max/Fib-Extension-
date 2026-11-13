#!/usr/bin/env python3
"""BTC Fib Top Tracker engine.

Usage: python3 fib_top_engine.py <ohlcv.json> <log.json> <out_state.json> [D|4H]

Profile D  (default): daily bars from 2018, 10% swings.
Profile 4H: 4-hour bars (TradingView serves from Jan 2024), 5% swings. Pass
h4_archive.json as a 5th argument to add the 2017-2024 Binance 4H setups to the
calibration and backtest:  ... state.json 4H h4_archive.json Every
other threshold is scaled by the same factor, so the 4H rules keep the daily
rules' proportions (hit tolerance = swing size, warnings at 0.5x / 0.7x, etc).

ohlcv.json : {bars:{t,o,h,l,c}} from drive_to_json.py (closed candles only, closed_only: true),
             or a TradingView get-ohlcv result whose last bar is still forming.
log.json   : forecast log from previous runs (created if missing). Updated in place.
out_state  : full state for the tracker page.

Model
- Zigzag on highs/lows (daily 10%, 4H 5%), wick-based (CONFIRM in PROFILES).
- Low strength badge for A and C: weak (no candle has CLOSED TH above the low
  yet), confirmed (one has), strong (confirmed and a higher low than the
  previous swing low), each shown with its historical fakeout rate (low broken
  before a further TH rally). Wick-only lows failed ~2 in 3 times; close-
  confirmed lows ~1 in 3.
- Bullish ABC: A swing low, B swing high, C higher low (C > A).
- Target = C + r * (B - A), r = median extension of all completed historical
  setups in the same trend regime (C close above / below 200-day SMA).
  Zone = 25th..75th percentile.
- A forecast is keyed by its A, B, C dates. If price makes a new low under C,
  the forecast is closed as "re-anchored" and a new one opens. If price breaks
  under A the structure is broken and no target is issued until a new higher
  low forms. When the zigzag confirms the next swing high after C, the forecast
  is scored: hit if the actual top is within +/-10% of the target.
"""
import json, sys, statistics as st, datetime as dt

PROFILES = {
    # TH zigzag swing, HIT_TOL score band, WATCH/WARN early-rejection drops,
    # MIN_RALLY arm level, NEAR confluence distance, SR_W resistance cluster width
    # CONFIRM: how a swing low confirms for the ABC structure.
    #   'wick'  = a candle HIGH reaches TH above the low (used: tested best for targets)
    #   'close' = a candle CLOSES TH above the low. Tested 5 Nov 2026: replay hit rate
    #             fell (daily 71.8% -> 64.2%, 4H 63.8% -> 61.0%) and re-plans rose, so the
    #             close test is used for the low strength badge instead, not the structure.
    'D':  dict(TH=0.10, HIT_TOL=0.10, WATCH=0.05, WARN=0.07, MIN_RALLY=0.03, NEAR=0.03, SR_W=0.02,
               FMT='%Y-%m-%d', TF='1D', BAR='day', CONFIRM='wick'),
    '4H': dict(TH=0.05, HIT_TOL=0.05, WATCH=0.025, WARN=0.035, MIN_RALLY=0.015, NEAR=0.015, SR_W=0.01,
               FMT='%Y-%m-%d %H:%M', TF='4H', BAR='4H bar', CONFIRM='wick'),
}
RSI_N = 7         # RSI period for zone confluence
RULE_NOTE = ''    # set once when a rule change re-draws the anchors, used as the close reason
RECENT = '2024-03-01'  # start of the "recent period" hit rate shown beside the long-run one

def configure(name):
    g = globals()
    for k, v in PROFILES[name].items(): g[k] = v
    g['PROFILE'] = name

import os as _os
# user's Google Drive files <BASE>USDT_D.xlsx / <BASE>USDT_4H.xlsx (Binance spot).
# Default BTC; set FIB_SYMBOL=BINANCE:ETHUSDT for the ETH tabs (same rules, own forecast log).
SYMBOL = _os.environ.get('FIB_SYMBOL', 'BINANCE:BTCUSDT')
configure('D')

def load(path):
    j = json.load(open(path))
    b = j['bars']
    return b['t'], b['o'], b['h'], b['l'], b['c']

def closed_only(path):
    """True when the file holds closed candles only (Google Drive export), so the
    last row is not a forming candle and must not be dropped."""
    return bool(json.load(open(path)).get('closed_only'))

def day(ts):
    return dt.datetime.fromtimestamp(ts, dt.UTC).strftime(FMT)

def zigzag_conf(h, l, th, c=None, confirm='wick'):
    """Zigzag swings as (kind, index_of_extreme, index_of_confirming_bar).
    Lows confirm on a CLOSE th above the low when confirm == 'close'."""
    up_src = c if (confirm == 'close' and c is not None) else h
    piv, trend, hi, lo = [], 0, 0, 0
    for i in range(1, len(h)):
        if trend >= 0:
            if h[i] > h[hi]: hi = i
            if l[i] < h[hi] * (1 - th):
                piv.append(('H', hi, i)); trend = -1; lo = i; continue
        if trend <= 0:
            if l[i] < l[lo]: lo = i
            if up_src[i] > l[lo] * (1 + th):
                piv.append(('L', lo, i)); trend = 1; hi = i
    p = []
    for k, i, cf in piv:
        if p and p[-1][0] == k:
            if (k == 'H' and h[i] > h[p[-1][1]]) or (k == 'L' and l[i] < l[p[-1][1]]):
                p[-1] = (k, i, cf)
        else:
            p.append((k, i, cf))
    return p

def zigzag(h, l, th, c=None, confirm='wick'):
    return [(k, i) for k, i, _ in zigzag_conf(h, l, th, c, confirm)]

def low_fakeouts(h, l, c, th):
    """Historical fakeout rate per low-strength badge. A fakeout = price trades
    below the low before rallying a further th (to low * (1 + 2*th)), measured
    from the bar the badge was first earned.
      weak      : a wick reached th above the low but no candle had closed there yet
      confirmed : a candle closed th above the low
      strong    : confirmed, and a higher low than the previous swing low"""
    n = len(c)
    def outcome(L, start):
        for q in range(start + 1, n):
            if l[q] < L: return 1
            if h[q] >= L * (1 + 2 * th): return 0
        return None
    res = {'weak': [], 'confirmed': [], 'strong': []}
    for k, i, cf in zigzag_conf(h, l, th, c, 'wick'):        # wick-only stage
        if k == 'L' and c[cf] <= l[i] * (1 + th):
            o = outcome(l[i], cf)
            if o is not None: res['weak'].append(o)
    sw = zigzag_conf(h, l, th, c, 'close')
    prev_low = None
    for k, i, cf in sw:
        if k != 'L': continue
        o = outcome(l[i], cf)
        if o is not None:
            res['confirmed'].append(o)
            if prev_low is not None and l[i] > prev_low: res['strong'].append(o)
        prev_low = l[i]
    return {b: dict(n=len(v), fakeouts=sum(v)) for b, v in res.items()}

def rsi_wilder(c, n=7):
    out = [None] * len(c)
    if len(c) <= n: return out
    g = [max(c[i] - c[i - 1], 0) for i in range(1, len(c))]
    d = [max(c[i - 1] - c[i], 0) for i in range(1, len(c))]
    ag, ad = sum(g[:n]) / n, sum(d[:n]) / n
    out[n] = 100 if ad == 0 else 100 - 100 / (1 + ag / ad)
    for i in range(n + 1, len(c)):
        ag = (ag * (n - 1) + g[i - 1]) / n
        ad = (ad * (n - 1) + d[i - 1]) / n
        out[i] = 100 if ad == 0 else 100 - 100 / (1 + ag / ad)
    return out

def ema(c, n=200):
    out = [None] * len(c); k = 2 / (n + 1)
    if len(c) < n: return out
    e = sum(c[:n]) / n; out[n - 1] = e
    for i in range(n, len(c)):
        e = c[i] * k + e * (1 - k); out[i] = e
    return out

def sr_levels(h, l, p, t):
    """Cluster major swing highs/lows (zigzag pivots) within 2% into levels."""
    pts = sorted((h[i] if k == 'H' else l[i], k, day(t[i])) for k, i in p)
    cl = []
    for v, k, d in pts:
        if cl and v <= cl[-1]['lo'] * (1 + SR_W): cl[-1]['m'].append((v, k, d))
        else: cl.append(dict(lo=v, m=[(v, k, d)]))
    out = []
    for x in cl:
        vs = [m[0] for m in x['m']]
        out.append(dict(price=round(sum(vs) / len(vs)), touches=len(vs),
                        last=max(m[2] for m in x['m']),
                        kinds=''.join(sorted(set(m[1] for m in x['m'])))))
    return out

def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]

def load_archive(path):
    """Pre-2024 4H setups computed from Binance history (see h4_archive.json)."""
    if not path: return None
    a = json.load(open(path))
    f = lambda k: [float(x) for x in a[k].split()]
    return dict(r={True: f('r_up'), False: f('r_dn')}, errs=f('errs'), meta=a)

def main(ohlcv, logp, outp, archive=None):
    ARC = load_archive(archive)
    AR = ARC['r'] if ARC else {True: [], False: []}
    t, o, h, l, c = load(ohlcv)
    live = dict(date=day(t[-1]), close=c[-1], high=h[-1], low=l[-1])
    # pivots use closed bars only: drop the forming bar unless the file is closed-only
    if not closed_only(ohlcv):
        t, o, h, l, c = t[:-1], o[:-1], h[:-1], l[:-1], c[:-1]
    n = len(c)
    D = lambda i: day(t[i])
    sma = [None] * n
    for i in range(199, n):
        sma[i] = sum(c[i - 199:i + 1]) / 200
    p = zigzag(h, l, TH, c, CONFIRM)
    idx = {D(i): i for i in range(n)}
    r7, e200 = rsi_wilder(c, RSI_N), ema(c, 200)

    # completed historical setups
    hist = []
    for j in range(len(p) - 3):
        (ka, a), (kb, b), (kc, cc), (kd, d) = p[j:j + 4]
        if ka != 'L' or l[cc] <= l[a] or sma[cc] is None:
            continue
        if ARC and D(d) < ARC['meta']['cutoff']:
            continue  # covered by the archive
        A, B, C, T = l[a], h[b], l[cc], h[d]
        hist.append(dict(a=D(a), b=D(b), c=D(cc), top_date=D(d), A=A, B=B, C=C, top=T,
                         r=(T - C) / (B - A), up=c[cc] > sma[cc]))

    def calib(up, upto=None):
        rs = AR[up] + [x['r'] for x in hist if x['up'] == up and (upto is None or x['top_date'] < upto)]
        if len(rs) < 10:
            rs = AR[True] + AR[False] + [x['r'] for x in hist if upto is None or x['top_date'] < upto]
        return dict(n=len(rs), median=st.median(rs), p25=pct(rs, .25), p75=pct(rs, .75),
                    reach1=sum(r >= 1 for r in rs) / len(rs))

    # walk-forward backtest (same regime filter as today's)
    wf = []
    for k, x in enumerate(hist):
        prior = AR[x['up']] + [y['r'] for y in hist[:k] if y['up'] == x['up']]
        if len(prior) < 15: continue
        m, lo_, hi_ = st.median(prior), pct(prior, .25), pct(prior, .75)
        L = x['B'] - x['A']
        tgt = x['C'] + m * L
        wf.append(dict(date=x['top_date'], target=round(tgt), top=round(x['top']),
                       err=x['top'] / tgt - 1,
                       inzone=x['C'] + lo_ * L <= x['top'] <= x['C'] + hi_ * L))
    # early-rejection warning backtest: price stalls below the zone low and
    # closes WATCH / WARN below its post-C high, before the 10% confirmation
    ew = {}
    for lvl, dip in (('watch', WATCH), ('warn', WARN)):
        fired = ok = 0
        for k, x in enumerate(hist):
            prior = AR[x['up']] + [y['r'] for y in hist[:k] if y['up'] == x['up']]
            if len(prior) < 15: continue
            A, B, C, T = x['A'], x['B'], x['C'], x['top']
            zlo = C + pct(prior, .25) * (B - A)
            ic, itop = idx[x['c']], idx[x['top_date']]
            end = itop
            while end < n and l[end] > T * (1 - TH): end += 1
            run = C
            for i in range(ic + 1, min(end + 1, n)):
                run = max(run, h[i])
                if run >= zlo: break
                if run > C * (1 + MIN_RALLY) and c[i] <= run * (1 - dip):
                    fired += 1; ok += T < zlo; break
        if ARC:
            m = ARC['meta']['ew']; fired += m[lvl + '_fired']; ok += m[lvl + '_correct']
        ew[lvl] = dict(fired=fired, correct=ok, precision=ok / fired if fired else None)

    am = ARC['meta'] if ARC else dict(wf_n=0, within_tol=0, within_half=0, higher_high=0, setups=0)
    allerr = (ARC['errs'] if ARC else []) + [w['err'] for w in wf]
    bt = dict(n=am['wf_n'] + len(wf), early=ew,
              within_tol=am['within_tol'] + sum(abs(w['err']) <= HIT_TOL for w in wf),
              within_half=am['within_half'] + sum(abs(w['err']) <= HIT_TOL / 2 for w in wf),
              median_err=st.median(abs(e) for e in allerr),
              higher_high=am['higher_high'] + sum(x['top'] > x['B'] for x in hist),
              setups=am['setups'] + len(hist),
              recent_n=sum(w['date'] >= RECENT for w in wf),
              recent_within=sum(w['date'] >= RECENT and abs(w['err']) <= HIT_TOL for w in wf),
              history=('Binance 4H 2017-2024 archive + TradingView' if ARC else 'single series'),
              recent=wf[-10:])

    # ---- current setup
    last_k, last_i = p[-1]
    setup, status, note = None, None, ''
    if last_k == 'H':
        # pulling back from B; C is the lowest low since B (provisional)
        b = last_i
        a = next(i for k, i in reversed(p[:-1]) if k == 'L')
        cc = min(range(b + 1, n), key=lambda i: l[i]) if b + 1 < n else b
        top_i = None
        c_conf = False
    else:
        # C confirmed (rally of 10%+ off it); top forming
        cc = last_i
        b = next(i for k, i in reversed(p[:-1]) if k == 'H')
        a = next(i for k, i in reversed(p) if k == 'L' and i < b)
        top_i = max(range(cc, n), key=lambda i: h[i])
        c_conf = True
    A, B, C = l[a], h[b], l[cc]
    if C <= A:
        status = 'broken'
        note = 'Price broke below swing low A. No valid bullish setup until a new higher low forms.'
    else:
        up = c[cc] > sma[cc]
        cal = calib(up)
        L = B - A
        levels = {f'{r}': round(C + r * L) for r in (0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618)}
        target = C + cal['median'] * L
        setup = dict(a=D(a), b=D(b), c=D(cc), A=A, B=B, C=C, c_confirmed=c_conf,
                     regime='above' if up else 'below', ratio=cal['median'],
                     target=round(target), zone=[round(C + cal['p25'] * L), round(C + cal['p75'] * L)],
                     levels=levels, calib=cal,
                     need_ratio_for_new_high=(B - C) / L,
                     top_so_far=(h[top_i] if top_i is not None else None))
        post_i = max(range(cc + 1, n), key=lambda i: h[i]) if cc + 1 < n else None
        post_high = h[post_i] if post_i is not None else None
        drop = (c[-1] / post_high - 1) if post_high else None
        setup.update(post_c_high=post_high, post_c_high_date=D(post_i) if post_i is not None else None,
                     drop_from_high=drop)
        # zone confluence: daily RSI(7), its hook, 200 EMA, resistance near the zone
        since = range(cc + 1, n)
        was_ob = any(r7[i] is not None and r7[i] >= 70 for i in since)
        last_ob = max((i for i in since if r7[i] is not None and r7[i] >= 70), default=None)
        if r7[-1] is not None and r7[-1] >= 70: rsi_state = 'overbought'
        elif was_ob: rsi_state = 'hooked'
        else: rsi_state = 'neutral'
        res = [x for x in sr_levels(h, l, p, t)
               if c[-1] < x['price'] <= setup['zone'][1] * 1.05]
        for x in res:
            x['in_zone'] = setup['zone'][0] <= x['price'] <= setup['zone'][1]
            x['dist'] = x['price'] / c[-1] - 1
        near = [x for x in res if abs(x['price'] / c[-1] - 1) <= NEAR]
        in_zone_now = setup['zone'][0] * (1 - NEAR) <= c[-1] <= setup['zone'][1]
        setup.update(rsi7=r7[-1], rsi_state=rsi_state,
                     rsi_hook_from=(D(last_ob) if last_ob is not None else None),
                     ema200=e200[-1], above_ema200=c[-1] > e200[-1],
                     resistance=res, near_resistance=(near[0]['price'] if near else None),
                     near_zone=in_zone_now,
                     confluence=sum([in_zone_now, bool(near), rsi_state == 'hooked']))
        stalled = post_high is not None and post_high < setup['zone'][0] and post_high > C * (1 + MIN_RALLY)
        if c_conf and h[top_i] >= setup['zone'][0]:
            status = 'in_zone' if h[top_i] <= setup['zone'][1] else 'above_zone'
        elif stalled and drop <= -WARN:
            status = 'early_rejection'
        elif stalled and drop <= -WATCH:
            status = 'early_watch'
        elif c_conf:
            status = 'rallying'
        else:
            status = 'pullback'

    # ---- low strength badges for A and C (and the A candidate when broken)
    lpiv = [i for k, i in p if k == 'L']
    def badge(i):
        # weak: provisional, or a wick reached TH above but no candle has CLOSED there yet
        closed_above = any(c[q] > l[i] * (1 + TH) for q in range(i + 1, n))
        if i not in lpiv or not closed_above: return 'weak'
        j = lpiv.index(i)
        return 'strong' if j > 0 and l[i] > l[lpiv[j - 1]] else 'confirmed'
    fk = low_fakeouts(h, l, c, TH)
    if ARC and ARC['meta'].get('badges'):
        for b, v in ARC['meta']['badges'].items():
            fk[b] = dict(n=fk[b]['n'] + v['n'], fakeouts=fk[b]['fakeouts'] + v['fakeouts'])
    for v in fk.values(): v['rate'] = v['fakeouts'] / v['n'] if v['n'] else None
    badges = dict(a=badge(a), c=badge(cc), rates=fk)

    # resistance is listed even without a setup: up to 5% above the zone top,
    # or 15% above price when no target exists
    if not setup:
        res = [x for x in sr_levels(h, l, p, t) if c[-1] < x['price'] <= c[-1] * 1.15]
        for x in res:
            x['in_zone'] = False
            x['dist'] = x['price'] / c[-1] - 1
        lo_i = min(range(p[-1][1], n), key=lambda i: l[i])
        broken_info = dict(low=l[lo_i], low_date=D(lo_i), confirm_at=l[lo_i] * (1 + TH), resistance=res,
                           low_badge=badge(lo_i))
    else:
        broken_info = None

    # ---- forecast log
    try:
        log = json.load(open(logp))
    except Exception:
        log = dict(forecasts=[])
    F = log['forecasts']
    today = live['date']
    opened = [f for f in F if f['state'] == 'open']

    # score open forecasts whose top is now confirmed by the zigzag
    for f in opened:
        for j in range(len(p) - 1):
            k, i = p[j]
            if k == 'L' and D(i) == f['c']:
                nxt = p[j + 1] if j + 1 < len(p) else None
                if nxt and nxt[0] == 'H':
                    top = h[nxt[1]]
                    f.update(state='scored', closed=today, top=round(top), top_date=D(nxt[1]),
                             err=top / f['target'] - 1,
                             hit=abs(top / f['target'] - 1) <= HIT_TOL,
                             inzone=f['zone'][0] <= top <= f['zone'][1])
    opened = [f for f in F if f['state'] == 'open']
    for f in opened:   # highest price since the forecast opened (closed bars + live bar)
        since = [h[i] for i in range(n) if D(i) >= f['opened']]
        f['max_high'] = round(max(since + [live['high']]))
    key = f"{setup['a']}|{setup['b']}|{setup['c']}" if setup else None
    for f in opened:
        if f['key'] != key:
            f['zone_touched'] = f.get('max_high', 0) >= f['zone'][0]
            if status == 'broken':
                f.update(state='invalidated', closed=today, reason='Price broke below A')
            elif setup and f['a'] == setup['a'] and f['b'] == setup['b']:
                f.update(state='reanchored', closed=today, reason=RULE_NOTE or 'New low under C; C moved lower')
            else:
                f.update(state='replaced', closed=today, reason=RULE_NOTE or 'New swing structure')
    if setup and not any(f['key'] == key and f['state'] in ('open', 'scored') for f in F):
        F.append(dict(key=key, opened=today, state='open', a=setup['a'], b=setup['b'], c=setup['c'],
                      A=round(A), B=round(B), C=round(C), ratio=round(setup['ratio'], 3),
                      target=setup['target'], zone=setup['zone']))
    for f in F:
        if f['state'] == 'open' and f['key'] == key and setup:
            f['last_seen'] = today
    json.dump(log, open(logp, 'w'), indent=1)

    scored = [f for f in F if f['state'] == 'scored']
    live_stats = dict(issued=len(F), open=sum(f['state'] == 'open' for f in F), scored=len(scored),
                      hits=sum(f['hit'] for f in scored),
                      invalidated=sum(f['state'] in ('invalidated', 'reanchored', 'replaced') for f in F))

    # chart series: last 240 closed days + live bar
    s = max(0, n - 240)
    series = [dict(d=D(i), o=round(o[i], 2), h=round(h[i], 2), l=round(l[i], 2), c=round(c[i], 2),
                   sma200=round(sma[i]) if sma[i] else None,
                   rsi7=(round(r7[i], 1) if r7[i] is not None else None)) for i in range(s, n)]
    state = dict(generated=dt.datetime.now(dt.UTC).strftime('%Y-%m-%d %H:%M UTC'),
                 symbol=SYMBOL, timeframe=TF, profile=PROFILE, bar=BAR, zigzag=TH, hit_tolerance=HIT_TOL,
                 watch=WATCH, warn=WARN, min_rally=MIN_RALLY, near=NEAR, confirm=CONFIRM, badges=badges,
                 live=live, sma200=round(sma[-1]), rsi7_now=r7[-1], ema200_now=e200[-1], broken=broken_info, status=status, note=note, setup=setup,
                 backtest=bt, live_stats=live_stats, forecasts=F[::-1], series=series,
                 pivots=[dict(k=k, d=D(i), v=round(h[i] if k == 'H' else l[i])) for k, i in p[-8:]])
    json.dump(state, open(outp, 'w'), indent=1)
    print(json.dumps(dict(status=status, setup={k: setup[k] for k in ('a', 'b', 'c', 'A', 'B', 'C', 'target', 'zone', 'ratio')} if setup else None,
                          live=live, backtest={k: bt[k] for k in ('n', 'within_tol', 'within_half', 'median_err', 'higher_high', 'setups')},
                          live_stats=live_stats), indent=1))

if __name__ == '__main__':
    configure(sys.argv[4] if len(sys.argv) > 4 else 'D')
    import os
    if os.environ.get('FIB_CONFIRM'): CONFIRM = os.environ['FIB_CONFIRM']      # testing only
    RULE_NOTE = os.environ.get('FIB_RULE_NOTE', '')
    main(*sys.argv[1:4], archive=(sys.argv[5] if len(sys.argv) > 5 else None))
