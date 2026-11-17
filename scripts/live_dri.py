"""Review official material locally and seal a prospective 30-day DRI snapshot."""
import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.storage import Store
from scripts.annotate_llm_pilot import DB, data
from scripts.bilateral_dri import Rhetoric, calculate, load_corpora, named_speaker
from scripts.collect_live_dri import MOSCOW
from scripts.prediction_backtest import EXCLUDED_DIRECTIONS, Speech, select_speeches

METHOD = 'DRI-90d-45d-v1/live-strict-v1'
DIRECTIONS = {'confrontational', 'cooperative', 'mixed', 'neutral', 'irrelevant', 'uncertain'}
FIELDS = {'id', 'content_sha256', 'direction', 'confrontation_intensity', 'cooperation_present',
          'target_country', 'position_ownership', 'confidence', 'summary_ru', 'reason_ru'}


def instant(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timestamp must specify a timezone')
    return value


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(text):
    return sha256(text.encode()).hexdigest()


def review_rows(db, *, pending=False):
    sql = '''SELECT q.id, q.document_id, q.statement_id, q.available_at, q.evidence_json, d.text,
                    a.reviewed_at, a.annotation_json
             FROM live_review_queue q JOIN documents d ON d.id=q.document_id
             LEFT JOIN live_annotations a ON a.id=q.id'''
    if pending:
        sql += ' WHERE a.id IS NULL'
    sql += ' ORDER BY q.available_at,q.id'
    return [
        dict(json.loads(evidence), id=identity, document_id=doc, statement_id=statement,
             available_at=available, text=text, reviewed_at=reviewed,
             annotation=json.loads(annotation) if annotation else None)
        for identity, doc, statement, available, evidence, text, reviewed, annotation in db.execute(sql)
    ]


def import_batch(db, batch, timestamp):
    if not isinstance(batch, list) or len({item['id'] for item in batch}) != len(batch):
        raise ValueError('Expected a list of unique queue IDs')
    queue = {row['id']: row for row in review_rows(db)}
    additions = []
    for label in batch:
        if set(label) != FIELDS:
            raise ValueError(f'Unexpected review fields for {label["id"]}')
        row = queue.get(label['id'])
        if not row or digest(row['text']) != label['content_sha256'] or row['content_sha256'] != label['content_sha256']:
            raise ValueError(f'Unknown ID or source text changed: {label["id"]}')
        direction, intensity = label['direction'], label['confrontation_intensity']
        if (direction not in DIRECTIONS or (direction == 'uncertain' and intensity is not None)
                or (direction != 'uncertain' and type(intensity) is not int)
                or (direction in {'mixed', 'confrontational'} and intensity not in (1, 2, 3))
                or (direction in {'neutral', 'cooperative', 'irrelevant'} and intensity != 0)):
            raise ValueError(f'Invalid direction or intensity: {label["id"]}')
        expected = 'ROK' if row['country'] == 'JPN' else 'JPN'
        if (type(label['cooperation_present']) is not bool
                or (direction in {'cooperative', 'mixed'} and not label['cooperation_present'])
                or (direction not in EXCLUDED_DIRECTIONS and label['target_country'] not in {expected, 'multiple'})
                or label['position_ownership'] not in {'own','reported','quoted','historical','unclear','mixed'}
                or label['confidence'] not in {'high','medium','low'}
                or any(not isinstance(label[k], str) or not label[k].strip() for k in ('summary_ru','reason_ru'))
                or instant(row['available_at']) > timestamp):
            raise ValueError(f'Invalid annotation: {label["id"]}')
        annotation = dict(label, annotation_method='codex_contextual_model', annotation_version='DRI-LLM-pilot-1')
        if row['annotation'] is not None:
            if row['annotation'] != annotation:
                raise ValueError(f'Conflicting annotation: {label["id"]}')
            continue
        additions.append((row['id'], timestamp.isoformat(), canonical(annotation)))
    with db:
        db.executemany('INSERT INTO live_annotations VALUES (?,?,?)', additions)
    return len(additions)


def verify_journal(db):
    history = []
    previous = '0' * 64
    for seq, day, method, issued, end, prior, record_hash, payload in db.execute(
        'SELECT sequence,assessment_date,method,issued_at,horizon_end,previous_hash,record_hash,payload '
        'FROM live_forecasts ORDER BY sequence'
    ):
        record = json.loads(payload)
        context = record.get('research_context')
        if context:
            cutoff = instant(context['collection_cutoff'])
            if (cutoff > instant(issued)
                    or any(instant(row['available_at']) > cutoff for row in record['inputs'] if 'available_at' in row)
                    or any(event['known_since'] > day for event in context['known_events'])):
                raise ValueError('Prospective collection cutoff or known-event chronology failed')
        horizon = date.fromisoformat(day) + timedelta(days=30)
        if (seq != len(history)+1 or prior != previous or digest(payload) != record_hash
                or (record['sequence'], record['assessment_date'], record['method'], record['issued_at'],
                    record['horizon_end'], record['previous_hash']) != (seq, day, method, issued, end, prior)
                or horizon.isoformat() != end
                or record['horizon_start'] != (date.fromisoformat(day)+timedelta(days=1)).isoformat()
                or instant(issued).astimezone(MOSCOW).date() != date.fromisoformat(day)
                or (history and instant(issued) < instant(history[-1]['issued_at']))
                or any(row['availability_date'] > day
                       or any(instant(row[key]) > instant(issued) for key in ('available_at','reviewed_at') if key in row)
                       for row in record['inputs'])):
            raise ValueError(f'Prospective journal verification failed at row {seq}')
        previous = record_hash
        history.append(dict(record, record_hash=record_hash))
    return history


def usable_reviews(db, issued):
    for row in review_rows(db):
        label = row['annotation']
        if not label or label['direction'] in EXCLUDED_DIRECTIONS:
            continue
        if digest(row['text']) != row['content_sha256']:
            raise ValueError(f'Live source text changed: {row["id"]}')
        captured = instant(row['available_at'])
        reviewed = instant(row['reviewed_at'])
        if captured > issued or reviewed > issued:
            continue
        spoken = date.fromisoformat(row['spoken_date'])
        published = date.fromisoformat(row['published_date']) if row['published_date'] else spoken
        # Capture is the actual availability bound for this prospective pilot.
        available = max(captured.astimezone(MOSCOW).date(), spoken, published)
        if available > issued.astimezone(MOSCOW).date():
            continue
        yield row, Rhetoric(Speech(
            spoken, available, available, 'collector_capture_bound', 'collector_capture_bound',
            named_speaker(row['speaker']), row['source'], label['direction'],
            label['confrontation_intensity'], label['cooperation_present'], row['id'],
        ), row['country'], row['institution'])


def frozen_references(db, ids):
    if not ids:
        return {}
    units, annotations = data()
    labels = {row['unit_id']: row for row in annotations}
    references = {}
    for identity in ids:
        docs = []
        for doc_id in sorted({fragment['ref']['document_id'] for fragment in units[identity]['fragments']}):
            source, url, sha = db.execute('SELECT source,url,text_sha256 FROM documents WHERE id=?', (doc_id,)).fetchone()
            docs.append(dict(document_id=doc_id, source=source, url=url, document_sha256=sha))
        references[identity] = dict(id=identity, documents=docs, annotation_sha256=digest(canonical(labels[identity])))
    return references


def issue(db, issued, research_context=None):
    day = issued.astimezone(MOSCOW).date()
    cutoff = issued
    if research_context is not None:
        cutoff = instant(research_context['collection_cutoff'])
        if cutoff > issued or cutoff.astimezone(MOSCOW).date() != day:
            raise ValueError('Collection cutoff must precede issuance on the same Moscow day')
        if any(date.fromisoformat(e['known_since']) > day for e in research_context['known_events']):
            raise ValueError('Future knowledge cannot enter the prospective context')
    db.execute('BEGIN IMMEDIATE')
    try:
        journal = verify_journal(db)
        existing = next((row for row in journal if row['assessment_date'] == day.isoformat() and row['method'] == METHOD), None)
        if existing:
            db.commit()
            return existing, False
        if journal and issued < instant(journal[-1]['issued_at']):
            raise ValueError('Clock precedes the last journal issue')
        reviewed = [(row, record) for row, record in usable_reviews(db, issued)
                    if instant(row['available_at']) <= cutoff]
        if not any(max(record.speech.strict_available, instant(row['reviewed_at']).astimezone(MOSCOW).date()) == day
                   for row, record in reviewed):
            raise ValueError('No newly confirmed, reviewed data for a prospective issue today (Moscow time)')
        original, strict_corpus = load_corpora()
        expanded = strict_corpus + [record for _, record in reviewed]
        calculation = calculate(day, 'strict', original, expanded)
        included = select_speeches(day, [record.speech for record in expanded], mode='strict')
        ids = {speech.unit_id for speech, _, _ in included if speech.direction not in EXCLUDED_DIRECTIONS}
        new_ids = {row['id'] for row, _ in reviewed} & ids
        if not new_ids:
            raise ValueError('New confirmed texts are outside the 90-day window')
        prior = frozen_references(db, ids - new_ids)
        inputs = []
        for speech, when, basis in included:
            if speech.unit_id not in ids:
                continue
            if speech.unit_id in new_ids:
                row = next(row for row, _ in reviewed if row['id'] == speech.unit_id)
                evidence = {key: row[key] for key in ('id','document_id','statement_id','country','source','url',
                            'title','speaker','institution','content_sha256','fetch_sha256','available_at','reviewed_at')}
                evidence.update(annotation_sha256=digest(canonical(row['annotation'])),
                                direction=row['annotation']['direction'], summary_ru=row['annotation']['summary_ru'])
            else:
                evidence = prior[speech.unit_id]
            inputs.append(dict(evidence, spoken_date=speech.spoken.isoformat(), availability_date=when.isoformat(),
                               availability_basis=basis, intensity=speech.intensity))
        record = dict(
            sequence=len(journal)+1, method=METHOD, issued_at=issued.isoformat(),
            assessment_date=day.isoformat(), window_start=(day-timedelta(days=89)).isoformat(),
            horizon_start=(day+timedelta(days=1)).isoformat(), horizon_end=(day+timedelta(days=30)).isoformat(),
            previous_hash=journal[-1]['record_hash'] if journal else '0'*64, calculation=calculation,
            inputs=inputs, new_inputs=len(new_ids),
        )
        if research_context is not None:
            record['research_context'] = research_context
        payload = canonical(record)
        seal = digest(payload)
        db.execute('INSERT INTO live_forecasts VALUES (?,?,?,?,?,?,?,?)',
                   (record['sequence'], record['assessment_date'], METHOD, record['issued_at'],
                    record['horizon_end'], record['previous_hash'], seal, payload))
        db.commit()
        return dict(record, record_hash=seal), True
    except BaseException:
        db.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('queue', help='Read new source excerpts for semantic annotation in Codex')
    imp = sub.add_parser('import', help='Import a completed local JSON array of Codex annotations')
    imp.add_argument('path', type=Path)
    issuance = sub.add_parser('issue', help='Issue today’s prospective snapshot')
    issuance.add_argument('--context', type=Path, help='Local cutoff and known-event context, sealed without affecting score')
    sub.add_parser('verify', help='Check and display journal seals')
    args = parser.parse_args()
    store = Store()
    try:
        if args.command == 'queue':
            for row in review_rows(store.db, pending=True):
                print(json.dumps(row, ensure_ascii=False))
        elif args.command == 'import':
            batch = json.loads(args.path.read_text(encoding='utf-8-sig'))
            print(json.dumps(dict(imported=import_batch(store.db, batch, datetime.now(timezone.utc)))))
        elif args.command == 'issue':
            context = json.loads(args.context.read_text(encoding='utf-8')) if args.context else None
            record, added = issue(store.db, datetime.now(timezone.utc), context)
            print(json.dumps(dict(added=added, **record), ensure_ascii=False, indent=2))
        else:
            for row in verify_journal(store.db):
                print(row['assessment_date'], row['issued_at'], row['horizon_end'], row['record_hash'])
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
