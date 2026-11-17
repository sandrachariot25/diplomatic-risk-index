"""DRI v2 pilot: stratified sample, annotation storage/validation and expert review workbook.

    python scripts/pilot_v2.py sample            # builds data/dri_v2_pilot_units.jsonl (offline, deterministic)
    python scripts/pilot_v2.py read --start 0 --count 40
    python scripts/pilot_v2.py save batch.json    # validates and appends annotations
    python scripts/pilot_v2.py review            # builds data/dri_v2_pilot_review.xlsx
    python scripts/pilot_v2.py summary
Codebook: docs/CODEBOOK_v2.md.
"""
import argparse
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DB = DATA / 'dri.sqlite3'
UNITS = DATA / 'dri_v2_pilot_units.jsonl'
ANNOTATIONS = DATA / 'dri_v2_pilot_annotations.jsonl'
REVIEW = DATA / 'dri_v2_pilot_review.xlsx'
VERSION = 'DRI-v2.1'  # rows saved before 2026-11-10 keep 'DRI-v2-pilot'
SEED = 'dri-v2-pilot-2026-11-09'

# Escalation episode starts (dri_bilateral episode registry) and key cooperation turning points.
ESCALATIONS = ['2015-05-21', '2016-03-15', '2016-08-15', '2017-01-06', '2018-06-18', '2018-10-30',
               '2018-11-06', '2018-12-20', '2019-07-01', '2019-08-25', '2020-03-06', '2021-01-08',
               '2022-05-28', '2023-12-21', '2024-06-06', '2024-11-23']
SADO = (date(2024, 6, 1), date(2026, 10, 31))
RAPPROCHEMENT = (date(2023, 1, 1), date(2023, 6, 30))
KR_QUOTA = {'pre_crisis': 50, 'post_crisis': 25, 'sado': 30, 'rapprochement': 15, 'background': 20}
JP_QUOTA = {'pre_crisis': 12, 'post_crisis': 6, 'sado': 8, 'rapprochement': 6, 'background': 8}
ROK_MOFA_QUOTA = {'pre_crisis': 7, 'post_crisis': 3, 'sado': 4, 'rapprochement': 3, 'background': 3}

KR_KEYS = ['일본', '日本', '일측', '아베', '스가', '기시다', '이시바', '다카이치', '독도', '위안부', '강제징용',
           '강제동원', '사도', '후쿠시마', '오염수', '처리수', '지소미아', 'GSOMIA', '수출규제', '화이트리스트',
           '한일', '한·일', '한미일', '한·미·일', '일제', '식민']

ENUMS = dict(
    relevance={'core', 'peripheral', 'mention', 'irrelevant'},
    criticism_target={'other_country', 'own_government', 'both', 'none'},
    domestic_pressure={'too_soft', 'too_hard', 'none'},
    ownership={'own', 'reported', 'quoted', 'mixed'},
    confidence={'high', 'medium', 'low'},
)
FRAMES = {'sado', 'forced_labor', 'comfort_women', 'dokdo_takeshima', 'textbooks', 'yasukuni',
          'colonial_general', 'other_history'}
MATERIAL = {'trade_balance', 'export_controls', 'critical_materials', 'fisheries_maritime', 'fukushima_seafood',
            'defense_security', 'corporate_assets', 'people_tourism', 'other_material'}
# Compact batch row order used by `save`.
FIELDS = ['unit_id', 'relevance', 'rung', 'coop', 'history_frame', 'material_issue', 'frame_link',
          'criticism_target', 'domestic_pressure', 'dprk_reference', 'ownership', 'confidence',
          'reason_ru', 'summary_ru']


def stratum(day):
    for start in map(date.fromisoformat, ESCALATIONS):
        if start - timedelta(days=180) <= day < start:
            return 'pre_crisis'
    for start in map(date.fromisoformat, ESCALATIONS):
        if start <= day <= start + timedelta(days=60):
            return 'post_crisis'
    if SADO[0] <= day <= SADO[1]:
        return 'sado'
    if RAPPROCHEMENT[0] <= day <= RAPPROCHEMENT[1]:
        return 'rapprochement'
    return 'background'


def kr_ruling(day):
    if day < date(2017, 5, 10):
        return {'새누리당', '자유한국당'}
    if day < date(2022, 5, 10):
        return {'더불어민주당'}
    if day < date(2025, 6, 4):
        return {'국민의힘'}
    return {'더불어민주당'}


def kr_level(row, day):
    pos = row['speaker_pos'] or ''
    if row['role_group'] == 'legislator':
        party = row['party']
        status = None if not party or row.get('party_uncertain') else ('ruling' if party in kr_ruling(day) else 'opposition')
        return 'L2', status
    if '대통령' in pos and '비서' not in pos:
        return 'L5', None
    if (pos.endswith('장관') and '차관' not in pos or '국무총리' in pos or '대변인' in pos
            or '비서실장' in pos or '안보실장' in pos or '장관후보자' in pos or '총리후보자' in pos):
        return 'L4', None
    if any(k in pos for k in ('차관', '청장', '처장', '실장', '국장', '본부장', '차장', '위원장', '원장', '대사',
                              '총영사', '관장')) or pos.endswith('관'):
        return 'L3', None
    return 'L1', None


def jp_level(office, text):
    # Only the speaker header (○…君) of a transcript is a role marker; other text may name a minister.
    header = text.split('）', 1)[0] if (text or '').startswith('○') else ''
    probe = (office or '') + ' ' + header
    if '内閣総理大臣' in probe:
        return 'L5'
    if ('大臣' in probe and '副大臣' not in probe and '政務官' not in probe) or '官房長官' in probe or '報道官' in probe:
        return 'L4'
    if any(k in probe for k in ('副大臣', '政務官', '政府参考人', '局長', '審議官')):
        return 'L3'
    if '参考人' in probe or '知事' in probe:
        return 'L1'
    return 'L2'


def excerpt(text, limit=1000):
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= limit:
        return text, False
    sentences = re.split(r'(?<=[.?!다요])\s+', text)
    hits = [i for i, s in enumerate(sentences) if any(k in s for k in KR_KEYS)]
    keep = sorted({j for i in hits for j in (i - 1, i, i + 1) if 0 <= j < len(sentences)})
    out, last, size = [], None, 0
    for j in keep:
        piece = sentences[j]
        if size + len(piece) > limit:
            break
        if last is not None and j != last + 1:
            out.append('…')
        out.append(piece)
        size += len(piece)
        last = j
    return ' '.join(out) or text[:limit], True


def density(text):
    return sum(text.count(k) for k in KR_KEYS)


def sample_kr(rng):
    pools = {k: [] for k in KR_QUOTA}
    for term in ('t19', 't20', 't21', 't22'):
        with (DATA / f'kr_hearings_candidates_{term}.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['role_group'] == 'excluded' or not row['speech_date']:
                    continue
                d = density(row['text'])
                if d == 0 or len(row['text']) < 80:
                    continue
                day = date.fromisoformat(str(row['speech_date'])[:10])
                pools[stratum(day)].append((d, day, row))
    units = []
    for name, quota in KR_QUOTA.items():
        dense = [p for p in pools[name] if p[0] >= 3]
        sparse = [p for p in pools[name] if p[0] < 3]
        n_dense = round(quota * 0.8)
        picked = rng.sample(dense, min(n_dense, len(dense)))
        picked += rng.sample(sparse, min(quota - len(picked), len(sparse)))
        for d, day, row in picked:
            level, status = kr_level(row, day)
            text, cut = excerpt(row['text'])
            units.append(dict(
                unit_id=f'kr:{row["conf_num"]}:{row["turn_seq"]}', source='assembly_kr', country='ROK', language='ko',
                date=day.isoformat(), stratum=name, speaker=row['speaker_name'], speaker_pos=row['speaker_pos'],
                party=row['party'], gov_status=status, speaker_level=level, japan_density=d,
                text=text, excerpted=cut, text_sha256=hashlib.sha256(row['text'].encode()).hexdigest(),
                source_url=f'https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={row["conf_num"]}&type=view'))
    return units


def sample_corpus(rng):
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('''
            SELECT s.id, s.country, COALESCE(s.spoken_date, s.published_date, d.published_date), s.speaker_name, s.speaker_office, s.institution, q.text,
                   d.source, d.url, m.institution_type, m.political_affiliation, m.government_opposition_status
            FROM statements s JOIN quotes q ON q.statement_id = s.id
            JOIN statement_sources ss ON ss.statement_id = s.id JOIN documents d ON d.id = ss.document_id
            LEFT JOIN statement_metadata m ON m.statement_id = s.id
            WHERE COALESCE(s.spoken_date, s.published_date, d.published_date) IS NOT NULL AND d.source IN ('kokkai_jp', 'mofa_kr')
            GROUP BY s.id''').fetchall()
    units = []
    for source, quota in (('kokkai_jp', JP_QUOTA), ('mofa_kr', ROK_MOFA_QUOTA)):
        pools = {k: [] for k in quota}
        for row in rows:
            if row[7] == source:
                pools[stratum(date.fromisoformat(row[2]))].append(row)
        for name, n in quota.items():
            for row in rng.sample(pools[name], min(n, len(pools[name]))):
                (sid, country, spoken, speaker, office, institution, text, src, url, itype, party, status) = row
                level = jp_level(office, text) if src == 'kokkai_jp' else 'L4'
                clean, cut = excerpt(text, 1500)
                units.append(dict(
                    unit_id=f'stmt:{sid}', source=src, country=country, language='ja' if src == 'kokkai_jp' else 'en',
                    date=spoken, stratum=name, speaker=speaker, speaker_pos=office, party=party,
                    gov_status=status, speaker_level=level, japan_density=None, text=clean, excerpted=cut,
                    text_sha256=hashlib.sha256(text.encode()).hexdigest(), source_url=url))
    return units


def cmd_sample(_):
    rng = random.Random(SEED)
    units = sample_kr(rng) + sample_corpus(rng)
    units.sort(key=lambda u: (u['date'], u['unit_id']))
    for i, unit in enumerate(units):
        unit['pilot_index'] = i
    UNITS.write_text(''.join(json.dumps(u, ensure_ascii=False) + '\n' for u in units), encoding='utf-8')
    print(len(units), Counter((u['source'], u['stratum']) for u in units))
    print(Counter(u['speaker_level'] for u in units))


def load_units():
    return {u['unit_id']: u for u in map(json.loads, UNITS.read_text(encoding='utf-8').splitlines())}


def load_annotations():
    if not ANNOTATIONS.exists():
        return {}
    return {r['unit_id']: r for r in map(json.loads, ANNOTATIONS.read_text(encoding='utf-8').splitlines())}


def cmd_read(args):
    units = sorted(load_units().values(), key=lambda u: u['pilot_index'])
    for u in units[args.start:args.start + args.count]:
        meta = {k: u[k] for k in ('pilot_index', 'unit_id', 'date', 'country', 'speaker', 'speaker_pos', 'party',
                                  'gov_status', 'speaker_level')}
        print(json.dumps(meta, ensure_ascii=False))
        print(u['text'])
        print()


def validate(r, units):
    assert r['unit_id'] in units, r['unit_id']
    for key, allowed in ENUMS.items():
        assert r[key] in allowed, (r['unit_id'], key, r[key])
    assert type(r['rung']) is int and 0 <= r['rung'] <= 6, r
    assert type(r['coop']) is int and 0 <= r['coop'] <= 3, r
    assert set(r['history_frame']) <= FRAMES and set(r['material_issue']) <= MATERIAL, r
    assert type(r['frame_link']) is bool and type(r['dprk_reference']) is bool
    assert not r['frame_link'] or (r['history_frame'] and r['material_issue']), r
    if r['relevance'] in {'mention', 'irrelevant'}:
        assert r['rung'] == 0 and r['coop'] == 0, r
    assert r['reason_ru'].strip() and r['summary_ru'].strip()


def cmd_save(args):
    units, done = load_units(), load_annotations()
    for values in json.loads(Path(args.file).read_text(encoding='utf-8-sig')):
        assert len(values) == len(FIELDS), values[0]
        r = dict(zip(FIELDS, values))
        r.update(annotation_version=VERSION, annotator='claude-opus-5-5 (Claude Code session, no API)',
                 text_sha256=units[r['unit_id']]['text_sha256'])
        validate(r, units)
        done[r['unit_id']] = r
    ordered = sorted(done.values(), key=lambda r: units[r['unit_id']]['pilot_index'])
    ANNOTATIONS.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ordered), encoding='utf-8')
    print(json.dumps({'saved': len(done), 'remaining': len(units) - len(done)}))


def cmd_summary(_):
    units, ann = load_units(), load_annotations()
    rows = [(units[i], r) for i, r in ann.items()]
    relevant = [(u, r) for u, r in rows if r['relevance'] in {'core', 'peripheral'}]
    print('annotated', len(rows), 'relevance', Counter(r['relevance'] for _, r in rows))
    print('rung', sorted(Counter(r['rung'] for _, r in relevant).items()))
    print('coop', sorted(Counter(r['coop'] for _, r in relevant).items()))
    print('frames', Counter(f for _, r in relevant for f in r['history_frame']).most_common())
    print('material', Counter(m for _, r in relevant for m in r['material_issue']).most_common())
    print('frame_link', sum(r['frame_link'] for _, r in relevant), 'dprk', sum(r['dprk_reference'] for _, r in relevant))
    print('domestic_pressure', Counter(r['domestic_pressure'] for _, r in relevant))
    print('confidence', Counter(r['confidence'] for _, r in rows))
    print('\nby stratum: n_relevant, share rung>=3, mean rung, share frame_link, share too_soft')
    for s in KR_QUOTA:
        g = [r for u, r in relevant if u['stratum'] == s]
        if g:
            print(f'  {s:14} {len(g):3} {sum(r["rung"] >= 3 for r in g)/len(g):.2f} '
                  f'{sum(r["rung"] for r in g)/len(g):.2f} {sum(r["frame_link"] for r in g)/len(g):.2f} '
                  f'{sum(r["domestic_pressure"] == "too_soft" for r in g)/len(g):.2f}')
    print('\nby country x level: n, mean rung, share rung>=3')
    for key in sorted({(u['country'], u['speaker_level']) for u, _ in relevant}):
        g = [r for u, r in relevant if (u['country'], u['speaker_level']) == key]
        print(f'  {key} {len(g):3} {sum(r["rung"] for r in g)/len(g):.2f} {sum(r["rung"] >= 3 for r in g)/len(g):.2f}')


def cmd_review(_):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    units, ann = load_units(), load_annotations()
    wb = Workbook()
    guide = wb.active
    guide.title = 'Инструкция'
    lines = [
        'Проверка пилотной разметки DRI v2',
        '',
        'Что делать: на листе «Проверка» прочитайте текст и метки модели (серые столбцы).',
        'Заполните только жёлтые столбцы:',
        '  • «Согласна?» — да / нет / не уверена.',
        '  • Если «нет»: укажите правильную ступень и/или рамку; коротко — почему.',
        'Не нужно размечать с нуля и не нужно заполнять всё сразу: можно частями.',
        'Строки с уверенностью low и ступенью ≥3 стоят первыми — их важнее проверить.',
        '',
        'Ступени конфронтации: R0 нет · R1 обеспокоенность · R2 протест/осуждение · R3 требование ·',
        '  R4 предупреждение «ответим» · R5 угроза/призыв к конкретной мере · R6 мера объявлена.',
        'Кооперация: C0 нет · C1 позитивная оценка/диалог · C2 конкретное предложение · C3 договорённость.',
        'Уровень говорящего: L1 общество/регион · L2 депутат · L3 бюрократия · L4 министр/МИД · L5 первое лицо.',
        'Полная инструкция: docs/CODEBOOK_v2.md.',
        '',
        'Внутренний исследовательский материал: тексты не публиковать.',
    ]
    for line in lines:
        guide.append([line])
    guide.column_dimensions['A'].width = 120
    guide['A1'].font = Font(bold=True, size=14)
    ws = wb.create_sheet('Проверка')
    head = ['№', 'ID', 'Дата', 'Страна', 'Говорящий', 'Должность', 'Партия', 'Уровень', 'Период', 'Текст',
            'Релевантность', 'Ступень R', 'Кооперация C', 'Ист. рамка', 'Мат. вопрос', 'Связь рамки',
            'Давление на своё пр-во', 'КНДР', 'Уверенность', 'Обоснование модели', 'Кратко',
            'Согласна?', 'Правильная ступень R', 'Правильная рамка', 'Комментарий']
    ws.append(head)
    order = sorted(ann.values(), key=lambda r: (r['confidence'] != 'low', -r['rung'], units[r['unit_id']]['pilot_index']))
    for r in order:
        u = units[r['unit_id']]
        ws.append([u['pilot_index'], u['unit_id'], u['date'], u['country'], u['speaker'], u['speaker_pos'],
                   ' '.join(filter(None, [u['party'], u['gov_status']])), u['speaker_level'], u['stratum'],
                   u['text'], r['relevance'], f'R{r["rung"]}', f'C{r["coop"]}', ', '.join(r['history_frame']),
                   ', '.join(r['material_issue']), 'да' if r['frame_link'] else '', r['domestic_pressure'],
                   'да' if r['dprk_reference'] else '', r['confidence'], r['reason_ru'], r['summary_ru'],
                   None, None, None, None])
    widths = [5, 18, 11, 7, 10, 14, 14, 7, 12, 70, 11, 8, 8, 16, 18, 8, 12, 6, 10, 45, 40, 11, 12, 16, 40]
    for i, w in enumerate(widths):
        ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = w
    yellow = PatternFill('solid', fgColor='FFF2CC')
    grey = PatternFill('solid', fgColor='EEEEEE')
    for row in ws.iter_rows(min_row=1):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            if cell.column >= 22:
                cell.fill = yellow
            elif 11 <= cell.column <= 21 and cell.row > 1:
                cell.fill = grey
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = 'K2'
    n = ws.max_row
    agree = DataValidation(type='list', formula1='"да,нет,не уверена"', allow_blank=True)
    rung = DataValidation(type='list', formula1='"R0,R1,R2,R3,R4,R5,R6"', allow_blank=True)
    ws.add_data_validation(agree)
    ws.add_data_validation(rung)
    agree.add(f'V2:V{n}')
    rung.add(f'W2:W{n}')
    wb.save(REVIEW)
    print('review rows', n - 1, '->', REVIEW)


def kappa(pairs, weighted=False, k=7):
    n = len(pairs)
    weight = (lambda i, j: 1 - abs(i - j) / (k - 1)) if weighted else (lambda i, j: float(i == j))
    po = sum(weight(a, b) for a, b in pairs) / n
    ma, mb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ma[i] * mb[j] * weight(i, j) for i in range(k) for j in range(k)) / n / n
    return (po - pe) / (1 - pe), po


def cmd_agreement(_):
    """Read the expert workbook, store expert labels and report agreement on the rung."""
    from openpyxl import load_workbook
    ws = load_workbook(REVIEW, read_only=True)['Проверка']
    rows = list(ws.iter_rows(values_only=True))
    head = rows[0]
    expert, pairs = [], []
    for values in rows[1:]:
        row = dict(zip(head, values))
        model = int(row['Ступень R'][1])
        corrected = row['Правильная ступень R']
        verdict = row['Согласна?']
        # A filled correction wins even when the verdict says "да" (one such row in the pilot).
        label = int(corrected[1]) if corrected else (model if verdict == 'да' else None)
        expert.append(dict(unit_id=row['ID'], verdict=verdict, model_rung=model, expert_rung=label,
                           expert_frame=row['Правильная рамка'], comment=row['Комментарий'],
                           relevance=row['Релевантность'], speaker_level=row['Уровень']))
        if label is not None and row['Релевантность'] in {'core', 'peripheral'}:
            pairs.append((model, label))
    (DATA / 'dri_v2_pilot_expert.json').write_text(json.dumps(expert, ensure_ascii=False, indent=1), encoding='utf-8')
    k, po = kappa(pairs)
    kw, _ = kappa(pairs, weighted=True)
    print(f'verdicts {dict(Counter(e["verdict"] for e in expert))}')
    print(f'relevant pairs {len(pairs)}: exact agreement {po:.3f}, Cohen kappa {k:.3f}, linear weighted {kw:.3f}')
    print('expert higher / equal / lower:', dict(Counter((b > a) - (b < a) for a, b in pairs)))
    for e in expert:
        if e['expert_rung'] is None or e['expert_rung'] != e['model_rung']:
            print(f'  {e["unit_id"]:18} model R{e["model_rung"]} expert {e["expert_rung"]} ({e["verdict"]})')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('sample')
    read = sub.add_parser('read')
    read.add_argument('--start', type=int, default=0)
    read.add_argument('--count', type=int, default=40)
    save = sub.add_parser('save')
    save.add_argument('file', help='JSON array of rows in FIELDS order')
    sub.add_parser('review')
    sub.add_parser('summary')
    sub.add_parser('agreement')
    args = parser.parse_args()
    globals()['cmd_' + args.cmd](args)
