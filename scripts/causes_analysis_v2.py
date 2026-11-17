"""Final causal typing of the 14 flare-ups (expert-reviewed) and the conditions that preceded each kind.

    python scripts/causes_analysis_v2.py    # -> data/dri_v2_episode_causes_final.json (+ printed tables)

Reads data/dri_v2_episode_causes.xlsx. Where the expert answered "да" and left the other columns empty, the
model draft is taken as agreed (expert, 13.11.2026: "where the model was confident I agreed"); the material
layer then follows the draft (second layer only for 2019-07). Groups: episodes with a material cause (main or
second layer) vs. without. For each layer, the pre-episode mean (t-3..t-1) is expressed in standard deviations
from the calm-month mean. With 5 vs 8 episodes this is descriptive, not a significance test.
"""
import json
import sys
from pathlib import Path

import numpy as np
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.episodes_v2 import FEATURES, add_approval, add_material, add_material2  # noqa: E402
from scripts.forecast_gdelt_v2 import build  # noqa: E402

DATA = ROOT / 'data'
BOOK = DATA / 'dri_v2_episode_causes.xlsx'
OUT = DATA / 'dri_v2_episode_causes_final.json'
DRAFT_MATERIAL = {'2019-07': 'вторым слоем'}
# Established after the expert review from the court docket (13.11.2026); to be confirmed by the expert.
OVERRIDES = {'2026-08': dict(final_type='суды и история', trigger='Верховный суд РК утвердил компенсацию от Nippon '
                             'Steel семье Мин Мун Сика (12.08.2026); протест Японии в тот же день',
                             deep_cause='Продолжение судебной линии по принудительному труду', material='нет',
                             comment='уточнено по реестру судов 13.11.2026, подтверждено экспертом')}


def load_final():
    rows = list(load_workbook(BOOK, read_only=True)['Эпизоды'].iter_rows(values_only=True))
    h = rows[0]
    col = {name: h.index(name) for name in h}
    out = []
    for r in rows[1:]:
        m = r[col['Месяц']]
        verdict = r[col['Верно?']]
        etype = r[col['Тип причины (эксперт)']]
        final_type = etype or (r[col['Черновик: тип']] if verdict == 'да' else 'неясно / возможный артефакт')
        material = r[col['Материальная причина была? (да/нет/вторым слоем)']] or \
            (DRAFT_MATERIAL.get(m, 'нет') if verdict == 'да' else None)
        out.append(dict(month=m, verdict=verdict, draft_type=r[col['Черновик: тип']], final_type=final_type,
                        deep_cause=r[col['Глубинная причина (эксперт)']] or r[col['Черновик: глубинная причина']],
                        trigger=r[col['Повод (эксперт)']] or r[col['Черновик: повод']], material=material,
                        comment=r[col['Комментарий']]))
        out[-1].update(OVERRIDES.get(m, {}))
    return out


def main():
    eps = load_final()
    rows = build()
    add_approval(rows)
    add_material(rows)
    add_material2(rows)
    idx = {r['month']: i for i, r in enumerate(rows)}
    onsets = [idx[e['month']] for e in eps if e['month'] in idx]
    calm = [i for i in range(6, len(rows)) if all(abs(i - o) > 3 for o in onsets)]
    groups = {'с материальной причиной': [e for e in eps if e['material'] in ('да', 'вторым слоем')],
              'без материальной причины': [e for e in eps if e['material'] == 'нет']}
    table = []
    for label, c in FEATURES.items():
        x = np.array([r[c] for r in rows], dtype=float)
        ref = x[calm]
        ref = ref[~np.isnan(ref)]
        mu, sd = ref.mean(), ref.std() + 1e-9
        line = dict(feature=label)
        for g, members in groups.items():
            vals = []
            for e in members:
                i = idx.get(e['month'])
                seg = x[max(0, i - 3): i] if i else np.array([np.nan])
                if i and not np.all(np.isnan(seg)):
                    vals.append((np.nanmean(seg) - mu) / sd)
            line[g] = round(float(np.mean(vals)), 2) if vals else None
            line[g + ' n'] = len(vals)
        table.append(line)
    types = {}
    for e in eps:
        types[e['final_type']] = types.get(e['final_type'], 0) + 1
    agree = sum(e['final_type'] == e['draft_type'] for e in eps if e['verdict'])
    OUT.write_text(json.dumps(dict(episodes=eps, types=types, draft_type_agreement=f'{agree}/'
                                   f'{sum(1 for e in eps if e["verdict"])}', pre_conditions=table),
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print('final types:', types)
    print('draft type kept:', agree, 'of', sum(1 for e in eps if e['verdict']))
    print('material cause:', {g: [e['month'] for e in m] for g, m in groups.items()})
    print(f'\n{"pre-episode level, SD from calm norm":44} {"материальн.":>12} {"без":>8}')
    for t in sorted(table, key=lambda t: -abs((t['с материальной причиной'] or 0) - (t['без материальной причины'] or 0))):
        a, b = t['с материальной причиной'], t['без материальной причины']
        print(f"{t['feature']:44} {a if a is not None else '—':>12} {b if b is not None else '—':>8}")


if __name__ == '__main__':
    main()
