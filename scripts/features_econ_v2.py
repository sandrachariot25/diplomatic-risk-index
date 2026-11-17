"""Monthly economic layer for the DRI v2 forecast (Korea-Japan trade dependence).

    python scripts/features_econ_v2.py     # -> data/dri_v2_econ_monthly.csv

Source: economic_trade_current in data/dri.sqlite3 (IMF IMTS totals; UN Comtrade HS6 basket of critical
goods), Korea as reporter. Trade statistics are published with a delay, so the row for month t carries
values of month t-LAG (LAG = 2): the forecast never uses data that would not have been available.
Features:
  econ_dep_total   share of Japan in Korea's total imports
  econ_dep_crit    share of Japan in Korea's imports of the critical HS6 basket (same codes, same month)
  econ_balance     Korea's balance with Japan / bilateral turnover
  econ_turnover_yoy  log change of bilateral turnover vs. 12 months earlier
  *_z12            deviation from the own trailing 12-month norm (in SDs) -> "dependence builds to a peak"
  *_chg12          change vs. 12 months earlier
"""
import csv
from collections import defaultdict
import math
import sqlite3
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_econ_monthly.csv'
LAG = 2


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def load():
    db = sqlite3.connect(f'file:{DATA / "dri.sqlite3"}?mode=ro', uri=True)
    tot, crit = defaultdict(float), defaultdict(lambda: defaultdict(float))
    for period, partner, flow, value in db.execute(
            "select period, partner, flow, value_usd from economic_trade_current where frequency='M' and "
            "classification='TOTAL' and reporter='KOR' and partner in ('JPN','WLD')"):
        tot[(period, partner, flow)] += value or 0.0
    for period, partner, code, value in db.execute(
            "select period, partner, commodity, value_usd from economic_trade_current where frequency='M' and "
            "classification in ('H4','H5','H6') and reporter='KOR' and partner in ('JPN','WLD') and flow='M'"):
        crit[period][(partner, code)] += value or 0.0
    return tot, crit


def main():
    tot, crit = load()
    months = sorted({p for p, _, _ in tot})
    raw = {}
    for m in months:
        mj, mw = tot.get((m, 'JPN', 'M')), tot.get((m, 'WLD', 'M'))
        xj = tot.get((m, 'JPN', 'X'))
        if not (mj and mw and xj):
            continue
        codes = {c for (p, c) in crit.get(m, {}) if p == 'JPN'} & {c for (p, c) in crit.get(m, {}) if p == 'WLD'}
        cw = sum(crit[m][('WLD', c)] for c in codes)
        raw[m] = dict(dep_total=mj / mw, dep_crit=(sum(crit[m][('JPN', c)] for c in codes) / cw) if cw else None,
                      balance=(xj - mj) / (xj + mj), turnover=xj + mj)
    rows = []
    for m in months:
        if m not in raw:
            continue
        r = dict(month=month_add(m, LAG), data_month=m)
        for k in ('dep_total', 'dep_crit', 'balance'):
            v = raw[m][k]
            past = [raw[p][k] for p in (month_add(m, -i) for i in range(12)) if p in raw and raw[p][k] is not None]
            prev = raw.get(month_add(m, -12), {}).get(k)
            r[f'econ_{k}'] = round(v, 5) if v is not None else ''
            r[f'econ_{k}_z12'] = round((v - np.mean(past)) / (np.std(past) + 1e-9), 3) if v is not None and len(past) >= 6 else ''
            r[f'econ_{k}_chg12'] = round(v - prev, 5) if v is not None and prev is not None else ''
        prev_t = raw.get(month_add(m, -12), {}).get('turnover')
        r['econ_turnover_yoy'] = round(math.log(raw[m]['turnover'] / prev_t), 4) if prev_t else ''
        rows.append(r)
    with OUT.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    crit_n = sum(r['econ_dep_crit'] != '' for r in rows)
    print(f'{OUT.name}: {len(rows)} months {rows[0]["month"]}..{rows[-1]["month"]} (data lag {LAG}); '
          f'critical basket in {crit_n}')
    for r in rows[::24]:
        print(' ', r['month'], 'dep_total', r['econ_dep_total'], 'dep_crit', r['econ_dep_crit'], 'balance', r['econ_balance'])


if __name__ == '__main__':
    main()
