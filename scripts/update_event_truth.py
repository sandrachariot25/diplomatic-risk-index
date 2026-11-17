"""Update verified bilateral actions and a daily, nullable 30-day target."""
import argparse
from collections import Counter
import csv
from datetime import date, timedelta
from html import escape
import io
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.connectors.gdelt_event_days import fetch_day
from dri.identity import fingerprint, normalize_url
from dri.paths import DATA, ROOT, inside, write_generated
from dri.storage import Store

START = date(2015, 1, 1)
AS_OF = date(2026, 11, 5)
SAMPLES = DATA / 'dri_event_gdelt_samples.json'
DAY = timedelta(days=1)
RULE_VERSION = 'DRI-event-action-1'


def public_url_key(url):
    try:
        # Article identity is independent of an HTTP to HTTPS upgrade.
        return normalize_url(url).split('://', 1)[1]
    except ValueError:
        return None


def read_actions():
    actions = {}
    raw_count = 0
    for line in (ROOT/'config/dri_event_actions.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        raw_count += 1
        day = date.fromisoformat(record['event_date'])
        public = date.fromisoformat(record['first_public_date'])
        countries = record['initiator'], record['target_country']
        if not START <= day <= AS_OF or not START <= public <= AS_OF:
            raise ValueError('Action or announcement outside observed period')
        if countries not in {('JPN','ROK'), ('ROK','JPN'), ('JPN+ROK','JPN+ROK')}:
            raise ValueError('Expected the Japan–Republic of Korea dyad')
        if record['direction'] not in {'escalation','cooperation','neutral'}:
            raise ValueError('Invalid action direction')
        if (bool(record['episode_id']) != (record['direction'] == 'escalation')
                or not record['inclusion_evidence'].strip()):
            raise ValueError('Each escalation needs an episode and each action needs inclusion evidence')
        for url in [record['primary_source'], *record['additional_sources']]:
            normalize_url(url)
        record['event_id'] = 'dri-act-' + fingerprint(RULE_VERSION, record['action_key'])[:20]
        record['verification_status'] = 'confirmed'
        record['rule_version'] = RULE_VERSION
        key = record['action_key']
        if key in actions:
            existing = actions[key]
            core = ('event_date','initiator','target_country','action_type','direction','description',
                    'episode_id','inclusion_evidence')
            if any(existing[field] != record[field] for field in core):
                raise ValueError(f'Conflicting review of action {key}')
            sources = [existing['primary_source'], *existing['additional_sources'],
                       record['primary_source'], *record['additional_sources']]
            existing['additional_sources'] = list(dict.fromkeys(sources))[1:]
            existing['first_public_date'] = min(existing['first_public_date'], record['first_public_date'])
        else:
            actions[key] = record
    return sorted(actions.values(), key=lambda row: (row['event_date'], row['event_id'])), raw_count


def update_samples(days):
    samples = json.loads(SAMPLES.read_text(encoding='utf-8')) if SAMPLES.exists() else {}
    for day in sorted(set(days)):
        if not START <= day <= AS_OF:
            raise ValueError('Archive day outside observed period')
        if day.isoformat() not in samples:
            try:
                samples[day.isoformat()] = fetch_day(day)
            except (OSError, ValueError) as exc:
                print(f'GDELT {day}: {exc}', file=sys.stderr)
                continue
            write_generated(SAMPLES, json.dumps(samples, ensure_ascii=False, separators=(',', ':'))+'\n')
    return samples


def sync_actions(db, actions, samples):
    candidates = {}
    raw_count = 0
    for sample in samples.values():
        for row in sample['records']:
            raw_count += 1
            row = {**row, 'archive_sha256': sample['sha256'], 'verification_status': 'machine_candidate'}
            key = row['candidate_id']
            if key in candidates and candidates[key]['record_sha256'] != row['record_sha256']:
                raise ValueError(f'Conflicting archive payload for {key}')
            candidates.setdefault(key, row)
    db.row_factory = sqlite3.Row
    existing_gdelt = list(db.execute('SELECT * FROM gdelt_events ORDER BY event_id'))
    for record in existing_gdelt:
        row = dict(record)
        key = 'gdelt2:' + row['event_id']
        candidates[key] = {**row, 'candidate_id': key, 'url': row['source_url'],
                           'cameo': row['event_code'], 'verification_status': 'machine_candidate'}
    # Only links to articles already checked in the review manifest. No matching by date alone.
    source_events = {}
    for action in actions:
        for url in [action['primary_source'], *action['additional_sources']]:
            source_events.setdefault(public_url_key(url), []).append(action)
    for action in actions:
        action['gdelt_links'] = []
        action['cameo_codes'] = []
    links = []
    for key,row in sorted(candidates.items()):
        matches = source_events.get(public_url_key(row['url']), [])
        if len(matches) != 1:
            continue
        action = matches[0]
        gap = abs((date.fromisoformat(row['event_date']) - date.fromisoformat(action['event_date'])).days)
        if gap > 3:
            continue
        action['gdelt_links'].append(key)
        action['cameo_codes'].append(row['cameo'])
        links.append((action['event_id'],key))
    with db:
        action_ids = json.dumps([action['event_id'] for action in actions])
        db.execute('DELETE FROM diplomatic_action_candidate_links WHERE event_id NOT IN (SELECT value FROM json_each(?))',
                   (action_ids,))
        db.execute('DELETE FROM diplomatic_actions WHERE event_id NOT IN (SELECT value FROM json_each(?))',
                   (action_ids,))
        for action in actions:
            action['cameo_codes'] = sorted(set(action['cameo_codes']))
            db.execute('''INSERT INTO diplomatic_actions VALUES (?,?,?,?,?)
                          ON CONFLICT(event_id) DO UPDATE SET event_date=excluded.event_date,
                          direction=excluded.direction, evidence_json=excluded.evidence_json
                          WHERE evidence_json<>excluded.evidence_json''',
                       (action['event_id'],action['action_key'],action['event_date'],action['direction'],
                        json.dumps(action, ensure_ascii=False, sort_keys=True)))
        for key,row in sorted(candidates.items()):
            db.execute('INSERT INTO diplomatic_event_candidates VALUES (?,?) ON CONFLICT DO NOTHING',
                       (key,json.dumps(row, ensure_ascii=False, sort_keys=True)))
        for action in actions:
            db.execute('DELETE FROM diplomatic_action_candidate_links WHERE event_id=? AND candidate_id NOT IN (SELECT value FROM json_each(?))',
                       (action['event_id'],json.dumps(action['gdelt_links'])))
        db.executemany('INSERT INTO diplomatic_action_candidate_links VALUES (?,?) ON CONFLICT DO NOTHING',links)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Event import violates a foreign key')
    return raw_count, len(candidates)-len(existing_gdelt), len(existing_gdelt), len(links)


def calendar(actions, covered_days, as_of=AS_OF):
    escalations = [(date.fromisoformat(r['event_date']),r['event_id'])
                   for r in actions if r['direction']=='escalation']
    for offset in range((as_of-START).days+1):
        day = START + offset*DAY
        end = day + 30*DAY
        events = [key for when,key in escalations if day < when <= min(end,as_of)]
        covered = sum(day + step*DAY in covered_days for step in range(1,31))
        if events:
            target, status = 1, 'confirmed_escalation'
        elif end > as_of:
            target, status = None, 'right_censored'
        elif covered == 30:
            target, status = 0, 'reviewed_no_escalation'
        else:
            target, status = None, 'insufficient_coverage'
        yield dict(assessment_date=day.isoformat(), window_start=(day+DAY).isoformat(),
                   window_end=end.isoformat(), target_30d=target, status=status,
                   reviewed_days=covered, escalation_event_ids='|'.join(events))


def coverage_days(path):
    if path is None:
        return set()
    result = set()
    for row in json.loads(inside(path).read_text(encoding='utf-8')):
        start,end = (date.fromisoformat(row[key]) for key in ('start','end'))
        if not START <= start <= end <= AS_OF or not row['reviewer'].strip() or not row['scope_notes'].strip():
            raise ValueError('Invalid audited coverage interval')
        for key in ('rok_sources','jpn_sources','independent_sources'):
            if not row[key]:
                raise ValueError('Negative coverage needs evidence from both sides and an independent channel')
            for url in row[key]:
                normalize_url(url)
        result.update(start + i*DAY for i in range((end-start).days+1))
    return result


def save_csv(path, records):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(records[0]), lineterminator='\n')
    writer.writeheader()
    for row in records:
        writer.writerow({key: '|'.join(value) if isinstance(value,list) else value for key,value in row.items()})
    write_generated(path, '\ufeff'+buffer.getvalue())


def timeline(actions, targets):
    labels = {'escalation':'Эскалация','cooperation':'Сотрудничество','neutral':'Нейтральное действие'}
    items = []
    for action in actions:
        references = [action['primary_source'], *action['additional_sources']]
        links = ' · '.join(f'<a href="{escape(url, quote=True)}">{"Первоисточник" if i==0 else f"Подтверждение {i}"}</a>'
                           for i,url in enumerate(references))
        items.append(f'<article class="{action["direction"]}" id="{action["event_id"]}">'
                     f'<time datetime="{action["event_date"]}">{action["event_date"]}</time>'
                     f'<h2>{labels[action["direction"]]} · {escape(action["action_type"])}</h2>'
                     f'<small>{escape(action["initiator"])} → {escape(action["target_country"])} · '
                     f'первое подтверждённое сообщение {action["first_public_date"]}</small>'
                     f'<p>{escape(action["description"])}</p>'
                     f'<p>{escape(action["episode_id"])}</p><p>{links}</p></article>')
    write_generated(ROOT/'docs/DRI_events_timeline.html', f'''<!doctype html>
<html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DRI · Дипломатические действия</title>
<style>
body{{font:1rem/1.5 system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1.2rem;color:#172033;background:#f5f7fa}}
article{{background:white;border-left:.35rem solid #64748b;margin:1rem 0;padding:1rem 1.25rem}}
.escalation{{border-color:#b42331}} .cooperation{{border-color:#157253}}
h2{{font-size:1.08rem;margin:.3rem 0}} time{{font-weight:700}} a{{color:#135a9a}}
</style>
<main><h1>Республика Корея и Япония · дипломатические действия</h1>
<p>2015–2026, срез на {AS_OF}. Подтверждённых действий {len(actions)}.</p>
<p>Дневной календарь · эскалация в горизонте 30 дней {targets[1]} ·
проверенное отсутствие {targets[0]} · неопределённый исход {targets[None]}.</p>
{''.join(items)}
</main></html>''')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-day', type=date.fromisoformat, action='append', default=[])
    parser.add_argument('--reviewed-coverage', type=Path)
    args = parser.parse_args()
    actions, review_count = read_actions()
    covered = coverage_days(args.reviewed_coverage)
    samples = update_samples(args.fetch_day)
    store = Store()
    try:
        raw, unique, legacy, links = sync_actions(store.db, actions, samples)
        # Read back the exact records just validated against the review manifest.
        actions = [json.loads(row[0]) for row in store.db.execute(
            'SELECT evidence_json FROM diplomatic_actions ORDER BY event_date,event_id')]
    finally:
        store.db.close()
    days = list(calendar(actions,covered))
    targets = Counter(row['target_30d'] for row in days)
    save_csv(DATA/'dri_event_truth.csv',actions)
    save_csv(DATA/'dri_event_calendar.csv',days)
    timeline(actions,targets)
    print(json.dumps(dict(actions=len(actions), direction=Counter(row['direction'] for row in actions),
                         years=Counter(row['event_date'][:4] for row in actions),
                         primary_sources=len({row['primary_source'] for row in actions}),
                         merged_review_rows=review_count-len(actions), archives=len(samples),
                         archive_rows=raw, unique_archive_candidates=unique, legacy_candidates=legacy,
                         reviewed_candidate_links=links, targets=targets,
                         calendar_status=Counter(row['status'] for row in days)), ensure_ascii=False))


if __name__ == '__main__':
    main()
