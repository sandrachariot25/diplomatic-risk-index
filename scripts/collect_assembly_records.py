"""Korean National Assembly records after the kr-hearings v10.3 dataset (ends 2026-09-18, conf 57313).

    python scripts/collect_assembly_records.py              # plan only, no network
    python scripts/collect_assembly_records.py --execute    # fetch new meeting records, resumable

Source: the public minutes viewer https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id=<conf_num>&type=view
(no robots.txt on the host; sequential requests, >= 2 s apart, stop on 403/429). Meeting ids are sequential, so the
collector walks upward from the last known id and stops after MAX_MISS consecutive ids without a record.

Each speaker block (div.speaker: data-name, data-pos; class spk_mem = member) becomes one turn; text = its spk_sub
spans. Turns after the adjournment marker ("산회") are flagged after_end_marker. Candidates are selected exactly as in
scripts/read_hearings.py (150-1200 characters, Japan/bilateral keyword, before the end marker, named speaker) and
written in the same schema to data/kr_hearings_candidates_t22_live.jsonl. Only meetings dated from LIVE_FROM on are
kept, so months already sampled from the v10.3 dataset are not changed. Party comes from the latest party seen for the
speaker in the v10.3 candidates (party_uncertain=True otherwise). Internal file: contains turn texts; never published.
"""
import argparse
import csv
import html
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'kr_hearings_candidates_t22_live.jsonl'
LOG = DATA / 'assembly_records_log.csv'
URL = 'https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={}&type=view'
LIVE_FROM = '2026-10-01'
MAX_MISS = 60
DELAY = 2.0
UA = {'User-Agent': 'DRI-research-client/1.0 (academic research; low-rate)'}
PATTERN = re.compile('일본|한일|대일외교|강제징용|강제동원|위안부|독도|수출규제|지소미아|GSOMIA')
LEGISLATOR_POS = {'위원', '위원장', '위원장대리', '의원', '소위원장', '반장', '의장', '부의장', '의장직무대행', '간사'}

DATE_RE = re.compile(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일')
BLOCK_RE = re.compile(r'<div id="spk_(\d+)" class="([^"]*speaker[^"]*)"([^>]*)>(.*?)(?=<div id="spk_\d+" class="|<div class="minutes_footer|$)', re.S)
ATTR_RE = re.compile(r'data-(name|pos)="([^"]*)"')
SUB_RE = re.compile(r'<span class="spk_sub"[^>]*>(.*?)</span>', re.S)
TAG_RE = re.compile(r'<[^>]+>')


def clean(fragment):
    return re.sub(r'\s+', ' ', html.unescape(TAG_RE.sub(' ', fragment))).strip()


def parse(page):
    """-> (date or None, [turn dicts]) for one minutes page."""
    head = page[page.find('minutes_header'):page.find('minutes_body')]
    m = DATE_RE.search(head)
    day = f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}' if m else None
    body = page[page.find('minutes_body'):]
    end_at = min((i for i in (body.find('산회)'), body.find('산회 )')) if i >= 0), default=len(body))
    turns = []
    for mm in BLOCK_RE.finditer(body):
        seq, cls, attrs, inner = int(mm[1]), mm[2], dict(ATTR_RE.findall(mm[3])), mm[4]
        text = ' '.join(t for t in (clean(s) for s in SUB_RE.findall(inner)) if t)
        pos = attrs.get('pos', '').strip()
        member = pos in LEGISLATOR_POS  # the viewer marks every speaker spk_mem, so the position decides
        role = 'excluded' if '전문위원' in pos or '입법조사관' in pos else 'legislator' if member else 'nonlegislator'
        turns.append(dict(turn_seq=seq, speaker_name=attrs.get('name', '').strip() or None, speaker_pos=pos or None,
                          role_group=role, text=text, after_end_marker=mm.start() > end_at))
    return day, turns


def party_map():
    latest = {}
    for term in ('t21', 't22'):
        p = DATA / f'kr_hearings_candidates_{term}.jsonl'
        for line in p.open(encoding='utf-8'):
            r = json.loads(line)
            if r.get('party') and r['speaker_name']:
                if r['speech_date'] >= latest.get(r['speaker_name'], ('', None))[0]:
                    latest[r['speaker_name']] = (r['speech_date'], r['party'])
    return {k: v[1] for k, v in latest.items()}


def known_last_id():
    ids = [json.loads(l)['conf_num'] for l in (DATA / 'kr_hearings_candidates_t22.jsonl').open(encoding='utf-8')]
    done = [int(r['conf_num']) for r in csv.DictReader(LOG.open(encoding='utf-8'))] if LOG.exists() else []
    return max(ids), set(done)


def fetch(conf):
    try:
        with urlopen(Request(URL.format(conf), headers=UA), timeout=60) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except HTTPError as e:
        return e.code, ''
    except URLError as e:
        return -1, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--start', type=int)
    args = ap.parse_args()
    last, done = known_last_id()
    start = args.start or last + 1
    print(f'dataset ends at conf {last}; logged ids {len(done)}; walking from {start}, stop after {MAX_MISS} misses')
    if not args.execute:
        return
    parties = party_map()
    new_log = not LOG.exists()
    log = LOG.open('a', encoding='utf-8', newline='')
    w = csv.writer(log)
    if new_log:
        w.writerow(['conf_num', 'status', 'date', 'turns', 'candidates', 'kept'])
    misses, conf, total = 0, start, 0
    with OUT.open('a', encoding='utf-8') as out:
        while misses < MAX_MISS:
            if conf in done:
                conf += 1
                continue
            status, page = fetch(conf)
            if status in (403, 429):
                print(f'stop: HTTP {status} at {conf}')
                break
            day, turns = parse(page) if status == 200 and 'minutes_body' in page else (None, [])
            if not turns:
                misses += 1
                w.writerow([conf, status, day or '', 0, 0, 0])
            else:
                misses = 0
                cands = [t for t in turns if 150 <= len(t['text']) <= 1200 and PATTERN.search(t['text'])
                         and not t['after_end_marker'] and t['speaker_name']]
                kept = day is not None and day >= LIVE_FROM
                if kept:
                    for t in cands:
                        party = parties.get(t['speaker_name']) if t['role_group'] == 'legislator' else None
                        out.write(json.dumps(dict(conf_num=conf, speech_date=day, party=party,
                                                  party_uncertain=t['role_group'] == 'legislator' and party is None,
                                                  source='record_viewer', row_group=None, term=22, **t),
                                             ensure_ascii=False) + '\n')
                    total += len(cands)
                w.writerow([conf, status, day or '', len(turns), len(cands), int(kept)])
                print(f'{conf} {day} turns {len(turns)} candidates {len(cands)}{"" if kept else " (before " + LIVE_FROM + ", skipped)"}', flush=True)
            log.flush()
            conf += 1
            time.sleep(DELAY)
    log.close()
    print(f'done at conf {conf - 1}; new candidates {total} -> {OUT.name}')


if __name__ == '__main__':
    main()
