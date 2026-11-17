"""Material-core layer: Korea-Japan rivalry in third markets (from scripts/collect_markets.py).

    python scripts/features_rivalry_v2.py   # -> data/dri_v2_rivalry_monthly.csv

For each market (USA, China, Germany, Viet Nam) and industry group, monthly shares of Korea and Japan in the
market's imports (3-month rolling sums to damp noise), the gap kr - jp and its 12-month change
(> 0: Korea gaining on Japan). Aggregates weight each market x industry cell by the combined Korea+Japan import
value of the trailing year (cells that matter to both count more). Data are shifted by LAG = 2 months
(publication delay): the row for month t only uses trade up to t-2.
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
SRC = DATA / 'market_imports_monthly.csv'
OUT = DATA / 'dri_v2_rivalry_monthly.csv'
LAG, ROLL = 2, 3
GROUPS = {'chips': {'8542'}, 'chip_equipment': {'8486'}, 'displays': {'8524', '9013'}, 'batteries': {'8507'},
          'autos': {'8703', '8708'}, 'steel': {'72'}, 'chemicals': {'29'}}
MARKETS = {'842': 'usa', '156': 'chn', '276': 'deu', '704': 'vnm'}


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def main():
    val = defaultdict(float)            # (market, group, partner, month) -> USD
    seen = set()
    for r in csv.DictReader(SRC.open(encoding='utf-8')):
        g = next((k for k, codes in GROUPS.items() if r['hs'] in codes), None)
        if g and r['reporter'] in MARKETS and r['value_usd']:
            key = (r['reporter'], g, r['partner'], r['period'], r['hs'])
            if key in seen:                 # resumed runs may repeat a period
                continue
            seen.add(key)
            val[(MARKETS[r['reporter']], g, r['partner'], r['period'])] += float(r['value_usd'])
    months = sorted({k[3] for k in val})
    cells = sorted({(k[0], k[1]) for k in val})

    def rolled(mk, g, p, m):
        vals = [val.get((mk, g, p, month_add(m, -i))) for i in range(ROLL)]
        return sum(vals) if all(v is not None for v in vals) else None

    gap = {}
    for mk, g in cells:
        for m in months:
            w, kr, jp = (rolled(mk, g, p, m) for p in ('0', '410', '392'))
            if w and kr is not None and jp is not None:
                gap[(mk, g, m)] = (kr / w, jp / w, kr + jp)
    rows = []
    for m in months:
        out = dict(month=month_add(m, LAG), data_month=m)
        agg = defaultdict(lambda: [0.0, 0.0])
        for mk, g in cells:
            now, prev = gap.get((mk, g, m)), gap.get((mk, g, month_add(m, -12)))
            if not now:
                continue
            out[f'riv_{mk}_{g}_gap'] = round(now[0] - now[1], 4)
            if prev:
                mom = (now[0] - now[1]) - (prev[0] - prev[1])
                out[f'riv_{mk}_{g}_mom'] = round(mom, 4)
                weight = now[2]
                for name in ('all', g, mk):
                    agg[name][0] += weight * mom
                    agg[name][1] += weight
                agg['jp_loss'][0] += weight * (prev[1] - now[1])
                agg['jp_loss'][1] += weight
        for name, (s, w) in agg.items():
            out[f'riv_{name}' if name in ('all', 'jp_loss') else f'riv_{name}_agg'] = round(s / w, 5) if w else ''
        rows.append(out)
    cols = ['month', 'data_month'] + sorted({k for r in rows for k in r} - {'month', 'data_month'})
    with OUT.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval='')
        w.writeheader()
        w.writerows(rows)
    filled = sum(r.get('riv_all', '') != '' for r in rows)
    print(f'{OUT.name}: {len(rows)} months, rivalry momentum available in {filled}; columns {len(cols)}')


if __name__ == '__main__':
    main()
