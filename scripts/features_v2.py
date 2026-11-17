"""Monthly feature table from the DRI v2.2 annotations (+ registry targets) for the forecasting model.

    python scripts/features_v2.py      # -> data/dri_v2_monthly.csv

One row per month 2015-01..last annotated month. Country prefixes: kr_ (National Assembly), jp_ (Diet).
Each month of a country is a random sample of up to 25 (KR) / 15 (JP) relevant turns, so shares are
estimated within the month; `*_pool` is the number of relevant turns that month (attention volume).
A single session is capped at SESSION_CAP units of weight per month so that one sitting (e.g. a
resolution debate) cannot dominate a month. Targets come from the verified action registry
(data/dri_event_truth.csv): escalation / cooperation actions in the next 1-3 months (t+1..t+3).
Registry months without actions are treated as 0; the registry is curated, not exhaustive.
"""
import csv
from collections import defaultdict
from datetime import date
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_v2 import QUEUES, load_done, load_queue  # noqa: E402

DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_monthly.csv'
TRUTH = DATA / 'dri_event_truth.csv'
SESSION_CAP = 3.0
HORIZON = 3
TOPICS = {
    'dokdo': lambda r: 'dokdo_takeshima' in r['history_frame'],
    'labor': lambda r: bool({'forced_labor', 'sado'} & set(r['history_frame'])),
    'comfort': lambda r: 'comfort_women' in r['history_frame'],
    'fukushima': lambda r: 'fukushima_seafood' in r['material_issue'],
    'trade': lambda r: bool({'export_controls', 'trade_balance', 'critical_materials'} & set(r['material_issue'])),
    'security': lambda r: 'defense_security' in r['material_issue'],
}


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def session_of(unit_id):
    kind, rest = unit_id.split(':', 1)
    return f'{kind}:{rest.split(":")[0]}' if kind == 'kr' else f'jp:{rest.rsplit("_", 1)[0]}'


def country_features(units, done):
    by_month = defaultdict(list)
    for u in units:
        by_month[u['date'][:7]].append((u, done[u['unit_id']]))
    out = {}
    for month, items in by_month.items():
        per_session = defaultdict(int)
        for u, _ in items:
            per_session[session_of(u['unit_id'])] += 1
        w = [min(1.0, SESSION_CAP / per_session[session_of(u['unit_id'])]) for u, _ in items]
        W = sum(w)
        rel = [(wi, u, r) for wi, (u, r) in zip(w, items) if r['relevance'] in {'core', 'peripheral'}]

        def share(pred, pool=None):
            pool = [(wi, u, r) for wi, (u, r) in zip(w, items)] if pool is None else pool
            tot = sum(wi for wi, _, _ in pool)
            return sum(wi for wi, u, r in pool if pred(u, r)) / tot if tot else 0.0

        f = dict(pool=items[0][0]['month_relevant_pool'], n=len(items),
                 rel=share(lambda u, r: r['relevance'] in {'core', 'peripheral'}),
                 r1=share(lambda u, r: r['relevance'] in {'core', 'peripheral'} and r['rung'] >= 1),
                 r2=share(lambda u, r: r['relevance'] in {'core', 'peripheral'} and r['rung'] >= 2),
                 r3=share(lambda u, r: r['relevance'] in {'core', 'peripheral'} and r['rung'] >= 3),
                 r4=share(lambda u, r: r['relevance'] in {'core', 'peripheral'} and r['rung'] >= 4),
                 max_rung=max((r['rung'] for _, _, r in rel), default=0),
                 urgency=share(lambda u, r: r.get('urgency', False)),
                 too_soft=share(lambda u, r: r['domestic_pressure'] == 'too_soft'),
                 too_hard=share(lambda u, r: r['domestic_pressure'] == 'too_hard'),
                 coop1=share(lambda u, r: r['coop'] >= 1), coop2=share(lambda u, r: r['coop'] >= 2),
                 elite=share(lambda u, r: u.get('speaker_level') in {'L4', 'L5'}),
                 elite_r3=share(lambda u, r: u.get('speaker_level') in {'L4', 'L5'} and r['rung'] >= 3),
                 frame_link=share(lambda u, r: r['frame_link']),
                 dprk=share(lambda u, r: r['dprk_reference']))
        for name, pred in TOPICS.items():
            f[f'topic_{name}'] = share(lambda u, r, p=pred: r['relevance'] in {'core', 'peripheral'} and p(r))
        f['conf_volume'] = f['pool'] * f['r3']   # estimated number of R3+ turns in the month
        f['n_sessions'] = len(per_session)
        f['weight_total'] = round(W, 3)
        out[month] = f
    return out


def registry_targets(months):
    rows = list(csv.DictReader(TRUTH.open(encoding='utf-8-sig')))
    esc, coop = defaultdict(int), defaultdict(int)
    for r in rows:
        (esc if r['direction'] == 'escalation' else coop if r['direction'] == 'cooperation' else {})[
            r['event_date'][:7]] = 1 if r['direction'] in {'escalation', 'cooperation'} else 0
    return {m: dict(esc_now=esc.get(m, 0), coop_now=coop.get(m, 0),
                    esc_next=int(any(esc.get(month_add(m, k), 0) for k in range(1, HORIZON + 1))),
                    coop_next=int(any(coop.get(month_add(m, k), 0) for k in range(1, HORIZON + 1))))
            for m in months}


def main():
    done = load_done()
    feats = {name: country_features(load_queue(name), done) for name in QUEUES}
    last = max(max(f) for f in feats.values())
    months, m = [], '2015-01'
    while m <= last:
        months.append(m)
        m = month_add(m, 1)
    targets = registry_targets(months)
    cols = sorted({k for f in feats.values() for v in f.values() for k in v})
    rows = []
    for m in months:
        row = dict(month=m)
        for name in QUEUES:
            f = feats[name].get(m)
            for k in cols:
                row[f'{name}_{k}'] = (round(f[k], 4) if isinstance(f[k], float) else f[k]) if f else (0 if k in {'pool', 'n'} else '')
        row.update(targets[m])
        # Last HORIZON months cannot have a complete future window yet.
        if m > month_add(date.today().strftime('%Y-%m'), -HORIZON - 1):
            row['esc_next'] = row['coop_next'] = ''
        rows.append(row)
    with OUT.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    filled = {name: sum(1 for m in months if m in feats[name]) for name in QUEUES}
    pos = sum(r['esc_next'] == 1 for r in rows)
    print(f'{OUT.name}: {len(rows)} months {months[0]}..{months[-1]}; months with data {filled}; '
          f'esc_next=1 in {pos} months; columns {len(rows[0])}')


if __name__ == '__main__':
    main()
