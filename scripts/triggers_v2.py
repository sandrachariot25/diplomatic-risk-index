"""Trigger calendar vs. background layers: what anticipates Korea-Japan flare-ups 1-3 months ahead?

    python scripts/triggers_v2.py     # -> data/dri_trigger_calendar.csv, data/dri_v2_triggers.json

Calendar (month level, 2015-2026). DRAFT compiled from public schedules by the model - dates must be checked
by the expert before publication (marked approximate where the month varies):
  recurring : Takeshima Day (Feb), March 1st (Mar), Japanese textbook screening results (Mar; Apr 2015),
              Diplomatic Bluebook (Apr; May 2018, May 2020), Yasukuni spring (Apr) and autumn (Oct)
              festivals, August 15 (Aug), Defense White Paper (Jul; Aug 2016-2018, Sep 2019),
              UNESCO World Heritage Committee (Jul; Sep 2023; none 2020, 2022), Sado memorial (Nov 2024, Sep 2025)
  elections : ROK legislative 2016-04, 2020-04, 2024-04; presidential 2017-05, 2022-03, 2025-06;
              local 2018-06, 2022-06, 2026-06; Japan upper house 2016-07, 2019-07, 2022-07, 2025-07;
              lower house 2017-10, 2021-10, 2024-10, 2026-02
  court     : Korean court rulings on wartime labour / comfort women from the court docket
              (data/court_rulings.csv, all outcomes; scripts/courts_v2.py). Dates are typically announced a few
              weeks ahead (horizon ~1 m).
Episodes: scripts/episodes_v2.py (GDELT, 14 onsets 2017-2026).
Comparison (target: an episode onset in t+1..t+3), rolling origin by year 2019-2026, L2 logistic:
  layers   - background layers (parliament, economy, rivalry, external), as in forecast_gdelt_v2;
  calendar - number of recurring / election triggers in t+1..t+3, court ruling in t+1;
  both     - layers + calendar (+ interaction court x parliament volume).
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.forecast_gdelt_v2 import build  # noqa: E402
from scripts.forecast_v2 import auc, fit_logistic, month_index  # noqa: E402

DATA = ROOT / 'data'
CAL = DATA / 'dri_trigger_calendar.csv'
OUT = DATA / 'dri_v2_triggers.json'
EPIS = DATA / 'dri_v2_episodes.json'
TRUTH = DATA / 'dri_event_truth.csv'
YEARS = range(2015, 2027)


def calendar():
    ev = []
    for y in YEARS:
        ev += [(f'{y}-02', 'recurring', 'День Такэсимы'), (f'{y}-03', 'recurring', '1 марта'),
               (f'{y}-04', 'recurring', 'Ясукуни, весенний фестиваль'), (f'{y}-08', 'recurring', '15 августа'),
               (f'{y}-10', 'recurring', 'Ясукуни, осенний фестиваль')]
        ev.append((f'{y}-04' if y == 2015 else f'{y}-03', 'recurring', 'Проверка японских учебников'))
        ev.append((f'{y}-05' if y in (2018, 2020) else f'{y}-04', 'recurring', '«Синяя книга» МИД Японии'))
        ev.append(({2016: f'{y}-08', 2017: f'{y}-08', 2018: f'{y}-08', 2019: f'{y}-09'}.get(y, f'{y}-07'),
                   'recurring', 'Белая книга по обороне Японии'))
        if y not in (2020, 2022):
            ev.append((f'{y}-09' if y == 2023 else f'{y}-07', 'recurring', 'Сессия Комитета всемирного наследия ЮНЕСКО'))
    ev += [('2024-11', 'recurring', 'Поминовение на Садо'), ('2025-09', 'recurring', 'Поминовение на Садо')]
    ev += [(m, 'election', n) for m, n in [
        ('2016-04', 'Выборы в парламент РК'), ('2020-04', 'Выборы в парламент РК'), ('2024-04', 'Выборы в парламент РК'),
        ('2017-05', 'Выборы президента РК'), ('2022-03', 'Выборы президента РК'), ('2025-06', 'Выборы президента РК'),
        ('2018-06', 'Местные выборы РК'), ('2022-06', 'Местные выборы РК'), ('2026-06', 'Местные выборы РК'),
        ('2016-07', 'Выборы в верхнюю палату Японии'), ('2019-07', 'Выборы в верхнюю палату Японии'),
        ('2022-07', 'Выборы в верхнюю палату Японии'), ('2025-07', 'Выборы в верхнюю палату Японии'),
        ('2017-10', 'Выборы в нижнюю палату Японии'), ('2021-10', 'Выборы в нижнюю палату Японии'),
        ('2024-10', 'Выборы в нижнюю палату Японии'), ('2026-02', 'Выборы в нижнюю палату Японии')]]
    # Court rulings from the court docket (data/court_rulings.csv), all outcomes, not only protested ones.
    decision_ru = {'plaintiff_win': 'победа истцов', 'enforcement': 'исполнение (арест/продажа активов)',
                   'procedural_win': 'процессуальное решение в пользу истцов', 'plaintiff_loss': 'отказ истцам',
                   'dismissed': 'иск отклонён'}
    for r in csv.DictReader((DATA / 'court_rulings.csv').open(encoding='utf-8')):
        ev.append((r['date'][:7], 'court', f"{r['court']}: {r['defendant']} — {decision_ru.get(r['decision'], r['decision'])}"))
    with CAL.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['month', 'kind', 'trigger', 'status'])
        for m, k, n in sorted(ev):
            w.writerow([m, k, n, 'court docket' if k == 'court' else 'draft: verify date'])
    return ev


def main():
    ev = calendar()
    by = {}
    for m, k, n in ev:
        by.setdefault(m, {}).setdefault(k, []).append(n)
    episodes = [e['month'] for e in json.loads(EPIS.read_text(encoding='utf-8'))['episodes']]
    rows = build()
    months = [r['month'] for r in rows]
    idx = {m: i for i, m in enumerate(months)}

    def near(m, kind, k=1):     # trigger in month m or the month before (onset month may lag the trigger)
        return any(kind in by.get(months[j], {}) for j in range(max(0, idx[m] - k), idx[m] + 1))

    hits = {}
    for kind in ('recurring', 'election', 'court'):
        on = sum(near(m, kind) for m in episodes)
        base = np.mean([near(m, kind) for m in months[6:]])
        hits[kind] = dict(episodes_with_trigger=on, of=len(episodes), share_all_months=round(float(base), 3))
    # Forecast comparison: target = onset in t+1..t+3
    onset = set(episodes)
    for i, r in enumerate(rows):
        fut = months[i + 1: i + 4]
        r['y'] = float(any(m in onset for m in fut)) if len(fut) == 3 else None
        r['c_recurring'] = sum(len(by.get(m, {}).get('recurring', [])) for m in fut)
        r['c_election'] = sum(len(by.get(m, {}).get('election', [])) for m in fut)
        r['c_court1'] = float(bool(by.get(months[i + 1], {}).get('court'))) if i + 1 < len(months) else 0.0
        r['c_court_x_parl'] = r['c_court1'] * r['kr_log_conf']
    layers = ['kr_log_conf', 'kr_r3', 'jp_log_conf', 'econ_balance_z12', 'riv_all', 'riv_chips_agg',
              'x_chn_hostile', 'x_prk_hostile', 'g_gap']
    cal = ['c_recurring', 'c_election', 'c_court1']
    sets = {'layers': layers, 'calendar': cal, 'calendar_no_court': ['c_recurring', 'c_election'],
            'both': layers + cal + ['c_court_x_parl']}
    lab = [r for r in rows if r['y'] is not None]
    preds, ys = {k: [] for k in sets}, []
    for Y in range(2019, 2027):
        tr = [r for r in lab if month_index(r['month']) < month_index(f'{Y}-01') - 3]
        te = [r for r in lab if int(r['month'][:4]) == Y]
        if not te:
            continue
        ys += [r['y'] for r in te]
        for k, cols in sets.items():
            X = np.array([[r[c] for c in cols] for r in tr])
            mu, sd = X.mean(0), X.std(0) + 1e-9
            w, b = fit_logistic((X - mu) / sd, np.array([r['y'] for r in tr]), lam=5.0)
            Xt = (np.array([[r[c] for c in cols] for r in te]) - mu) / sd
            preds[k] += list(1 / (1 + np.exp(-(Xt @ w + b))))
    y = np.array(ys)
    comp = {k: dict(auc=round(auc(y, np.array(p)), 3), brier=round(float(((np.array(p) - y) ** 2).mean()), 4))
            for k, p in preds.items()}
    comp['base_rate'] = dict(brier=round(float(((y.mean() - y) ** 2).mean()), 4))
    per_episode = [dict(month=m, triggers={k: v for k, v in {**by.get(months[idx[m] - 1], {}), **by.get(m, {})}.items()})
                   for m in episodes]
    OUT.write_text(json.dumps(dict(hit_rates=hits, comparison=comp, test_months=len(y), positives=int(y.sum()),
                                   per_episode=per_episode), ensure_ascii=False, indent=1), encoding='utf-8')
    print('trigger in onset month or month before (episodes vs share of all months):')
    for k, h in hits.items():
        print(f"  {k:10} {h['episodes_with_trigger']}/{h['of']}  vs  {h['share_all_months']:.0%} of all months")
    print(f'\nforecast of onset in t+1..t+3, test 2019-2026: {len(y)} months, {int(y.sum())} positive')
    for k, m in comp.items():
        print(f'  {k:18} {m}')
    print('\nper episode:')
    for e in per_episode:
        print(f"  {e['month']}: " + '; '.join(f"{k}: {', '.join(v)[:80]}" for k, v in e['triggers'].items()))


if __name__ == '__main__':
    main()
