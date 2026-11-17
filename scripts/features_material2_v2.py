"""Second material layer, built around the mechanisms named by the expert (13.11.2026):
Japanese industrial slowdown, the semiconductor cycle, and seafood (Fukushima / fisheries).

    python scripts/fetch_industrial.py                        # OECD industrial production
    python scripts/collect_markets.py --set seafood --execute # Comtrade seafood trade
    python scripts/features_material2_v2.py                   # -> data/dri_v2_material2_monthly.csv

Publication delay: industrial production LAG_IP = 1 month, trade LAG_TRADE = 2 months (row t uses data up to
t-lag). Growth rates use 3-month sums of trade (noise) and log changes vs. 12 months earlier.
  m2_jp_ip_yoy / m2_jp_ip_3m   Japan industrial production, 12-month and 3-month log change (SA index)
  m2_kr_ip_yoy, m2_ip_gap      Korea industrial production growth; Korea minus Japan (Korea outgrowing Japan)
  m2_jp_exports_yoy            Japan exports to the world (IMF)
  m2_jp_exports_kr_yoy         Japan exports to Korea (IMF)
  m2_kr_memory_yoy             Korea memory-chip exports to the world (HS 854232, Comtrade) - chip cycle
  m2_jp_equip_kr_yoy           Japan exports of chip-making equipment to Korea (HS 848620)
  m2_kr_seafood_jp_yoy / _share Korea's seafood imports from Japan (HS 03, 1604, 1605) and Japan's share
  m2_cn_seafood_jp_yoy         China's seafood imports from Japan
  m2_jp_seafood_exports_yoy    Japan's seafood exports to the world
"""
import csv
from collections import defaultdict
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_material2_monthly.csv'
LAG_IP, LAG_TRADE = 1, 2


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def logchg(series, m, k, roll=1):
    def s(x):
        vals = [series.get(month_add(x, -i)) for i in range(roll)]
        return sum(vals) if all(v for v in vals) else None
    a, b = s(m), s(month_add(m, -k))
    return round(math.log(a / b), 4) if a and b else ''


def main():
    ip = {r['month']: r for r in csv.DictReader((DATA / 'industrial_production_monthly.csv').open(encoding='utf-8'))}
    jp_ip = {m: float(r['jp_ip']) for m, r in ip.items() if r['jp_ip']}
    kr_ip = {m: float(r['kr_ip']) for m, r in ip.items() if r['kr_ip']}
    db = sqlite3.connect(f'file:{DATA / "dri.sqlite3"}?mode=ro', uri=True)
    series = defaultdict(lambda: defaultdict(float))
    for name, cls, rep, par, flow, cmd in [('jp_x_wld', 'TOTAL', 'JPN', 'WLD', 'X', 'TOTAL'),
                                           ('jp_x_kr', 'TOTAL', 'JPN', 'KOR', 'X', 'TOTAL'),
                                           ('kr_mem', None, 'KOR', 'WLD', 'X', '854232'),
                                           ('jp_equip_kr', None, 'JPN', 'KOR', 'X', '848620')]:
        q = ("select period, sum(value_usd) from economic_trade_current where frequency='M' and reporter=? and "
             "partner=? and flow=? and commodity=? " + ("and classification='TOTAL' " if cls else
                                                        "and classification in ('H4','H5','H6') ") + "group by period")
        for period, v in db.execute(q, (rep, par, flow, cmd)):
            series[name][period] = v or 0.0
    sea = DATA / 'market_seafood_monthly.csv'
    if sea.exists():
        seen = set()
        for r in csv.DictReader(sea.open(encoding='utf-8')):
            k = (r['period'], r['reporter'], r['partner'], r['hs'], r['flow'])
            if k in seen or not r['value_usd']:
                continue
            seen.add(k)
            v = float(r['value_usd'])
            if r['reporter'] == '410' and r['flow'] == 'M' and r['partner'] == '392':
                series['kr_sea_jp'][r['period']] += v
            if r['reporter'] == '410' and r['flow'] == 'M' and r['partner'] == '0':
                series['kr_sea_wld'][r['period']] += v
            if r['reporter'] == '156' and r['flow'] == 'M' and r['partner'] == '392':
                series['cn_sea_jp'][r['period']] += v
            if r['reporter'] == '392' and r['flow'] == 'X' and r['partner'] == '0':
                series['jp_sea_wld'][r['period']] += v
    months, m = [], '2016-01'
    while m <= '2026-11':
        months.append(m)
        m = month_add(m, 1)
    rows = []
    for m in months:
        mi, mt = month_add(m, -LAG_IP), month_add(m, -LAG_TRADE)
        r = dict(month=m,
                 m2_jp_ip_yoy=logchg(jp_ip, mi, 12), m2_jp_ip_3m=logchg(jp_ip, mi, 3),
                 m2_kr_ip_yoy=logchg(kr_ip, mi, 12),
                 m2_jp_exports_yoy=logchg(series['jp_x_wld'], mt, 12, 3),
                 m2_jp_exports_kr_yoy=logchg(series['jp_x_kr'], mt, 12, 3),
                 m2_kr_memory_yoy=logchg(series['kr_mem'], mt, 12, 3),
                 m2_jp_equip_kr_yoy=logchg(series['jp_equip_kr'], mt, 12, 3),
                 m2_kr_seafood_jp_yoy=logchg(series['kr_sea_jp'], mt, 12, 3),
                 m2_cn_seafood_jp_yoy=logchg(series['cn_sea_jp'], mt, 12, 3),
                 m2_jp_seafood_exports_yoy=logchg(series['jp_sea_wld'], mt, 12, 3))
        r['m2_ip_gap'] = round(r['m2_kr_ip_yoy'] - r['m2_jp_ip_yoy'], 4) if r['m2_kr_ip_yoy'] != '' and \
            r['m2_jp_ip_yoy'] != '' else ''
        sj = sum(series['kr_sea_jp'].get(month_add(mt, -i), 0) for i in range(3))
        sw = sum(series['kr_sea_wld'].get(month_add(mt, -i), 0) for i in range(3))
        r['m2_kr_seafood_jp_share'] = round(sj / sw, 4) if sw else ''
        rows.append(r)
    with OUT.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    filled = {k: sum(r[k] != '' for r in rows) for k in rows[0] if k != 'month'}
    print(f'{OUT.name}: {len(rows)} months; filled per column: {filled}')


if __name__ == '__main__':
    main()
