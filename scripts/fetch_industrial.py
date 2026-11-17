"""Industrial production index, Japan and Korea, monthly (OECD STES, total industry BTE, volume index).

    python scripts/fetch_industrial.py   # -> data/raw/oecd_industrial_production.csv + data/industrial_production_monthly.csv

Source: OECD SDMX dataflow OECD.SDD.STES,DSD_STES@DF_INDSERV (key JPN+KOR.M.PRVM.IX.BTE....), from 2015-01.
Seasonally adjusted (ADJUSTMENT=Y) values are used for the features; the raw response is kept with its SHA-256.
"""
import csv
from hashlib import sha256
import io
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw' / 'oecd_industrial_production.csv'
OUT = ROOT / 'data' / 'industrial_production_monthly.csv'
URL = ('https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_INDSERV,/JPN+KOR.M.PRVM.IX.BTE....'
       '?startPeriod=2015-01&dimensionAtObservation=AllDimensions&format=csvfile')


def main():
    body = urlopen(Request(URL, headers={'User-Agent': 'DiplomaticRiskIndex/1.0 research', 'Accept': 'text/csv'}),
                   timeout=120).read()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_bytes(body)
    (RAW.with_suffix('.json')).write_text(json.dumps(dict(url=URL, sha256=sha256(body).hexdigest(),
                                                          retrieved_at=time.strftime('%Y-%m-%dT%H:%M:%S')), indent=1))
    vals = {}
    for r in csv.DictReader(io.StringIO(body.decode('utf-8'))):
        if r['ADJUSTMENT'] == 'Y' and r['OBS_VALUE']:
            vals.setdefault(r['TIME_PERIOD'], {})[r['REF_AREA']] = float(r['OBS_VALUE'])
    with OUT.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['month', 'jp_ip', 'kr_ip'])
        for m in sorted(vals):
            w.writerow([m, vals[m].get('JPN', ''), vals[m].get('KOR', '')])
    print(f'{OUT.name}: {len(vals)} months {min(vals)}..{max(vals)}')


if __name__ == '__main__':
    main()
