"""DRI v2.1 full annotation of the month-stratified queues (docs/CODEBOOK_v2.md).

    python scripts/annotate_v2.py next --queue jp --count 40      # next unannotated units of a queue
    python scripts/annotate_v2.py save batch.json                  # validate + store (rows in FIELDS order)
    python scripts/annotate_v2.py progress
Annotations: data/dri_v2_annotations.jsonl (internal; contains no source text).
"""
import argparse
from collections import Counter
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.pilot_v2 import DATA, FIELDS, validate  # noqa: E402

QUEUES = {'kr': DATA / 'dri_v2_queue_kr.jsonl', 'jp': DATA / 'dri_v2_queue_jp.jsonl'}
OUT = DATA / 'dri_v2_annotations.jsonl'
VERSION = 'DRI-v2.1'
ANNOTATOR = 'claude-opus-5-5 (Claude Code session, no API)'


def load_queue(name):
    return [json.loads(l) for l in QUEUES[name].read_text(encoding='utf-8').splitlines()]


def load_units():
    return {u['unit_id']: u for name in QUEUES for u in load_queue(name)}


def load_done():
    if not OUT.exists():
        return {}
    return {r['unit_id']: r for r in map(json.loads, OUT.read_text(encoding='utf-8').splitlines())}


def cmd_next(args):
    done = load_done()
    todo = [u for u in load_queue(args.queue) if u['unit_id'] not in done][:args.count]
    for u in todo:
        meta = {k: u.get(k) for k in ('unit_id', 'date', 'speaker', 'speaker_pos', 'party', 'gov_status',
                                      'speaker_level', 'venue')}
        print(json.dumps({k: v for k, v in meta.items() if v is not None}, ensure_ascii=False))
        print(u['text'])
        print()


def cmd_save(args):
    units, done = load_units(), load_done()
    for values in json.loads(Path(args.file).read_text(encoding='utf-8-sig')):
        assert len(values) == len(FIELDS), values[0]
        r = dict(zip(FIELDS, values))
        r.update(annotation_version=VERSION, annotator=ANNOTATOR, text_sha256=units[r['unit_id']]['text_sha256'])
        validate(r, units)
        done[r['unit_id']] = r
    order = {uid: i for i, uid in enumerate(units)}
    rows = sorted(done.values(), key=lambda r: order[r['unit_id']])
    OUT.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    cmd_progress(args)


def cmd_progress(_):
    units, done = load_units(), load_done()
    for name in QUEUES:
        ids = [u['unit_id'] for u in load_queue(name)]
        ann = [done[i] for i in ids if i in done]
        rel = [r for r in ann if r['relevance'] in {'core', 'peripheral'}]
        print(f'{name}: {len(ann)}/{len(ids)} annotated; relevance {dict(Counter(r["relevance"] for r in ann))}; '
              f'rung {dict(sorted(Counter(r["rung"] for r in rel).items()))}; '
              f'too_soft {sum(r["domestic_pressure"] == "too_soft" for r in rel)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    nxt = sub.add_parser('next')
    nxt.add_argument('--queue', choices=QUEUES, required=True)
    nxt.add_argument('--count', type=int, default=40)
    save = sub.add_parser('save')
    save.add_argument('file')
    sub.add_parser('progress')
    args = parser.parse_args()
    globals()['cmd_' + args.cmd](args)
