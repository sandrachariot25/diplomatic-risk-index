"""DRI v2 forecast: does parliamentary rhetoric in month t predict bilateral escalation in t+1..t+3?

    python scripts/forecast_v2.py        # -> data/dri_v2_forecast.json (+ printed backtest)

Target: esc_next from data/dri_v2_monthly.csv (verified registry actions in the next 3 months).
Validation: rolling origin by year - for each test year Y (2018..), the model is fitted only on months
whose 3-month target window closes before Y starts, then scored on Y. Models: L2 logistic regression
(numpy, standardized features) with (a) registry history only, (b) parliament features only, (c) both.
Baseline: training base rate. Metrics: ROC AUC, Brier score. Small sample (~140 months): read the
numbers as indicative, not as a validated accuracy.
"""
import csv
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MONTHLY = DATA / 'dri_v2_monthly.csv'
OUT = DATA / 'dri_v2_forecast.json'
LAMBDA = 1.0

PARL = ['kr_log_pool', 'kr_r3', 'kr_log_conf', 'kr_urgency', 'kr_too_soft', 'kr_coop2',
        'jp_log_pool', 'jp_r3', 'jp_log_conf', 'jp_urgency', 'jp_coop2', 'jp_too_soft']
HIST = ['esc_past3', 'coop_past3']
SETS = {'history': HIST, 'parliament': PARL, 'parliament+history': PARL + HIST}


def load():
    rows = list(csv.DictReader(MONTHLY.open(encoding='utf-8')))
    num = lambda v: float(v) if v not in ('', None) else 0.0
    for i, r in enumerate(rows):
        for c in ('kr', 'jp'):
            r[f'{c}_log_pool'] = math.log1p(num(r[f'{c}_pool']))
            r[f'{c}_log_conf'] = math.log1p(num(r[f'{c}_conf_volume']))
        past = rows[max(0, i - 2): i + 1]
        r['esc_past3'] = float(any(num(p['esc_now']) for p in past))
        r['coop_past3'] = float(any(num(p['coop_now']) for p in past))
        for k in PARL:
            r[k] = num(r[k]) if not isinstance(r[k], float) else r[k]
    return rows


def fit_logistic(X, y, lam=LAMBDA, iters=500):
    w, b = np.zeros(X.shape[1]), math.log((y.mean() + 1e-3) / (1 - y.mean() + 1e-3))
    for _ in range(iters):              # Newton steps on the L2-penalized log-likelihood
        p = 1 / (1 + np.exp(-(X @ w + b)))
        g_w, g_b = X.T @ (p - y) + lam * w, (p - y).sum()
        s = p * (1 - p)
        H = np.block([[X.T @ (X * s[:, None]) + lam * np.eye(X.shape[1]), (X * s[:, None]).sum(0)[:, None]],
                      [(X * s[:, None]).sum(0)[None, :], np.array([[s.sum() + 1e-9]])]])
        step = np.linalg.solve(H, np.concatenate([g_w, [g_b]]))
        w, b = w - step[:-1], b - step[-1]
        if np.abs(step).max() < 1e-8:
            break
    return w, b


def auc(y, p):
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def month_index(m):
    y, mm = map(int, m.split('-'))
    return y * 12 + mm


def backtest(rows):
    labeled = [r for r in rows if r['esc_next'] != '']
    years = sorted({int(r['month'][:4]) for r in labeled if int(r['month'][:4]) >= 2018})
    preds = {name: [] for name in SETS}
    preds['base_rate'] = []
    ys = []
    for Y in years:
        cutoff = month_index(f'{Y}-01') - 3            # target window of training months must close before Y
        train = [r for r in labeled if month_index(r['month']) < cutoff]
        test = [r for r in labeled if int(r['month'][:4]) == Y]
        y_tr = np.array([float(r['esc_next']) for r in train])
        ys += [float(r['esc_next']) for r in test]
        preds['base_rate'] += [y_tr.mean()] * len(test)
        for name, cols in SETS.items():
            X_tr = np.array([[r[c] for c in cols] for r in train])
            mu, sd = X_tr.mean(0), X_tr.std(0) + 1e-9
            w, b = fit_logistic((X_tr - mu) / sd, y_tr)
            X_te = (np.array([[r[c] for c in cols] for r in test]) - mu) / sd
            preds[name] += list(1 / (1 + np.exp(-(X_te @ w + b))))
    y = np.array(ys)
    report = {}
    for name, p in preds.items():
        p = np.array(p)
        report[name] = dict(auc=None if auc(y, p) is None else round(auc(y, p), 3),
                            brier=round(float(((p - y) ** 2).mean()), 4))
    return report, len(y), int(y.sum()), years


def final_model(rows):
    labeled = [r for r in rows if r['esc_next'] != '']
    cols = SETS['parliament+history']
    X = np.array([[r[c] for c in cols] for r in labeled])
    y = np.array([float(r['esc_next']) for r in labeled])
    mu, sd = X.mean(0), X.std(0) + 1e-9
    w, b = fit_logistic((X - mu) / sd, y)
    latest = []
    for r in rows[-6:]:
        x = (np.array([r[c] for c in cols]) - mu) / sd
        contrib = sorted(zip(cols, (x * w).round(3)), key=lambda t: -abs(t[1]))[:4]
        latest.append(dict(month=r['month'], p_escalation_next_3m=round(float(1 / (1 + np.exp(-(x @ w + b)))), 3),
                           top_drivers=[dict(feature=c, contribution=float(v)) for c, v in contrib]))
    coefs = dict(sorted(zip(cols, w.round(3).tolist()), key=lambda t: -abs(t[1])))
    return coefs, latest, float(y.mean())


def main():
    rows = load()
    report, n, pos, years = backtest(rows)
    coefs, latest, base = final_model(rows)
    OUT.write_text(json.dumps(dict(target='escalation action in t+1..t+3 (verified registry)', test_years=years,
                                   test_months=n, test_positive=pos, backtest=report, coefficients=coefs,
                                   base_rate=round(base, 3), latest=latest), ensure_ascii=False, indent=1),
                   encoding='utf-8')
    print(f'rolling backtest {years[0]}-{years[-1]}: {n} months, {pos} positive')
    for name, m in report.items():
        print(f'  {name:20} AUC {m["auc"]}  Brier {m["brier"]}')
    print('coefficients (standardized):', coefs)
    for r in latest:
        print(' ', r['month'], r['p_escalation_next_3m'], r['top_drivers'][:2])


if __name__ == '__main__':
    main()
