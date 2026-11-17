"""Daily KOR-JPN aggregates from documented GDELT 1.0 daily exports -> monthly target for the forecast.

    python scripts/collect_gdelt_monthly.py                     # plan only, no network
    python scripts/collect_gdelt_monthly.py --step 1 --execute  # every day 2015-01-01..yesterday, resumable
    python scripts/collect_gdelt_monthly.py --step 1 --workers 4 --execute   # bulk mode (see below)
    python scripts/collect_gdelt_monthly.py --monthly           # offline: daily CSV -> data/gdelt_kor_jpn_monthly.csv

Each ZIP is read in memory (dri/connectors/gdelt_event_days.fetch_day), only events whose two actors are
KOR and JPN are kept, and only daily aggregates are written (no article text, no raw rows).
Default: sequential, >= 5.5 s between requests. Bulk mode (--workers N, at most 4) is a deliberate exception
for the static GDELT 1.0 daily-export archive, which GDELT publishes for bulk download: up to 4 parallel
requests without the pause; HTTP 429/5xx or network errors trigger a 60 s back-off and up to 3 retries.
Already collected days are skipped; remaining failures are logged and picked up by the next run.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from collections import defaultdict
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hashlib import sha256  # noqa: E402
import io  # noqa: E402
from urllib.request import Request, urlopen  # noqa: E402
from zipfile import ZipFile  # noqa: E402

# External environment layer: actions of North Korea, China and the US towards South Korea / Japan
# (DPRK also towards the US). Hostile = root CAMEO 13 threaten, 15 exhibit force posture (missile tests,
# drills), 16 reduce relations, 17 coerce (incl. sanctions), 18 assault, 19 fight, 20 mass violence;
# cooperative = QuadClass 1-2.
EXTERNAL = {b'PRK': {b'KOR', b'JPN', b'USA'}, b'CHN': {b'KOR', b'JPN'}, b'USA': {b'KOR', b'JPN'}}
HOSTILE = {'13', '15', '16', '17', '18', '19', '20'}


def fetch_day(day):
    """Read one GDELT 1.0 daily export in memory; keep KOR-JPN dyad rows and external-actor rows."""
    url = f'https://data.gdeltproject.org/events/{day:%Y%m%d}.export.CSV.zip'
    request = Request(url, headers={'User-Agent': 'DiplomaticRiskIndex/1.0 research archive reader'})
    with urlopen(request, timeout=60) as response:
        body = response.read(32_000_001)
    if len(body) > 32_000_000:
        raise ValueError('Compressed archive exceeds 32 MB')
    dyad, ext = [], []
    with ZipFile(io.BytesIO(body)) as archive:
        files = archive.infolist()
        if len(files) != 1 or files[0].file_size > 256_000_000:
            raise ValueError('Expected one bounded TSV member')
        with archive.open(files[0]) as stream:
            for raw in stream:
                row = raw.rstrip(b'\r\n').split(b'\t')
                if len(row) != 58:
                    raise ValueError(f'Unexpected GDELT 1.0 width: {len(row)}')
                pair = {row[7], row[17]}
                if pair == {b'KOR', b'JPN'}:
                    dyad.append([v.decode('utf-8', 'replace') for v in row])
                elif row[17] in EXTERNAL.get(row[7], ()):
                    ext.append([v.decode('utf-8', 'replace') for v in row])
    return dict(day=day.isoformat(), sha256=sha256(body).hexdigest(),
                records=[dict(raw_fields=f) for f in dyad], ext=ext)

DATA = ROOT / 'data'
DAILY = DATA / 'gdelt_kor_jpn_daily.csv'
MONTHLY = DATA / 'gdelt_kor_jpn_monthly.csv'
ERRORS = DATA / 'gdelt_kor_jpn_errors.csv'
START = date(2015, 1, 1)
PAUSE = 5.5
COLS = ['day', 'archive_sha256', 'events', 'mentions', 'goldstein_w', 'tone_w', 'q1', 'q2', 'q3', 'q4',
        'q3m', 'q4m', 'root_events'] + [f'{a}_{k}' for a in ('prk', 'chn', 'usa')
                                         for k in ('mentions', 'hostile', 'force', 'coop')]


def aggregate(result):
    ev = mentions = q3m = q4m = root = 0
    gs = tone = 0.0
    quad = defaultdict(int)
    for r in result['records']:
        f = r['raw_fields']
        m = max(1, int(f[31] or 1))          # NumMentions
        ev += 1
        mentions += m
        gs += float(f[30] or 0) * m          # GoldsteinScale, mention-weighted
        tone += float(f[34] or 0) * m        # AvgTone, mention-weighted
        quad[f[29]] += 1                     # QuadClass 1 verbal coop, 2 material coop, 3 verbal conflict, 4 material
        q3m += m if f[29] == '3' else 0
        q4m += m if f[29] == '4' else 0
        root += f[25] == '1'
    ext = {f'{a}_{k}': 0 for a in ('prk', 'chn', 'usa') for k in ('mentions', 'hostile', 'force', 'coop')}
    for f in result.get('ext', []):
        a, m = f[7].lower(), max(1, int(f[31] or 1))
        ext[f'{a}_mentions'] += m
        ext[f'{a}_hostile'] += m if f[28] in HOSTILE else 0
        ext[f'{a}_force'] += m if f[28] == '15' else 0        # exhibit force posture (tests, drills)
        ext[f'{a}_coop'] += m if f[29] in {'1', '2'} else 0
    return dict(day=result['day'], archive_sha256=result['sha256'], events=ev, mentions=mentions,
                goldstein_w=round(gs / mentions, 4) if mentions else '', tone_w=round(tone / mentions, 4) if mentions else '',
                q1=quad['1'], q2=quad['2'], q3=quad['3'], q4=quad['4'], q3m=q3m, q4m=q4m, root_events=root, **ext)


def planned_days(step, end):
    d, out = START, []
    while d <= end:
        out.append(d)
        d += timedelta(days=step)
    return out


def fetch_with_retry(d, pause):
    for attempt in range(4):
        try:
            result = aggregate(fetch_day(d))
            if pause:
                time.sleep(pause)
            return result
        except HTTPError as exc:
            if exc.code == 404 or exc.code < 429 or attempt == 3:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
        time.sleep(60)


def collect(step, execute, limit, workers):
    workers = max(1, min(4, workers))
    done = {r['day'] for r in csv.DictReader(DAILY.open(encoding='utf-8'))} if DAILY.exists() else set()
    todo = [d for d in planned_days(step, date.today() - timedelta(days=1)) if d.isoformat() not in done][:limit]
    per_file = 8.0 if workers > 1 else 13.5
    print(f'planned every {step} day(s); already {len(done)}; to fetch {len(todo)} with {workers} worker(s) '
          f'(~{len(todo) * 9 / 1000:.1f} GB transfer, ~{len(todo) * per_file / workers / 3600:.1f} h)', flush=True)
    if not execute:
        return
    new_file = not DAILY.exists()
    pause = PAUSE if workers == 1 else 0.0
    started = time.time()
    with DAILY.open('a', newline='', encoding='utf-8') as fh, ERRORS.open('a', newline='', encoding='utf-8') as eh, \
            ThreadPoolExecutor(max_workers=workers) as pool:
        writer, errs = csv.DictWriter(fh, fieldnames=COLS), csv.writer(eh)
        if new_file:
            writer.writeheader()
        futures = {pool.submit(fetch_with_retry, d, pause): d for d in todo}
        ok = failed = 0
        for i, fut in enumerate(as_completed(futures), 1):
            d = futures[fut]
            try:
                writer.writerow(fut.result())   # written from the main thread only
                fh.flush()
                ok += 1
            except Exception as exc:  # noqa: BLE001 - log any archive/network failure and continue
                errs.writerow([d.isoformat(), type(exc).__name__, str(exc)[:200]])
                eh.flush()
                failed += 1
            if i % 50 == 0 or i == len(todo):
                rate = i / (time.time() - started)
                print(f'{i}/{len(todo)} ok {ok} failed {failed}; ~{(len(todo) - i) / rate / 60:.0f} min left',
                      flush=True)


def monthly():
    by = defaultdict(list)
    for r in csv.DictReader(DAILY.open(encoding='utf-8')):
        by[r['day'][:7]].append(r)
    rows = []
    for m in sorted(by):
        days = by[m]
        ment = sum(int(r['mentions']) for r in days)
        ev = sum(int(r['events']) for r in days)
        rows.append(dict(
            month=m, days_sampled=len(days), events_per_day=round(ev / len(days), 2),
            goldstein=round(sum(float(r['goldstein_w'] or 0) * int(r['mentions']) for r in days) / ment, 4) if ment else '',
            tone=round(sum(float(r['tone_w'] or 0) * int(r['mentions']) for r in days) / ment, 4) if ment else '',
            conflict_share=round(sum(int(r['q3m']) + int(r['q4m']) for r in days) / ment, 4) if ment else '',
            material_conflict_share=round(sum(int(r['q4m']) for r in days) / ment, 4) if ment else '',
            **{f'{a}_{k}_per_day': round(sum(int(r[f'{a}_{k}']) for r in days) / len(days), 2)
               for a in ('prk', 'chn', 'usa') for k in ('hostile', 'force', 'coop')},
            **{f'{a}_hostile_share': round(sum(int(r[f'{a}_hostile']) for r in days) /
                                           max(1, sum(int(r[f'{a}_mentions']) for r in days)), 4)
               for a in ('prk', 'chn', 'usa')}))
    with MONTHLY.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{MONTHLY.name}: {len(rows)} months')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--step', type=int, default=3)
    p.add_argument('--limit', type=int, default=100000)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--monthly', action='store_true')
    a = p.parse_args()
    monthly() if a.monthly else collect(a.step, a.execute, a.limit, a.workers)
