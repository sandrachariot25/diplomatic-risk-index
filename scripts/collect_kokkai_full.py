"""Collect complete Kokkai speeches mentioning Korea into the internal research table (schema 9).

Author decision 2026-11-10: full texts are kept only inside data/dri.sqlite3
(kokkai_speeches_full, content_policy=restricted_research_full_text) and are never exported.
Documented NDL API only, sequential, >=6 s between requests, stop on 401/403/429, resumable.

    python scripts/collect_kokkai_full.py                 # plan only, no network
    python scripts/collect_kokkai_full.py --execute       # collect / resume 2015..2026-10
    python scripts/collect_kokkai_full.py --stats         # offline counts
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dri.http import AccessBlocked, Client  # noqa: E402
from dri.storage import Store, now  # noqa: E402

HOST = 'kokkai.ndl.go.jp'
ENDPOINT = f'https://{HOST}/api/speech'
QUERY = '韓国'
PAGE = 50            # well under the 4 MB transport cap; falls back to SMALL_PAGE if exceeded
SMALL_PAGE = 10
INTERVAL = 6.0
END = '2026-11-17'  # extended 18.11.2026 for the monthly update
FIELDS = ('speechID', 'issueID', 'date', 'nameOfHouse', 'nameOfMeeting', 'issue', 'speechOrder', 'speaker',
          'speakerYomi', 'speakerGroup', 'speakerPosition', 'speakerRole', 'speech', 'speechURL', 'meetingURL')


def page_url(year, start, size=PAGE):
    params = {'any': QUERY, 'from': f'{year}-01-01', 'until': f'{year}-12-31' if year < 2026 else END,
              'maximumRecords': size, 'startRecord': start, 'recordPacking': 'json'}
    return ENDPOINT + '?' + urlencode(params)


def parse(body):
    """Return (numberOfRecords, nextRecordPosition, rows) from one documented API response."""
    obj = json.loads(body)
    if 'message' in obj and 'speechRecord' not in obj:
        raise ValueError(f'NDL API error: {obj.get("message")}')
    total = int(obj.get('numberOfRecords') or 0)
    records = obj.get('speechRecord') or []
    if total and not isinstance(records, list):
        raise ValueError('Missing official speechRecord list')
    rows = []
    for item in records:
        missing = [k for k in ('speechID', 'date', 'speech', 'speechURL') if not item.get(k)]
        if missing:
            raise ValueError(f'Speech record without {missing}')
        if urlsplit(item['speechURL']).hostname != HOST:
            raise ValueError('Unexpected speech URL host')
        if not '2015-01-01' <= item['date'] <= END:
            raise ValueError('Speech outside requested period')
        if str(item.get('speechOrder')) == '0':
            continue  # meeting header / attendance roster, not a speech
        rows.append({k: item.get(k) for k in FIELDS})
    return total, obj.get('nextRecordPosition'), rows


def save(db, rows, response_sha256):
    added = 0
    with db:
        for r in rows:
            cur = db.execute('''INSERT OR IGNORE INTO kokkai_speeches_full(speech_id,issue_id,spoken_date,name_of_house,
                name_of_meeting,issue,speech_order,speaker,speaker_yomi,speaker_group,speaker_position,speaker_role,
                speech,speech_sha256,speech_url,meeting_url,query,fetched_at,response_sha256)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (r['speechID'], r['issueID'], r['date'], r['nameOfHouse'], r['nameOfMeeting'], r['issue'],
                 int(r['speechOrder']) if r['speechOrder'] is not None else None, r['speaker'], r['speakerYomi'],
                 r['speakerGroup'], r['speakerPosition'], r['speakerRole'], r['speech'],
                 hashlib.sha256(r['speech'].encode('utf-8')).hexdigest(), r['speechURL'], r['meetingURL'],
                 QUERY, now(), response_sha256))
            added += cur.rowcount
    return added


def resume_point(db, year):
    row = db.execute('SELECT start_record, returned, next_record, number_of_records FROM kokkai_full_pages '
                     'WHERE query=? AND year=? ORDER BY start_record DESC LIMIT 1', (QUERY, year)).fetchone()
    if not row:
        return 1
    start, returned, nxt, total = row
    return nxt if nxt else None


def check_robots(client):
    # Same narrow exception as scripts/expand_kokkai.py: robots.txt redirects to the home page while the
    # published API specification explicitly allows machine access to /api/speech.
    try:
        client.check_robots(ENDPOINT)
    except AccessBlocked:
        last = client.store.db.execute(
            "SELECT status,headers_json FROM fetches WHERE url=? ORDER BY id DESC LIMIT 1",
            (f'https://{HOST}/robots.txt',)).fetchone()
        headers = {k.lower(): v for k, v in json.loads(last[1]).items()} if last else {}
        if not last or last[0] not in (301, 302, 303, 307, 308) or headers.get('location') != f'https://{HOST}/':
            raise


def fetch_page(client, year, start):
    for size in (PAGE, SMALL_PAGE):
        url = page_url(year, start, size)
        try:
            status, headers, body, raw = client.request(url)
        except ValueError as error:
            if 'size cap' in str(error) and size != SMALL_PAGE:
                continue
            raise
        if status in (401, 403, 429):
            raise AccessBlocked(f'HTTP {status}; collection stopped without retry')
        if status != 200 or 'json' not in headers.get('content-type', ''):
            raise ValueError(f'Expected documented API JSON, got HTTP {status} {headers.get("content-type")}')
        return url, body, raw
    raise ValueError('Response exceeds size cap even at the small page size')


def collect(store, years):
    client = Client(store, 'urllib', interval=INTERVAL, hosts={HOST}, retain_body=False)
    check_robots(client)
    db = store.db
    for year in years:
        start = resume_point(db, year)
        while start:
            url, body, raw = fetch_page(client, year, start)
            total, nxt, rows = parse(body)
            added = save(db, rows, raw[1])
            with db:
                db.execute('INSERT OR REPLACE INTO kokkai_full_pages VALUES(?,?,?,?,?,?,?,?)',
                           (QUERY, year, start, now(), total, len(rows), nxt, raw[1]))
            print(json.dumps({'year': year, 'start': start, 'total': total, 'returned': len(rows),
                              'added': added, 'next': nxt}), flush=True)
            start = nxt


def stats(db):
    print('speeches', db.execute('SELECT count(*) FROM kokkai_speeches_full').fetchone()[0])
    for year, n, chars in db.execute("SELECT substr(spoken_date,1,4), count(*), sum(length(speech)) "
                                     "FROM kokkai_speeches_full GROUP BY 1 ORDER BY 1"):
        total = db.execute('SELECT max(number_of_records) FROM kokkai_full_pages WHERE query=? AND year=?',
                           (QUERY, int(year))).fetchone()[0]
        print(f'  {year}: {n} speeches (API total {total}), {chars} chars')
    print('roles', db.execute("SELECT coalesce(speaker_role,'(none)'), count(*) FROM kokkai_speeches_full GROUP BY 1").fetchall())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--stats', action='store_true')
    parser.add_argument('--year', type=int, choices=range(2015, 2027))
    args = parser.parse_args()
    years = [args.year] if args.year else list(range(2015, 2027))
    store = Store()
    try:
        if args.stats:
            stats(store.db)
            return
        print(json.dumps({'plan': [page_url(y, resume_point(store.db, y) or 0) for y in years],
                          'resume_points': {y: resume_point(store.db, y) for y in years},
                          'interval_seconds': INTERVAL, 'page_size': PAGE,
                          'storage': 'kokkai_speeches_full (internal, restricted_research_full_text; never exported)',
                          'raw_api_bodies_retained': False}, ensure_ascii=False, indent=1))
        if args.execute:
            try:
                collect(store, years)
            except Exception as error:
                store.error('kokkai_jp', ENDPOINT, 'collect_kokkai_full', error)
                raise
            stats(store.db)
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
