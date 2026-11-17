"""Honest test of Korean court rulings as triggers, using the court docket (data/court_rulings.csv) instead of the
protest-selected registry.

    python scripts/courts_v2.py      # -> data/dri_v2_courts.json

For every ruling (month m): did a GDELT flare-up start in m or m+1, and how far was the conflict share above its
12-month norm (max of m, m+1)? Grouped by outcome for the plaintiffs (favourable: win, enforcement, procedural win;
unfavourable: loss, dismissal) and by whether Japan lodged an official protest. Then the monitor rule that can be
used in advance - "a ruling is scheduled in the next 3 months" (outcome unknown) - against months without one.
Caveat: the docket covers the main rulings found in public sources (Supreme Court, notable lower-court rulings),
not every lower-court decision; four dates are flagged for checking.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.forecast_gdelt_v2 import build  # noqa: E402

DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_courts.json'
FAV = {'plaintiff_win', 'enforcement', 'procedural_win'}


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def main():
    rulings = list(csv.DictReader((DATA / 'court_rulings.csv').open(encoding='utf-8')))
    episodes = {e['month'] for e in json.loads((DATA / 'dri_v2_episodes.json').read_text(encoding='utf-8'))['episodes']}
    rows = build()
    gap = {r['month']: r['g_gap'] for r in rows}
    first, last_ep = min(gap), max(episodes)
    out = []
    for r in rulings:
        m = r['date'][:7]
        if m < first or month_add(m, 1) > max(gap):
            continue
        # an episode "follows" if a flare-up starts in m or m+1, or m/m+1 is inside a flare-up already under way
        follows = any(month_add(m, k) in episodes for k in (0, 1))
        peak = max(gap.get(m, np.nan), gap.get(month_add(m, 1), np.nan))
        out.append(dict(r, month=m, flareup_follows=follows, conflict_gap_sd=round(float(peak), 2),
                        favourable=r['decision'] in FAV))

    def summary(sel):
        return dict(n=len(sel), followed=sum(x['flareup_follows'] for x in sel),
                    share=round(sum(x['flareup_follows'] for x in sel) / len(sel), 2) if sel else None,
                    mean_gap_sd=round(float(np.mean([x['conflict_gap_sd'] for x in sel])), 2) if sel else None)
    groups = {'все решения': out,
              'благоприятные для истцов': [x for x in out if x['favourable']],
              'неблагоприятные (отказ, отклонение)': [x for x in out if not x['favourable']],
              'с протестом Японии': [x for x in out if x['japan_protest'] == 'yes'],
              'без протеста Японии': [x for x in out if x['japan_protest'] == 'no'],
              'Верховный суд': [x for x in out if x['level'] == 'supreme']}
    base_months = [m for m in gap if m <= last_ep]
    base_share = sum(any(month_add(m, k) in episodes for k in (0, 1)) for m in base_months) / len(base_months)
    # Advance rule: any ruling in t+1..t+3 (outcome unknown in advance)
    ruling_months = {x['month'] for x in out}
    lab = [m for m in gap if month_add(m, 3) <= last_ep]
    ahead = [m for m in lab if any(month_add(m, k) in ruling_months for k in (1, 2, 3))]
    none = [m for m in lab if m not in ahead]
    flare = lambda m: any(month_add(m, k) in episodes for k in (1, 2, 3))
    rule = dict(months_with_ruling_ahead=len(ahead), share_flareup_ahead=round(sum(map(flare, ahead)) / len(ahead), 2),
                months_without=len(none), share_without=round(sum(map(flare, none)) / len(none), 2),
                episodes_after_a_ruling_month=sorted({month_add(m, k) for m in ahead for k in (1, 2, 3)} & episodes))
    report = dict(groups={k: summary(v) for k, v in groups.items()}, base_share_any_month=round(base_share, 2),
                  advance_rule=rule, rulings=out)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rulings in GDELT window: {len(out)}; base: a flare-up starts in m or m+1 for {base_share:.0%} of months')
    for k, v in report['groups'].items():
        print(f'  {k:38} n={v["n"]:2}  обострение следом: {v["followed"]}/{v["n"]} ({v["share"]})  '
              f'средний пик конфликтности {v["mean_gap_sd"]:+} SD')
    print('advance rule (ruling in next 3 months):', rule)
    print('\nper ruling:')
    for x in out:
        print(f"  {x['date']} {x['decision']:15} protest={x['japan_protest']:7} follows={x['flareup_follows']!s:5} "
              f"gap={x['conflict_gap_sd']:+.2f}  {x['defendant']}")


if __name__ == '__main__':
    main()
