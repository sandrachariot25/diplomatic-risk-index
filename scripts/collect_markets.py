"""Monthly imports of third markets from Korea and Japan in contested industries (UN Comtrade public preview).

    python scripts/collect_markets.py              # plan only
    python scripts/collect_markets.py --execute    # 2015-01..latest available, resumable
-> data/market_imports_monthly.csv (reporter, partner, hs, period, value_usd) + data/market_imports_log.csv

Markets (reporters): USA 842, China 156, Germany 276 (EU proxy), Viet Nam 704.
Partners: world 0, Japan 392, Korea 410. HS codes: 8542 integrated circuits, 8486 semiconductor
manufacturing equipment, 8524 / 9013 display modules (8524 exists from HS2022; 9013 before), 8507 batteries,
8703 cars, 8708 auto parts, 72 iron and steel, 29 organic chemicals. The public preview allows one period
per request; requests are sequential with a 3 s pause; 429/5xx -> 60 s back-off, up to 3 retries.
Empty months (not yet reported) are logged and retried on the next run.
"""
import argparse
import csv
from datetime import date
from hashlib import sha256
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'market_imports_monthly.csv'
LOG = DATA / 'market_imports_log.csv'
REPORTERS = '842,156,276,704'
PARTNERS = '0,392,410'
CODES = '8542,8486,8524,9013,8507,8703,8708,72,29'
FLOWS = 'M'
# --set seafood: fish and seafood trade (HS 03 fish/crustaceans, 1604 prepared fish, 1605 prepared crustaceans)
# of Korea, China and Japan with each other and the world, imports and exports -> market_seafood_monthly.csv
SEAFOOD = dict(reporters='410,156,392', partners='0,392,410,156', codes='03,1604,1605', flows='M,X',
               out='market_seafood_monthly.csv', log='market_seafood_log.csv')
BASE = 'https://comtradeapi.un.org/public/v1/preview/C/M/HS'
COLS = ['period', 'reporter', 'partner', 'hs', 'value_usd', 'net_weight_kg', 'classification', 'flow']


def periods():
    y, m, out, today = 2015, 1, [], date.today()
    while (y, m) < (today.year, today.month):
        out.append(f'{y}{m:02d}')
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def get(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'DiplomaticRiskIndex/1.0 research'}), timeout=90) as r:
                body = r.read()
            return body, json.loads(body)
        except HTTPError as exc:
            if exc.code < 429 or attempt == 3:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
        time.sleep(60)


def main(execute, which='markets'):
    global OUT, LOG, REPORTERS, PARTNERS, CODES, FLOWS
    if which == 'seafood':
        OUT, LOG = DATA / SEAFOOD['out'], DATA / SEAFOOD['log']
        REPORTERS, PARTNERS, CODES, FLOWS = (SEAFOOD[k] for k in ('reporters', 'partners', 'codes', 'flows'))
    done = {r['period'] for r in csv.DictReader(LOG.open(encoding='utf-8')) if r['rows'] != '0'} if LOG.exists() else set()
    todo = [p for p in periods() if p not in done]
    print(f'periods to fetch {len(todo)} (~{len(todo) * 5 / 60:.0f} min)', flush=True)
    if not execute:
        return
    new_out, new_log = not OUT.exists(), not LOG.exists()
    with OUT.open('a', newline='', encoding='utf-8') as fo, LOG.open('a', newline='', encoding='utf-8') as fl:
        w, lg = csv.DictWriter(fo, fieldnames=COLS), csv.writer(fl)
        if new_out:
            w.writeheader()
        if new_log:
            lg.writerow(['period', 'rows', 'sha256', 'url', 'retrieved_at', 'error'])
        for i, p in enumerate(todo, 1):
            url = f'{BASE}?reporterCode={REPORTERS}&period={p}&partnerCode={PARTNERS}&flowCode={FLOWS}&cmdCode={CODES}'
            try:
                body, d = get(url)
                rows = d.get('data') or []
                for x in rows:
                    w.writerow(dict(period=f'{p[:4]}-{p[4:]}', reporter=x['reporterCode'], partner=x['partnerCode'],
                                    hs=x['cmdCode'], value_usd=x['primaryValue'], net_weight_kg=x.get('netWgt'),
                                    classification=x.get('classificationCode'), flow=x.get('flowCode')))
                lg.writerow([p, len(rows), sha256(body).hexdigest(), url, time.strftime('%Y-%m-%dT%H:%M:%S'),
                             d.get('error', '')])
            except Exception as exc:  # noqa: BLE001
                lg.writerow([p, 0, '', url, time.strftime('%Y-%m-%dT%H:%M:%S'), f'{type(exc).__name__}: {exc}'[:200]])
            fo.flush()
            fl.flush()
            if i % 12 == 0:
                print(f'{i}/{len(todo)} up to {p}', flush=True)
            time.sleep(3)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--set', choices=['markets', 'seafood'], default='markets')
    a = ap.parse_args()
    main(a.execute, a.set)
