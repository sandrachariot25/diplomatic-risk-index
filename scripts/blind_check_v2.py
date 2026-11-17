"""DRI v2.1 blind double annotation of a stratified subsample (docs/CODEBOOK_v2.md, "Экспертная проверка").

The pilot check showed the expert the model labels (anchoring). Here the expert labels units from scratch;
model labels are kept in a separate key file and compared only afterwards.

    python scripts/blind_check_v2.py sample      # draws 50 units -> data/dri_v2_blind_key.json + workbook
    python scripts/blind_check_v2.py book        # rebuilds the empty workbook, adding translations if present
    python scripts/blind_check_v2.py agreement   # reads the filled workbook, reports agreement

Translations (data/dri_v2_blind_translations.json, keyed by row №) are literal, made by the model without
labels or paraphrase; they are a weaker anchor than labels but must be mentioned when reporting agreement.

Strata are defined by the model labels (to get enough R2+ cases), so the agreement figures describe this
design, not a random draw from the corpus; per-stratum results are reported alongside the pooled ones.
Internal research material: the workbook contains source texts and must not be published.
"""
import argparse
from collections import Counter
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_v2 import load_done, load_queue  # noqa: E402
from scripts.pilot_v2 import DATA, FRAMES, kappa as _kappa  # noqa: E402


def kappa(pairs, weighted=False, k=7):
    """Cohen's kappa; None when chance agreement is 1 (e.g. both raters used one label only)."""
    try:
        return _kappa(pairs, weighted=weighted, k=k)
    except ZeroDivisionError:
        return None, sum(a == b for a, b in pairs) / len(pairs)

KEY = DATA / 'dri_v2_blind_key.json'
BOOK = DATA / 'dri_v2_blind_check.xlsx'
RESULT = DATA / 'dri_v2_blind_result.json'
TRANSLATIONS = DATA / 'dri_v2_blind_translations.json'
SEED = 'dri-v2.1-blind-2026-11-10'
MAX_CHARS = 3000  # keep the task readable; longer units are excluded and the share is reported
QUOTA = {  # stratum -> (kr, jp)
    'noise': (6, 4),     # model: mention / irrelevant
    'R0': (8, 5),        # model: relevant, rung 0
    'R1': (6, 4),
    'R2-R3': (6, 4),
    'R4-R6': (4, 3),
}
RELEVANCE = ['core', 'peripheral', 'mention', 'irrelevant']
PRESSURE = ['too_soft', 'too_hard', 'none']
COLS = ['№', 'Страна', 'Дата', 'Говорящий', 'Должность', 'Партия / статус', 'Уровень', 'Место', 'Текст',
        'Перевод (дословный)', 'Релевантность', 'Ступень R', 'Кооперация C', 'Ист. рамка', 'Давление на своё пр-во', 'Комментарий']


def stratum(r):
    if r['relevance'] not in {'core', 'peripheral'}:
        return 'noise'
    return {0: 'R0', 1: 'R1', 2: 'R2-R3', 3: 'R2-R3'}.get(r['rung'], 'R4-R6')


def cmd_sample(_):
    done = load_done()
    rng = random.Random(SEED)
    picked, excluded = [], Counter()
    for qi, name in enumerate(('kr', 'jp')):
        pool = {s: [] for s in QUOTA}
        for u in load_queue(name):
            r = done[u['unit_id']]
            if len(u['text']) > MAX_CHARS:
                excluded[name] += 1
                continue
            pool[stratum(r)].append((u, r))
        for s, quota in QUOTA.items():
            items = sorted(pool[s], key=lambda x: x[0]['unit_id'])
            assert len(items) >= quota[qi], (name, s, len(items))
            picked += [(s, u, r) for u, r in rng.sample(items, quota[qi])]
    rng.shuffle(picked)
    key = [dict(n=i + 1, unit_id=u['unit_id'], stratum=s, model={k: r[k] for k in (
        'relevance', 'rung', 'coop', 'history_frame', 'domestic_pressure')}) for i, (s, u, r) in enumerate(picked)]
    KEY.write_text(json.dumps(dict(seed=SEED, max_chars=MAX_CHARS, excluded_long=dict(excluded), units=key),
                              ensure_ascii=False, indent=1), encoding='utf-8')
    write_book([u for _, u, _ in picked], load_translations())
    print(f'sampled {len(key)} units -> {KEY.name}, {BOOK.name}; excluded as too long: {dict(excluded)}')
    print('by country x stratum:', dict(Counter((u['country'], s) for s, u, _ in picked)))


def load_translations():
    if not TRANSLATIONS.exists():
        return {}
    data = json.loads(TRANSLATIONS.read_text(encoding='utf-8'))
    return {int(k): v for k, v in data.items() if not k.startswith('_')}


def cmd_book(_):
    """Rebuild the workbook for the existing key (same units and order); refuses to overwrite filled rows."""
    if BOOK.exists():
        from openpyxl import load_workbook
        rows = list(load_workbook(BOOK, read_only=True)['Разметка'].iter_rows(values_only=True))
        start = rows[0].index('Релевантность')
        filled = sum(1 for r in rows[1:] if any(v not in (None, '') for v in r[start:]))
        assert not filled, f'{filled} rows already filled in {BOOK.name}; not overwriting'
    units = {u['unit_id']: u for name in ('kr', 'jp') for u in load_queue(name)}
    key = json.loads(KEY.read_text(encoding='utf-8'))['units']
    translations = load_translations()
    missing = [k['n'] for k in key if k['n'] not in translations]
    write_book([units[k['unit_id']] for k in key], translations)
    print(f'rebuilt {BOOK.name}: {len(key)} rows, translations for {len(key) - len(missing)}; missing {missing}')


def write_book(units, translations=None):
    translations = translations or {}
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    guide = wb.active
    guide.title = 'Инструкция'
    lines = [
        'Слепая проверка разметки DRI v2.1 — 50 единиц',
        '',
        'Разметьте каждую реплику сами, с нуля. Меток модели здесь нет — они хранятся отдельно и будут',
        'сравнены с вашими только после заполнения. Не сверяйтесь с прошлыми таблицами и отчётами.',
        '',
        'Рядом с оригиналом — дословный перевод на русский (сделан моделью, без оценок и пересказа;',
        'слова-маркеры даны в скобках в оригинале). При сомнении опирайтесь на оригинал.',
        '',
        'Заполните жёлтые столбцы на листе «Разметка»:',
        '  • Релевантность: core — отношения Кореи и Японии в центре; peripheral — затронуты по ходу;',
        '    mention — Япония/Корея лишь упомянута (сравнение, пример); irrelevant — не о том.',
        '  • Ступень R (только для core/peripheral; для mention/irrelevant ставьте R0):',
        '    R0 нет конфронтации · R1 обеспокоенность, критика · R2 протест, осуждение, «遺憾», «규탄» ·',
        '    R3 требование · R4 ультиматум, «немедленно» (直ちに, 即時, 즉각), жёсткое требование ·',
        '    R5 угроза конкретной меры (правовые меры, резолюции о дипломатических мерах, возражение в ЮНЕСКО) ·',
        '    R6 мера объявлена или действует (бойкот, отзыв, санкция).',
        '  • Кооперация C: C0 нет · C1 позитивная оценка, диалог · C2 конкретное предложение · C3 договорённость.',
        '  • Ист. рамка (можно несколько через запятую или пусто): ' + ', '.join(sorted(FRAMES)) + '.',
        '  • Давление на своё правительство: too_soft — «слишком мягко с соседом»,',
        '    too_hard — «слишком жёстко», none — нет.',
        '  • Комментарий — по желанию, особенно если сомневаетесь.',
        '',
        'Ступень — позиция самого говорящего. Если он пересказывает чужую позицию без своей оценки,',
        'ставьте ступень того, что пересказано, и отметьте это в комментарии.',
        'Можно заполнять частями. Пустые строки в расчёт не попадут.',
        'Полная инструкция: docs/CODEBOOK_v2.md.',
        '',
        'Внутренний исследовательский материал: тексты не публиковать.',
    ]
    for line in lines:
        guide.append([line])
    guide.column_dimensions['A'].width = 120
    guide['A1'].font = Font(bold=True, size=14)
    ws = wb.create_sheet('Разметка')
    ws.append(COLS)
    for i, u in enumerate(units, 1):
        ws.append([i, u['country'], u['date'], u['speaker'], u.get('speaker_pos'),
                   ' '.join(filter(None, [u.get('party'), u.get('gov_status')])), u['speaker_level'],
                   u.get('venue'), u['text'], translations.get(i), None, None, None, None, None, None])
    widths = [5, 7, 11, 12, 16, 18, 7, 18, 60, 70, 13, 9, 11, 22, 14, 40]
    for i, w in enumerate(widths):
        ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = w
    yellow = PatternFill('solid', fgColor='FFF2CC')
    for row in ws.iter_rows(min_row=1):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if cell.column >= 11:
                cell.fill = yellow
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = 'K2'
    n = ws.max_row
    for col, options in (('K', RELEVANCE), ('L', [f'R{i}' for i in range(7)]), ('M', [f'C{i}' for i in range(4)]),
                         ('O', PRESSURE)):
        dv = DataValidation(type='list', formula1='"' + ','.join(options) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f'{col}2:{col}{n}')
    wb.save(BOOK)


def parse_frames(value):
    if not value:
        return set()
    frames = {f.strip() for f in str(value).replace(';', ',').split(',') if f.strip()}
    unknown = frames - FRAMES
    assert not unknown, f'unknown frame(s) {unknown}'
    return frames


def cmd_agreement(_):
    from openpyxl import load_workbook
    key = {k['n']: k for k in json.loads(KEY.read_text(encoding='utf-8'))['units']}
    rows = list(load_workbook(BOOK, read_only=True)['Разметка'].iter_rows(values_only=True))
    head = rows[0]
    out = []
    for values in rows[1:]:
        row = dict(zip(head, values))
        if not row['Релевантность']:
            continue
        k = key[row['№']]
        rel = row['Релевантность']
        expert = dict(relevance=rel,
                      rung=int(str(row['Ступень R'] or 'R0')[1]) if rel in {'core', 'peripheral'} else 0,
                      coop=int(str(row['Кооперация C'] or 'C0')[1]) if rel in {'core', 'peripheral'} else 0,
                      history_frame=sorted(parse_frames(row['Ист. рамка'])),
                      domestic_pressure=row['Давление на своё пр-во'] or 'none')
        out.append(dict(n=k['n'], unit_id=k['unit_id'], stratum=k['stratum'], country=row['Страна'],
                        model=k['model'], expert=expert, comment=row['Комментарий']))
    if not out:
        print('no filled rows yet')
        return
    report = summarize(out)
    RESULT.write_text(json.dumps(dict(report=report, units=out), ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print('\nrung disagreements (both relevant):')
    for o in out:
        m, e = o['model'], o['expert']
        if both_relevant(o) and m['rung'] != e['rung']:
            print(f'  №{o["n"]:2} {o["unit_id"]:30} model R{m["rung"]} expert R{e["rung"]}  {o["comment"] or ""}')
    print('relevance disagreements (relevant vs not):')
    for o in out:
        if is_rel(o['model']) != is_rel(o['expert']):
            print(f'  №{o["n"]:2} {o["unit_id"]:30} model {o["model"]["relevance"]} expert {o["expert"]["relevance"]}')


def is_rel(lab):
    return lab['relevance'] in {'core', 'peripheral'}


def both_relevant(o):
    return is_rel(o['model']) and is_rel(o['expert'])


def nominal_kappa(pairs, labels):
    idx = {v: i for i, v in enumerate(labels)}
    return kappa([(idx[a], idx[b]) for a, b in pairs], k=len(labels))


def summarize(out):
    rep = dict(filled=len(out), by_country=dict(Counter(o['country'] for o in out)))
    pairs = [(o['model']['relevance'], o['expert']['relevance']) for o in out]
    rep['relevance_4class'] = fmt(nominal_kappa(pairs, RELEVANCE))
    rep['relevant_vs_not'] = fmt(nominal_kappa([(is_rel(o['model']), is_rel(o['expert'])) for o in out],
                                               [False, True]))
    rel = [o for o in out if both_relevant(o)]
    rep['both_relevant'] = len(rel)
    if rel:
        rp = [(o['model']['rung'], o['expert']['rung']) for o in rel]
        k, po = kappa(rp)
        kw, _ = kappa(rp, weighted=True)
        rep['rung'] = dict(exact=round(po, 3), kappa=rnd(k), weighted_kappa=rnd(kw),
                           expert_higher=sum(b > a for a, b in rp), expert_lower=sum(b < a for a, b in rp),
                           within_one=round(sum(abs(a - b) <= 1 for a, b in rp) / len(rp), 3))
        rep['rung_ge3'] = fmt(nominal_kappa([(a >= 3, b >= 3) for a, b in rp], [False, True]))
        rep['coop'] = fmt(kappa([(o['model']['coop'], o['expert']['coop']) for o in rel], k=4))
        rep['domestic_pressure'] = fmt(nominal_kappa(
            [(o['model']['domestic_pressure'], o['expert']['domestic_pressure']) for o in rel], PRESSURE))
        jac = [len(set(o['model']['history_frame']) & set(o['expert']['history_frame'])) /
               len(set(o['model']['history_frame']) | set(o['expert']['history_frame']))
               for o in rel if o['model']['history_frame'] or o['expert']['history_frame']]
        rep['history_frame_mean_jaccard'] = round(sum(jac) / len(jac), 3) if jac else None
        rep['rung_exact_by_stratum'] = {
            s: f'{sum(o["model"]["rung"] == o["expert"]["rung"] for o in g)}/{len(g)}'
            for s in QUOTA if (g := [o for o in rel if o['stratum'] == s])}
    return rep


def rnd(x):
    return None if x is None else round(x, 3)


def fmt(result):
    k, po = result
    return dict(exact=round(po, 3), kappa=rnd(k))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('sample')
    sub.add_parser('book')
    sub.add_parser('agreement')
    args = parser.parse_args()
    globals()['cmd_' + args.cmd](args)
