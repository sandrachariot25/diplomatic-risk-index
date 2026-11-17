"""DRI v2 forecast against a systematic target: KOR-JPN conflict in GDELT 1.0, 1-3 months ahead.

    python scripts/collect_gdelt_monthly.py --monthly   # daily -> monthly GDELT target
    python scripts/forecast_gdelt_v2.py                 # -> data/dri_v2_forecast_gdelt.json

Target per month t (mention-weighted share of conflict events, QuadClass 3+4, among KOR-JPN events):
  spike_next = mean(conflict share, t+1..t+3) exceeds its own norm for the past 12 months (t-11..t)
               by more than one standard deviation of those 12 months;
  delta_next = mean(t+1..t+3) - mean(t-2..t)  (continuous change).
Models (rolling origin by year, fitted only on months whose target window closes before the test year):
  gdelt_history - current GDELT level, 3-month trend and gap to the 12-month norm;
  parliament    - parliamentary features only (scripts/forecast_v2.PARL);
  both          - the two together. Logistic (spike) and ridge (delta) regressions, L2.
The parliament layer adds value only if `both` beats `gdelt_history` on the held-out years.
"""
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.forecast_v2 import PARL, auc, fit_logistic, load, month_index  # noqa: E402

DATA = ROOT / 'data'
GDELT = DATA / 'gdelt_kor_jpn_monthly.csv'
ECON = DATA / 'dri_v2_econ_monthly.csv'
OUT = DATA / 'dri_v2_forecast_gdelt.json'
GHIST = ['g_level', 'g_trend', 'g_gap', 'g_log_events']
ECONF = ['econ_dep_total_z12', 'econ_dep_crit_z12', 'econ_balance_z12', 'econ_turnover_yoy',
         'econ_dep_total_chg12', 'econ_dep_crit_chg12']
EXT = ['x_prk_hostile', 'x_prk_hostile_share', 'x_chn_hostile', 'x_chn_hostile_share', 'x_usa_coop']
RIVALRY = DATA / 'dri_v2_rivalry_monthly.csv'
RIV = ['riv_all', 'riv_jp_loss', 'riv_chips_agg', 'riv_chip_equipment_agg', 'riv_autos_agg', 'riv_batteries_agg']
SETS = {'gdelt_history': GHIST, 'parliament_only': PARL, '+parliament': GHIST + PARL, '+economy': GHIST + ECONF,
        '+rivalry': GHIST + RIV, '+external': GHIST + EXT, 'material_core': GHIST + ECONF + RIV,
        'all_layers': GHIST + PARL + ECONF + RIV + EXT}
H, NORM = 3, 12
LAMBDA = 5.0   # stronger shrinkage: up to ~27 features on ~100 training months


def build():
    rows = {r['month']: r for r in load()}
    g = {r['month']: r for r in csv.DictReader(GDELT.open(encoding='utf-8'))}
    econ = {r['month']: r for r in csv.DictReader(ECON.open(encoding='utf-8'))}
    riv = {r['month']: r for r in csv.DictReader(RIVALRY.open(encoding='utf-8'))}
    num = lambda v: float(v) if v not in ('', None) else 0.0
    for m, r in rows.items():
        e, v = econ.get(m, {}), riv.get(m, {})
        for k in ECONF:
            r[k] = num(e.get(k))
        for k in RIV:
            r[k] = num(v.get(k))
        if m in g:
            r['x_prk_hostile'] = math.log1p(num(g[m]['prk_hostile_per_day']))
            r['x_prk_hostile_share'] = num(g[m]['prk_hostile_share'])
            r['x_chn_hostile'] = math.log1p(num(g[m]['chn_hostile_per_day']))
            r['x_chn_hostile_share'] = num(g[m]['chn_hostile_share'])
            r['x_usa_coop'] = math.log1p(num(g[m]['usa_coop_per_day']))
    months = [m for m in rows if m in g and g[m]['conflict_share'] != '']
    cs = {m: float(g[m]['conflict_share']) for m in months}
    out = []
    for i, m in enumerate(months):
        past, future = months[max(0, i - NORM + 1): i + 1], months[i + 1: i + 1 + H]
        if len(past) < NORM:
            continue
        r = rows[m]
        norm = np.array([cs[p] for p in past])
        r['g_level'] = cs[m]
        r['g_trend'] = cs[m] - np.mean([cs[p] for p in past[-3:]])
        r['g_gap'] = (cs[m] - norm.mean()) / (norm.std() + 1e-9)
        r['g_log_events'] = math.log1p(float(g[m]['events_per_day']))
        if len(future) == H:
            fut = np.mean([cs[f] for f in future])
            r['spike_next'] = float(fut > norm.mean() + norm.std())
            r['delta_next'] = fut - np.mean([cs[p] for p in past[-3:]])
        else:
            r['spike_next'] = r['delta_next'] = None
        out.append(r)
    return out


def ridge(X, y, lam=1.0):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    P = lam * np.eye(Xb.shape[1])
    P[-1, -1] = 0
    return np.linalg.solve(Xb.T @ Xb + P, Xb.T @ y)


def backtest(rows):
    lab = [r for r in rows if r['spike_next'] is not None]
    years = sorted({int(r['month'][:4]) for r in lab if int(r['month'][:4]) >= 2018})
    res = {k: dict(p=[], d=[]) for k in SETS}
    ys, ds = [], []
    for Y in years:
        cut = month_index(f'{Y}-01') - H
        tr = [r for r in lab if month_index(r['month']) < cut]
        te = [r for r in lab if int(r['month'][:4]) == Y]
        if not te or len(tr) < 24:
            continue
        ys += [r['spike_next'] for r in te]
        ds += [r['delta_next'] for r in te]
        for k, cols in SETS.items():
            Xtr = np.array([[r[c] for c in cols] for r in tr])
            mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
            Xte = (np.array([[r[c] for c in cols] for r in te]) - mu) / sd
            w, b = fit_logistic((Xtr - mu) / sd, np.array([r['spike_next'] for r in tr]), lam=LAMBDA)
            res[k]['p'] += list(1 / (1 + np.exp(-(Xte @ w + b))))
            beta = ridge((Xtr - mu) / sd, np.array([r['delta_next'] for r in tr]), lam=LAMBDA)
            res[k]['d'] += list(np.hstack([Xte, np.ones((len(Xte), 1))]) @ beta)
    y, d = np.array(ys), np.array(ds)
    report = {}
    for k, v in res.items():
        p, dp = np.array(v['p']), np.array(v['d'])
        report[k] = dict(spike_auc=None if auc(y, p) is None else round(auc(y, p), 3),
                         spike_brier=round(float(((p - y) ** 2).mean()), 4),
                         delta_corr=round(float(np.corrcoef(dp, d)[0, 1]), 3),
                         delta_rmse=round(float(np.sqrt(((dp - d) ** 2).mean())), 4))
    report['no_change'] = dict(delta_rmse=round(float(np.sqrt((d ** 2).mean())), 4))
    return report, years, len(y), int(y.sum())


def main():
    rows = build()
    report, years, n, pos = backtest(rows)
    OUT.write_text(json.dumps(dict(target='GDELT KOR-JPN conflict share, t+1..t+3', test_years=years,
                                   test_months=n, spikes=pos, backtest=report), ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print(f'months with target {sum(r["spike_next"] is not None for r in rows)}; test {years[0]}-{years[-1]}: '
          f'{n} months, {pos} spikes')
    for k, m in report.items():
        print(f'  {k:14} {m}')


if __name__ == '__main__':
    main()
