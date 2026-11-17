"""Event study: which layers are elevated in the months BEFORE Korea-Japan flare-ups?

    python scripts/episodes_v2.py           # -> data/dri_v2_episodes.json (+ printed table)

Episodes are defined only from GDELT (systematic target), not from the curated registry:
onset = first month whose conflict share exceeds its own trailing 12-month norm by >= ONSET_SD standard
deviations, at least MIN_GAP months after the previous onset. Registry actions in the onset month are
attached for interpretation only.
For each feature, the mean over the pre-window (months t-3..t-1, and t-6..t-4) is compared with the
distribution of the same window statistic in calm months (no onset within +/- CALM months):
"elevated" = above the calm 75th percentile. Under no relationship ~25% of episodes would be elevated.
Significance: permutation test - the same number of pseudo-onsets drawn at random from eligible months,
5 000 draws; p = share of draws with at least as many elevated episodes.
Features are the same as in scripts/forecast_gdelt_v2.py. `material_pressure` = mean of standardized
rivalry + dependence features (signed so that higher = more Korea gaining / more dependence).
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
OUT = DATA / 'dri_v2_episodes.json'
TRUTH = DATA / 'dri_event_truth.csv'
ONSET_SD, MIN_GAP, CALM, PERM = 1.0, 4, 3, 5000
FEATURES = {
    'Парламент РК: доля R3+': 'kr_r3', 'Парламент РК: объём жёстких реплик': 'kr_log_conf',
    'Парламент РК: «слишком мягко»': 'kr_too_soft', 'Парламент Японии: доля R3+': 'jp_r3',
    'Парламент Японии: объём жёстких реплик': 'jp_log_conf',
    'Зависимость от Японии (откл. от нормы)': 'econ_dep_total_z12',
    'Зависимость по крит. товарам (откл.)': 'econ_dep_crit_z12', 'Торговый баланс (откл.)': 'econ_balance_z12',
    'Соперничество на рынках (импульс)': 'riv_all', 'Япония теряет долю': 'riv_jp_loss',
    'Соперничество: чипы': 'riv_chips_agg', 'Соперничество: оборуд. для чипов': 'riv_chip_equipment_agg',
    'Соперничество: авто': 'riv_autos_agg', 'КНДР: враждебные действия': 'x_prk_hostile',
    'Китай: враждебные действия': 'x_chn_hostile', 'Материальное давление (сводное)': 'material_pressure',
    'Рейтинг президента РК: падение за 3 мес.': 'a_kr_fall3', 'Рейтинг президента РК: низкий уровень': 'a_kr_low',
    'Рейтинг кабинета Японии: падение за 3 мес.': 'a_jp_fall3', 'Рейтинг кабинета Японии: низкий уровень': 'a_jp_low',
    'Спад промышленности Японии (за год)': 'm2_jp_slow', 'Спад промышленности Японии (за 3 мес.)': 'm2_jp_slow3',
    'Корея растёт быстрее Японии (промпроизв.)': 'm2_ip_gap', 'Спад экспорта Японии': 'm2_jp_exports_drop',
    'Спад экспорта Японии в Корею': 'm2_jp_exports_kr_drop', 'Бум экспорта корейской памяти': 'm2_kr_memory_yoy',
    'Спад поставок японского оборуд. для чипов в Корею': 'm2_jp_equip_kr_drop',
    'Спад импорта морепродуктов Кореи из Японии': 'm2_kr_seafood_drop',
    'Спад импорта морепродуктов Китая из Японии': 'm2_cn_seafood_drop',
    'Спад экспорта морепродуктов Японии': 'm2_jp_seafood_drop',
}
APPROVAL = DATA / 'approval_monthly.csv'
MATERIAL2 = DATA / 'dri_v2_material2_monthly.csv'


def add_material2(rows):
    """Second material layer (scripts/features_material2_v2.py), signed so that higher = more material strain."""
    src = {r['month']: r for r in csv.DictReader(MATERIAL2.open(encoding='utf-8'))} if MATERIAL2.exists() else {}

    def v(m, k):
        x = src.get(m, {}).get(k, '')
        return float(x) if x not in ('', None) else np.nan
    for r in rows:
        m = r['month']
        r['m2_jp_slow'] = -v(m, 'm2_jp_ip_yoy')
        r['m2_jp_slow3'] = -v(m, 'm2_jp_ip_3m')
        r['m2_ip_gap'] = v(m, 'm2_ip_gap')
        r['m2_jp_exports_drop'] = -v(m, 'm2_jp_exports_yoy')
        r['m2_jp_exports_kr_drop'] = -v(m, 'm2_jp_exports_kr_yoy')
        r['m2_kr_memory_yoy'] = v(m, 'm2_kr_memory_yoy')
        r['m2_jp_equip_kr_drop'] = -v(m, 'm2_jp_equip_kr_yoy')
        r['m2_kr_seafood_drop'] = -v(m, 'm2_kr_seafood_jp_yoy')
        r['m2_cn_seafood_drop'] = -v(m, 'm2_cn_seafood_jp_yoy')
        r['m2_jp_seafood_drop'] = -v(m, 'm2_jp_seafood_exports_yoy')


def add_material(rows):
    """Composite material pressure: mean of standardized rivalry and dependence features."""
    for c in MATERIAL:
        x = np.array([r[c] for r in rows])
        z = (x - x.mean()) / (x.std() + 1e-9)
        for r, v in zip(rows, z):
            r.setdefault('_mp', []).append(v)
    for r in rows:
        r['material_pressure'] = float(np.mean(r.pop('_mp')))


def add_approval(rows):
    """Leader approval features (NaN where no series: acting presidents, Japan before 2017-10)."""
    src = {r['month']: r for r in csv.DictReader(APPROVAL.open(encoding='utf-8'))}

    def val(m, k):
        v = src.get(m, {}).get(k, '')
        return float(v) if v not in ('', None) else np.nan
    months = [r['month'] for r in rows]
    for i, r in enumerate(rows):
        for c, k in (('kr', 'kr_approval'), ('jp', 'jp_approval')):
            now = val(months[i], k)
            before = val(months[i - 3], k) if i >= 3 else np.nan
            r[f'a_{c}_level'] = now
            r[f'a_{c}_fall3'] = before - now          # > 0: approval fell over the last 3 months
            r[f'a_{c}_low'] = -now                    # higher = weaker leader
MATERIAL = ['riv_all', 'riv_jp_loss', 'riv_chips_agg', 'riv_chip_equipment_agg', 'econ_dep_total_z12',
            'econ_dep_crit_z12']


def main():
    rows = build()
    add_approval(rows)
    add_material(rows)
    add_material2(rows)
    months = [r['month'] for r in rows]
    gap = np.array([r['g_gap'] for r in rows])
    onsets, last = [], -99
    for i, gv in enumerate(gap):
        if gv >= ONSET_SD and i - last >= MIN_GAP and i >= 6:
            onsets.append(i)
        if gv >= ONSET_SD:
            last = i
    truth = list(csv.DictReader(TRUTH.open(encoding='utf-8-sig')))
    eligible = list(range(6, len(rows)))
    calm = [i for i in eligible if all(abs(i - o) > CALM for o in onsets)]
    rng = np.random.default_rng(20261112)
    report = []
    for label, col in FEATURES.items():
        x = np.array([r[col] for r in rows])
        res = dict(feature=label, column=col)
        for wname, (a, b) in {'1-3': (3, 1), '4-6': (6, 4)}.items():
            stat = np.array([np.nanmean(x[i - a: i - b + 1]) if i >= a and not np.all(np.isnan(x[i - a: i - b + 1]))
                             else np.nan for i in range(len(rows))])
            ok = [o for o in onsets if not np.isnan(stat[o])]          # episodes where the series exists
            calm_ok = [i for i in calm if not np.isnan(stat[i])]
            pool = [i for i in eligible if not np.isnan(stat[i])]
            thr = np.nanpercentile(stat[calm_ok], 75)
            obs = int(sum(stat[o] > thr for o in ok))
            draws = [sum(stat[j] > thr for j in rng.choice(pool, len(ok), replace=False)) for _ in range(PERM)]
            res[f'pre_{wname}'] = dict(elevated=obs, of=len(ok), p=round(float(np.mean(np.array(draws) >= obs)), 3),
                                       onset_mean=round(float(np.nanmean(stat[ok])), 3),
                                       calm_mean=round(float(np.nanmean(stat[calm_ok])), 3))
        report.append(res)
    episodes = []
    for o in onsets:
        m = months[o]
        acts = [t['description'] for t in truth if t['event_date'][:7] in (m, months[o - 1]) and t['direction'] == 'escalation']
        episodes.append(dict(month=m, conflict_share=round(rows[o]['g_level'], 3), gap_sd=round(float(gap[o]), 2),
                             registry_escalations=acts))
    OUT.write_text(json.dumps(dict(rule=f'onset gap >= {ONSET_SD} SD over 12m norm, >= {MIN_GAP} months apart',
                                   episodes=episodes, calm_months=len(calm), features=report),
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'episodes ({len(onsets)}):')
    for e in episodes:
        print(f"  {e['month']}  share {e['conflict_share']}  +{e['gap_sd']} SD  registry: {len(e['registry_escalations'])}"
              + (f" — {e['registry_escalations'][0][:70]}" if e['registry_escalations'] else ''))
    print(f'calm months: {len(calm)}; "elevated" = above calm 75th percentile (chance ~25%)')
    print(f'{"":42} {"за 1-3 мес.":>18} {"за 4-6 мес.":>18}')
    for r in report:
        a, b = r['pre_1-3'], r['pre_4-6']
        print(f"{r['feature']:42} {a['elevated']:2}/{a['of']} p={a['p']:<5}    {b['elevated']:2}/{b['of']} p={b['p']:<5}")


if __name__ == '__main__':
    main()
