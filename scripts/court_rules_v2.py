"""Finer court-based risk rules: which kind of upcoming ruling actually signals a flare-up within 3 months?

    python scripts/court_rules_v2.py      # -> data/dri_v2_court_rules.json (+ printed table)

Unit: month t (2016-01 .. last month whose t+1..t+3 is observed). Outcome: a flare-up episode (14 GDELT episodes,
data/dri_v2_episode_causes_final.json) starting in t+1..t+3. A rule flags t if the court docket
(data/court_rulings.csv) has a ruling of the given kind in the given window. Reported per rule: flagged months,
share followed by a flare-up, lift over the base rate, episodes warned, one-sided Fisher exact p (flagged vs not).
With 14 episodes and correlated neighbouring months, p-values are indicative only; rules are compared, not tuned:
all candidates are listed here before looking at results and every one is reported.
"""
import csv
import json
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_court_rules.json'
FAVOURABLE = {'plaintiff_win', 'enforcement', 'procedural_win'}


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def fisher_greater(a, b, c, d):
    """P(X >= a) for the 2x2 table [[a, b], [c, d]] with fixed margins (hypergeometric)."""
    n1, k, n = a + b, a + c, a + b + c + d
    tot = comb(n, k)
    return sum(comb(n1, x) * comb(n - n1, k - x) for x in range(a, min(n1, k) + 1)) / tot


def main():
    rulings = list(csv.DictReader((DATA / 'court_rulings.csv').open(encoding='utf-8')))
    for r in rulings:
        r['m'] = r['date'][:7]
    eps = sorted(e['month'] for e in json.loads((DATA / 'dri_v2_episode_causes_final.json')
                                                 .read_text(encoding='utf-8'))['episodes'])
    last = month_add(eps[-1], -1)
    months, m = [], '2016-01'
    while m <= last:
        months.append(m)
        m = month_add(m, 1)
    flare = {m: [e for e in eps if e in {month_add(m, k) for k in (1, 2, 3)}] for m in months}

    def court(m, window, pred):
        ahead = {month_add(m, k) for k in window}
        return any(r['m'] in ahead and pred(r) for r in rulings)

    rules = {
        'A. любое решение суда, 1–3 мес. (текущее правило)': lambda m: court(m, (1, 2, 3), lambda r: True),
        'B. любое решение в следующем месяце': lambda m: court(m, (1,), lambda r: True),
        'C. любое решение через 2–3 мес.': lambda m: court(m, (2, 3), lambda r: True) and not court(m, (1,), lambda r: True),
        'D. Верховный суд, 1–3 мес.': lambda m: court(m, (1, 2, 3), lambda r: r['level'] == 'supreme'),
        'E. решение в пользу истцов (победа, исполнение), 1–3 мес.': lambda m: court(m, (1, 2, 3), lambda r: r['decision'] in FAVOURABLE),
        'F. только отказы истцам / отклонения, 1–3 мес.': lambda m: court(m, (1, 2, 3), lambda r: True) and not court(m, (1, 2, 3), lambda r: r['decision'] in FAVOURABLE),
        'G. в пользу истцов в следующем месяце': lambda m: court(m, (1,), lambda r: r['decision'] in FAVOURABLE),
        'H. Верховный суд или иск к правительству Японии, 1–3 мес.': lambda m: court(m, (1, 2, 3), lambda r: r['level'] == 'supreme' or r['case_type'] == 'comfort_women' and r['decision'] in FAVOURABLE),
        'I. исполнение (арест / продажа активов), 1–3 мес.': lambda m: court(m, (1, 2, 3), lambda r: r['decision'] == 'enforcement'),
        'J. два и более решения в окне 1–3 мес.': lambda m: sum(r['m'] in {month_add(m, k) for k in (1, 2, 3)} for r in rulings) >= 2,
        'K. первое решение после паузы ≥ 6 мес.': lambda m: any(r['m'] in {month_add(m, k) for k in (1, 2, 3)} and not any(
            q['m'] < r['m'] and q['m'] >= month_add(r['m'], -6) for q in rulings) for r in rulings),
    }
    n, pos = len(months), sum(bool(flare[m]) for m in months)
    base = pos / n
    table = []
    for name, rule in rules.items():
        flagged = [m for m in months if rule(m)]
        a = sum(bool(flare[m]) for m in flagged)
        b, c = len(flagged) - a, pos - a
        d = n - len(flagged) - c
        warned = sorted({e for m in flagged for e in flare[m]})
        rest = (pos - a) / (n - len(flagged)) if n > len(flagged) else None
        table.append(dict(rule=name, months=len(flagged), with_flareup=a,
                          share=round(a / len(flagged), 3) if flagged else None,
                          share_other_months=round(rest, 3) if rest is not None else None,
                          lift=round(a / len(flagged) / base, 2) if flagged else None,
                          episodes_warned=len(warned), p_fisher=round(fisher_greater(a, b, c, d), 3) if flagged else None,
                          flagged_last_24=sum(m in flagged for m in months[-24:])))
    OUT.write_text(json.dumps(dict(months=n, base_rate=round(base, 3), episodes=len(eps), rules=table),
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{n} months, base rate {base:.0%}, {len(eps)} episodes')
    print(f"{'rule':62} {'мес':>4} {'доля':>5} {'ост.':>5} {'lift':>5} {'эпиз':>4} {'p':>6} {'посл24':>6}")
    for t in table:
        print(f"{t['rule'][:62]:62} {t['months']:>4} {t['share'] if t['share'] is not None else '-':>5} "
              f"{t['share_other_months']:>5} {t['lift'] if t['lift'] else '-':>5} {t['episodes_warned']:>4} "
              f"{t['p_fisher'] if t['p_fisher'] is not None else '-':>6} {t['flagged_last_24']:>6}")


if __name__ == '__main__':
    main()
