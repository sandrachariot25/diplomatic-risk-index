"""DRI v2 monitor data: one record per month for the Streamlit "Монитор DRI v2" screen.

    python scripts/monitor_v2.py       # -> data/dri_v2_monitor.json (internal: contains summaries of internal texts)

Per month t:
  index (0-100)   percentile of the composite tension score in 2016-2026 history; the composite is the mean of
                  standardized layers (signed so that higher = tenser), each shown with its contribution;
  triggers_ahead  calendar triggers in t+1..t+3 (data/dri_trigger_calendar.csv; court rulings from the registry -
                  in live use they come from the court docket, typically known weeks ahead);
  risk            by triggers ahead (the only layer with a signal in the 2016-2026 tests; the index itself did not
                  anticipate flare-ups): "повышен" - a Korean court ruling in t+1..t+3; "внимание" - a heritage date
                  (UNESCO session, Sado memorial); otherwise "обычный". Court rulings come from the court docket
                  (data/court_rulings.csv, all outcomes); cases still pending (data/court_pipeline.csv) are added
                  to the latest month;
  outcome         flare-ups in t+1..t+3 with the expert cause type (for past dates);
  evidence        the most confrontational annotated parliamentary turns of t-2..t and registry actions of t-2..t.
The rule's historical hit rate is stored in `rule_check` and shown on screen. Not a probability forecast.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_v2 import load_done, load_units  # noqa: E402
from scripts.episodes_v2 import add_approval, add_material, add_material2  # noqa: E402
from scripts.forecast_gdelt_v2 import build  # noqa: E402

DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_monitor.json'
HIGH, VERY_HIGH = 70, 90
LAYERS = {  # column -> (label, group)
    'g_gap': ('Конфликтность в новостях (GDELT, откл. от нормы)', 'Новости'),
    'kr_r3': ('Жёсткие реплики, парламент РК', 'Парламент'),
    'kr_log_conf': ('Объём жёсткой риторики, парламент РК', 'Парламент'),
    'jp_r3': ('Жёсткие реплики, парламент Японии', 'Парламент'),
    'kr_too_soft': ('Давление «слишком мягко», парламент РК', 'Парламент'),
    'econ_balance_z12': ('Торговый баланс (откл. от нормы)', 'Экономика'),
    'riv_chips_agg': ('Соперничество: чипы', 'Экономика'),
    'm2_kr_memory_yoy': ('Цикл корейской памяти', 'Экономика'),
    'x_chn_hostile': ('Враждебность Китая', 'Внешний фон'),
    'x_prk_hostile': ('Враждебность КНДР', 'Внешний фон'),
}
SHARP = ('court', 'heritage')


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def main():
    rows = build()
    add_approval(rows)
    add_material(rows)
    add_material2(rows)
    months = [r['month'] for r in rows]
    Z = {}
    for c in LAYERS:
        x = np.array([r[c] for r in rows], dtype=float)
        mu, sd = np.nanmean(x), np.nanstd(x) + 1e-9
        Z[c] = (x - mu) / sd
    comp = np.nanmean(np.vstack([Z[c] for c in LAYERS]), axis=0)
    pct = np.array([100 * np.mean(comp <= v) for v in comp])
    cal = list(csv.DictReader((DATA / 'dri_trigger_calendar.csv').open(encoding='utf-8')))
    for c in cal:
        if 'ЮНЕСКО' in c['trigger'] or 'Садо' in c['trigger']:
            c['kind'] = 'heritage'
    final = json.loads((DATA / 'dri_v2_episode_causes_final.json').read_text(encoding='utf-8'))['episodes']
    ep = {e['month']: e for e in final}
    truth = list(csv.DictReader((DATA / 'dri_event_truth.csv').open(encoding='utf-8-sig')))
    units, done = load_units(), load_done()
    by_month = {}
    for u, r in done.items():
        if r['relevance'] == 'core' and r['rung'] >= 2:
            by_month.setdefault(units[u]['date'][:7], []).append((u, r))
    out = []
    for i, m in enumerate(months):
        ahead = [month_add(m, k) for k in (1, 2, 3)]
        trig = [dict(month=c['month'], kind=c['kind'], trigger=c['trigger']) for c in cal if c['month'] in ahead]
        kinds = {t['kind'] for t in trig}
        courts = [t['trigger'] for t in trig if t['kind'] == 'court']
        supreme = any(c.startswith('Верховный суд') for c in courts)
        favourable = any(not ('отказ' in c or 'отклонён' in c) for c in courts)
        # Rule v2 (13.11.2026, scripts/court_rules_v2.py): Supreme Court ahead -> 73% of months followed by a
        # flare-up (base 33%); other rulings for plaintiffs / heritage dates ~ base; plaintiff losses 0 of 8.
        risk = 'повышен' if supreme else 'внимание' if favourable or 'heritage' in kinds else 'обычный'
        win = {month_add(m, -k) for k in (0, 1, 2)}
        turns = sorted((x for mm in win for x in by_month.get(mm, [])), key=lambda x: (-x[1]['rung'], units[x[0]]['date']))
        out.append(dict(
            month=m, index=round(float(pct[i]), 1), composite=round(float(comp[i]), 3), risk=risk,
            gdelt_conflict_share=round(rows[i]['g_level'], 3),
            layers=[dict(column=c, label=l, group=g, z=None if np.isnan(Z[c][i]) else round(float(Z[c][i]), 2))
                    for c, (l, g) in LAYERS.items()],
            triggers_ahead=trig,
            outcome=[dict(month=a, type=ep[a]['final_type'], trigger=ep[a]['trigger'], deep_cause=ep[a]['deep_cause'])
                     for a in ahead if a in ep],
            evidence_turns=[dict(date=units[u]['date'], country='РК' if u.startswith('kr') else 'Япония',
                                 speaker=units[u].get('speaker'), level=units[u].get('speaker_level'),
                                 rung=r['rung'], summary=r['reason_ru'], url=units[u].get('source_url'))
                            for u, r in turns[:8]],
            evidence_actions=[dict(date=t['event_date'], direction=t['direction'], description=t['description'],
                                   url=t['primary_source']) for t in truth if t['event_date'][:7] in win],
        ))
    # Historical check of the rule: months whose next 3 months contain a flare-up.
    lab = [r for r in out if r['month'] <= month_add(max(ep), -1)]
    pos = [r for r in lab if r['outcome']]
    check = dict(months=len(lab), base_rate=round(len(pos) / len(lab), 3), episodes=len(ep))
    for level in ('повышен', 'внимание', 'обычный'):
        flagged = [r for r in lab if r['risk'] == level]
        hits = [r for r in flagged if r['outcome']]
        check[level] = dict(months=len(flagged), with_flareup_ahead=len(hits),
                            share=round(len(hits) / len(flagged), 3) if flagged else None,
                            episodes_warned=len({o['month'] for r in hits for o in r['outcome']}))
    check['index_ge_70_share'] = round(sum(bool(r['outcome']) for r in lab if r['index'] >= 70) /
                                       max(1, sum(r['index'] >= 70 for r in lab)), 3)
    pipeline = list(csv.DictReader((DATA / 'court_pipeline.csv').open(encoding='utf-8')))
    courts = json.loads((DATA / 'dri_v2_courts.json').read_text(encoding='utf-8'))
    OUT.write_text(json.dumps(dict(rule='повышен — решение Верховного суда РК в ближайшие 3 мес.; внимание — другое решение '
                                        'в пользу истцов или дата наследия; иначе обычный',
                                   rule_check=check, court_check=dict(groups=courts['groups'],
                                                                      base=courts['base_share_any_month']),
                                   pipeline=pipeline, months=out), ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{OUT.name}: {len(out)} months; rule check {check}')


if __name__ == '__main__':
    main()
