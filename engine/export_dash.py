#!/usr/bin/env python3
"""Turn fib_top_engine state.json into the tracker's five dataset files.
Usage: python3 export_dash.py state.json outdir
Writes the same six files for either profile (daily or 4H); the 4H set goes in its own folder.
"""
import json, sys, os

LABELS = {
    'pullback': 'Pullback forming',
    'rallying': 'Rally under way',
    'in_zone': 'Inside target zone',
    'above_zone': 'Above target zone',
    'broken': 'Structure broken',
    'early_watch': 'Early rejection watch',
    'early_rejection': 'Early rejection warning',
}

s = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
su, bt, ls, lv = s['setup'] or {}, s['backtest'], s['live_stats'], s['live']
summary = [dict(
    generated=s['generated'], live_date=lv['date'], live_close=round(lv['close']),
    status=s['status'], status_label=LABELS.get(s['status'], s['status']), note=s['note'] or '',
    a_date=su.get('a'), A=round(su['A']) if su else None,
    b_date=su.get('b'), B=round(su['B']) if su else None,
    c_date=su.get('c'), C=round(su['C']) if su else None,
    c_state='Confirmed' if su.get('c_confirmed') else 'Provisional',
    target=su.get('target'), zone_lo=su['zone'][0] if su else None, zone_hi=su['zone'][1] if su else None,
    ratio=round(su['ratio'], 3) if su else None, regime=su.get('regime'),
    to_target_pct=round(su['target'] / lv['close'] - 1, 4) if su else None,
    sma200=s['sma200'], top_so_far=round(su['top_so_far']) if su and su.get('top_so_far') else None,
    calib_n=su['calib']['n'] if su else None, reach_1_pct=round(su['calib']['reach1'], 3) if su else None,
    bt_n=bt['n'], bt_within10=bt['within_tol'], bt_within10_pct=round(bt['within_tol'] / bt['n'], 3),
    bt_within5_pct=round(bt['within_half'] / bt['n'], 3),
    timeframe=s['timeframe'], zigzag=s['zigzag'], hit_tol=s['hit_tolerance'], watch=s['watch'],
    warn=s['warn'], min_rally=s['min_rally'], near=s['near'], bt_median_err=round(bt['median_err'], 4),
    bt_recent_n=bt.get('recent_n'), bt_recent_within=bt.get('recent_within'),
    bt_recent_pct=round(bt['recent_within'] / bt['recent_n'], 3) if bt.get('recent_n') else None,
    symbol=s.get('symbol'),
    bt_higher_high_pct=round(bt['higher_high'] / bt['setups'], 3),
    post_c_high=round(su['post_c_high']) if su and su.get('post_c_high') else None,
    post_c_high_date=su.get('post_c_high_date'),
    drop_from_high=round(su['drop_from_high'], 4) if su and su.get('drop_from_high') is not None else None,
    ew_watch_fired=bt['early']['watch']['fired'], ew_watch_correct=bt['early']['watch']['correct'],
    ew_watch_precision=round(bt['early']['watch']['precision'], 3) if bt['early']['watch']['precision'] is not None else None,
    ew_warn_fired=bt['early']['warn']['fired'], ew_warn_correct=bt['early']['warn']['correct'],
    ew_warn_precision=round(bt['early']['warn']['precision'], 3) if bt['early']['warn']['precision'] is not None else None,
    rsi7=round(s['rsi7_now'], 1) if s.get('rsi7_now') is not None else None,
    rsi_state=su.get('rsi_state'),
    rsi_state_label={'overbought': 'Overbought, above 70', 'hooked': 'Hooked back below 70',
                     'neutral': 'Not overbought since C'}.get(su.get('rsi_state'), '—'),
    rsi_hook_from=su.get('rsi_hook_from'),
    ema200=round(s['ema200_now']) if s.get('ema200_now') else None,
    above_ema200=(s['live']['close'] > s['ema200_now']) if s.get('ema200_now') else None,
    near_resistance=su.get('near_resistance'),
    near_zone=su.get('near_zone'),
    confluence=su.get('confluence'),
    live_issued=ls['issued'], live_open=ls['open'], live_scored=ls['scored'], live_hits=ls['hits'],
    live_invalidated=ls['invalidated'],
    live_hit_pct=round(ls['hits'] / ls['scored'], 3) if ls['scored'] else None,
)]
levels = []
if su:
    for r, p in su['levels'].items():
        levels.append(dict(label=f'Fib {r}', ratio=float(r), price=p, kind='fib'))
    levels.append(dict(label='Model target', ratio=round(su['ratio'], 3), price=su['target'], kind='target'))
    levels.sort(key=lambda x: x['price'])
price = s['series']
forecasts = [dict(opened=f['opened'], key=f['key'], A=f['A'], B=f['B'], C=f['C'], target=f['target'],
                  zone_lo=f['zone'][0], zone_hi=f['zone'][1], state=f['state'],
                  top=f.get('top'), top_date=f.get('top_date'),
                  err=round(f['err'], 4) if f.get('err') is not None else None,
                  hit=f.get('hit'), closed=f.get('closed'), reason=f.get('reason', ''),
                  zone_touched=f.get('zone_touched'), max_high=f.get('max_high'))
             for f in s['forecasts']]
backtest = [dict(date=w['date'], target=w['target'], top=w['top'], err=round(w['err'], 4),
                 hit=abs(w['err']) <= s['hit_tolerance']) for w in bt['recent']][::-1]
res_src = (su.get('resistance') if su else None) or ((s.get('broken') or {}).get('resistance')) or []
resistance = [dict(price=x['price'], touches=x['touches'], last=x['last'], in_zone=x['in_zone'],
                   dist=round(x['dist'], 4), kind={'H': 'Swing highs', 'L': 'Swing lows', 'HL': 'Highs and lows'}[x['kinds']])
              for x in res_src]
if not levels:
    levels = [dict(label='No active setup', ratio=None, price=None, kind='none')]
if not forecasts:
    forecasts = [dict(opened=None, key='none', A=None, B=None, C=None, target=None, zone_lo=None, zone_hi=None,
                      state='none', top=None, top_date=None, err=None, hit=None, closed=None, reason='No forecast issued yet',
                      zone_touched=None, max_high=None)]
if not resistance:
    resistance = [dict(price=None, touches=0, last=None, in_zone=False, dist=None, kind='none')]
bk = s.get('broken') or {}
bg = s.get('badges') or {}
rt = bg.get('rates') or {}
LBL = {'weak': 'Weak', 'confirmed': 'Confirmed', 'strong': 'Strong'}
summary[0].update(a_strength=LBL.get(bg.get('a')) if su else None, c_strength=LBL.get(bg.get('c')) if su else None,
                  broken_low_strength=LBL.get(bk.get('low_badge')) if bk else None,
                  **{f'fk_{b}_rate': round(rt[b]['rate'], 3) if rt.get(b) and rt[b].get('rate') is not None else None for b in ('weak', 'confirmed', 'strong')},
                  **{f'fk_{b}_n': rt[b]['n'] if rt.get(b) else None for b in ('weak', 'confirmed', 'strong')})
summary[0].update(broken_low=round(bk['low']) if bk.get('low') else None, broken_low_date=bk.get('low_date'),
                  broken_confirm_at=round(bk['confirm_at']) if bk.get('confirm_at') else None)
for name, rows in [('summary', summary), ('levels', levels), ('price', price),
                   ('forecasts', forecasts), ('backtest', backtest), ('resistance', resistance)]:
    json.dump(rows, open(os.path.join(out, f'{name}.json'), 'w'))
print('ok', {k: len(v) for k, v in [('levels', levels), ('price', price), ('forecasts', forecasts), ('backtest', backtest)]})
