import sys, json, os, statistics as st, importlib.util
sys.path.insert(0, '/home/claude/fib-extension-/build'); import build as B
spec = importlib.util.spec_from_file_location('E', B.ENGINE); E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
md = sys.argv[1]; INV = len(sys.argv) > 2
res = {}
for tab in B.CFG['tabs']:
    E.configure(tab['profile'])
    rows = B.load_rows(md, tab, None)
    if INV: rows = [(t, 1e9/o, 1e9/l, 1e9/h, 1e9/c) for t, o, h, l, c in rows]
    t, o, h, l, c = [list(x) for x in zip(*rows)]
    n = len(c); sma = [None]*n
    for i in range(199, n): sma[i] = sum(c[i-199:i+1])/200
    p = E.zigzag(h, l, E.TH, c, E.CONFIRM); r7 = E.rsi_wilder(c, 7)
    hist = []
    for j in range(len(p)-3):
        (ka,a),(kb,b),(kc,cc),(kd,d) = p[j:j+4]
        if ka != 'L' or l[cc] <= l[a] or sma[cc] is None: continue
        hist.append(dict(a=a,b=b,cc=cc,d=d,A=l[a],B=h[b],C=l[cc],T=h[d],r=(h[d]-l[cc])/(h[b]-l[a]),up=c[cc]>sma[cc]))
    S = {k: [] for k in ('zone','pull','rsi','either','both')}; miss = 0
    for k, x in enumerate(hist):
        prior = [y['r'] for y in hist[:k] if y['up'] == x['up']]
        if len(prior) < 15: continue
        L = x['B']-x['A']; zlo = x['C']+E.pct(prior,.25)*L; T = x['T']
        iz = next((i for i in range(x['cc']+1, n) if h[i] >= zlo), None)
        if iz is None or iz > x['d']: miss += 1; continue
        end = x['d']
        while end < n-1 and l[end] > T*(1-E.TH): end += 1
        fallback = T*(1-E.TH)
        S['zone'].append(min(zlo, T)/T-1 if o[iz] < zlo else o[iz]/T-1)
        run = 0; ob = False; got = {}
        for i in range(iz, end+1):
            run = max(run, h[i])
            if r7[i] is not None and r7[i] >= 70: ob = True
            pull = c[i] <= run*(1-E.WATCH); hook = ob and r7[i] is not None and r7[i] < 70
            if pull and 'pull' not in got: got['pull'] = c[i]
            if hook and 'rsi' not in got: got['rsi'] = c[i]
            if (pull or hook) and 'either' not in got: got['either'] = c[i]
            if 'pull' in got and 'rsi' in got and 'both' not in got: got['both'] = c[i]
        for s in ('pull','rsi','either','both'): S[s].append(got.get(s, fallback)/T-1)
    tol = E.HIT_TOL/2
    out = {}
    for s, v in S.items():
        if not v: continue
        out[s] = dict(n=len(v), med=round(st.median(v)*100,1), mean=round(st.mean(v)*100,1),
                      near=round(sum(x >= -tol for x in v)/len(v)*100), bad=round(sum(x < -2*E.HIT_TOL for x in v)/len(v)*100))
    res[tab['id']] = out
    print(tab['id'], 'no-touch', miss, ' '.join('%s:n%d med%+.1f mean%+.1f near%d%% bad%d%%' % (s, d['n'], d['med'], d['mean'], d['near'], d['bad']) for s, d in out.items()))
json.dump(res, open('/tmp/cf/res%s.json' % ('_inv' if INV else ''), 'w'))
