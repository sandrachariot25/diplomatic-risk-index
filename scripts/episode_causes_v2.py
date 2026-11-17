"""Expert workbook: causal chains of the 14 GDELT flare-ups (draft by the model + evidence from project data).

    python scripts/episode_causes_v2.py      # -> data/dri_v2_episode_causes.xlsx (refuses to overwrite filled rows)

Draft chains (trigger -> deep cause -> type) are written by the model from general knowledge up to mid-2026 and
must be checked by the expert; uncertain ones are marked. Evidence columns are generated from project data:
registry actions (t-1..t), the most confrontational annotated parliamentary turns of t-1..t (internal summaries),
and layers above their calm-month norm in t-3..t-1. Internal material: contains summaries of internal texts.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_v2 import load_done, load_units  # noqa: E402
from scripts.episodes_v2 import FEATURES, add_approval, add_material, add_material2  # noqa: E402
from scripts.forecast_gdelt_v2 import build  # noqa: E402

DATA = ROOT / 'data'
OUT = DATA / 'dri_v2_episode_causes.xlsx'
EPIS = DATA / 'dri_v2_episodes.json'
TRUTH = DATA / 'dri_event_truth.csv'
TYPES = ['суды и история', 'наследие и символы', 'экономика и рынки', 'безопасность / внешний фактор',
         'внутренняя политика', 'здравоохранение / прочее', 'неясно / возможный артефакт']
DRAFT = {
    '2017-01': ('Статуя девушки у консульства Японии в Пусане (30.12.2016) → Япония 06.01 отзывает посла и генконсула, '
                'приостанавливает переговоры о свопе.',
                'Спор об исполнении соглашения 2015 г.; вакуум власти в РК после импичмента Пак Кын Хе (12.2016) — '
                'правительство не сдерживает гражданские инициативы.', 'наследие и символы', 'средняя'),
    '2017-06': ('Неясно. Возможно: заявления нового правительства Мун Чжэ Ина (с 05.2017), что народ не принимает '
                'соглашение 2015 г.', 'Смена власти в РК и курс на пересмотр договорённостей с Японией.',
                'внутренняя политика', 'низкая — проверить'),
    '2018-01': ('Итоги проверки соглашения 2015 г. (27.12.2017) и заявление Сеула 09.01.2018: не пересматривать, '
                'но соглашение «не решает вопрос», японский 1 млрд иен заменить своими средствами → протест Японии.',
                'Пересмотр договорённостей прежнего правительства новым.', 'суды и история', 'высокая'),
    '2018-10': ('Решение Верховного суда РК по Nippon Steel (30.10); спор о флаге на смотре флота в Чеджу (10.2018).',
                'Неурегулированность претензий по договору 1965 г.; позиция правительства Мун Чжэ Ина.',
                'суды и история', 'высокая'),
    '2019-07': ('Японские ограничения на экспорт трёх материалов для чипов (01.07); официально — «безопасность и '
                'доверие».', 'Ответ на неисполнение судебных решений; экономика как рычаг (Корея зависит от японских '
                'материалов); выборы в верхнюю палату Японии (21.07).', 'суды и история', 'высокая'),
    '2020-03': ('Взаимные ограничения въезда из-за COVID-19 (05–06.03).', 'Внешний шок на фоне накопленного недоверия; '
                'выборы в РК (15.04).', 'здравоохранение / прочее', 'высокая'),
    '2021-01': ('Решение Сеульского суда против правительства Японии по «женщинам для утешения» (08.01), отказ в '
                'иммунитете государства.', 'Нерешённость вопроса после соглашения 2015 г.', 'суды и история', 'высокая'),
    '2021-09': ('Суд распорядился о продаже активов Mitsubishi Heavy Industries (27.09).',
                'Затяжной спор о принудительном труде; смена премьера Японии (выборы лидера ЛДП 29.09).',
                'суды и история', 'высокая'),
    '2022-01': ('Решение Японии выдвинуть рудник Садо в ЮНЕСКО (28.01) → протест РК.',
                'Спор о памяти принудительного труда (прецедент Хасимы 2015 г.); выборы президента РК (03.2022).',
                'наследие и символы', 'высокая'),
    '2022-10': ('Неясно. По репликам парламента РК — спор о сбросе воды Фукусимы (проект резолюции 73 депутатов, '
                'призывы к иску в Международный трибунал по морскому праву); также пуски КНДР (ракета над Японией 04.10).',
                'Фукусима: рыболовство и здоровье (материальный слой) + внутриполитическое давление оппозиции; '
                'не исключён артефакт GDELT (совместные военные события как «конфликт»).',
                'неясно / возможный артефакт', 'низкая — проверить'),
    '2023-12': ('Решения Высокого суда (23.11) и Верховного суда РК (21 и 28.12) о компенсациях.',
                'Суды продолжают дела, несмотря на схему выплат через третью сторону (03.2023).',
                'суды и история', 'высокая'),
    '2024-11': ('Корея бойкотирует поминовение на Садо (24.11) из-за участия японского парламентского секретаря, '
                'посещавшего Ясукуни.', 'Компромисс по Садо (07.2024) без признания принудительного труда.',
                'наследие и символы', 'высокая'),
    '2025-12': ('Решения корейских судов по Nippon Steel (11.12) и Nishimatsu (24.12).',
                'Продолжение судебной линии; новый кабинет Такаити (с 10.2025) на фоне спора Китая и Японии о Тайване.',
                'суды и история', 'средняя'),
    '2026-08': ('Неизвестно (после горизонта знаний модели). Проверить события около 15 августа 2026 г.', '—',
                'неясно / возможный артефакт', 'нет данных'),
}


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def main():
    if OUT.exists():
        from openpyxl import load_workbook
        rows = list(load_workbook(OUT, read_only=True)['Эпизоды'].iter_rows(values_only=True))
        k = rows[0].index('Верно?')
        assert not any(any(v not in (None, '') for v in r[k:]) for r in rows[1:]), 'filled by expert; not overwriting'
    episodes = json.loads(EPIS.read_text(encoding='utf-8'))['episodes']
    truth = list(csv.DictReader(TRUTH.open(encoding='utf-8-sig')))
    units, done = load_units(), load_done()
    feat_rows = build()
    add_approval(feat_rows)
    add_material(feat_rows)
    add_material2(feat_rows)
    idx = {r['month']: i for i, r in enumerate(feat_rows)}
    onset_months = {e['month'] for e in episodes}
    calm = [i for i, r in enumerate(feat_rows) if all(abs(i - idx[o]) > 3 for o in onset_months if o in idx)]
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    g = wb.active
    g.title = 'Инструкция'
    for line in ['Причинные цепочки 14 обострений Корея–Япония (по GDELT), 2017–2026', '',
                 'Серые столбцы — черновик модели и доказательства из данных проекта. Жёлтые — для вас.',
                 '«Верно?»: да / частично / нет. Если не «да» — исправьте тип, глубинную причину и/или повод.',
                 'Тип причины — главная, «суть», а не повод. Можно указать второй тип в комментарии.',
                 'Отдельно отметьте, была ли материальная (экономическая) причина хотя бы вторым слоем.',
                 'Черновики составлены по общим знаниям модели до середины 2026 г.; помечены низкой уверенностью там, '
                 'где модель не уверена. Эпизод 08.2026 модели неизвестен.', '',
                 'Внутренний материал (содержит резюме внутренних текстов): не публиковать.']:
        g.append([line])
    g.column_dimensions['A'].width = 120
    g['A1'].font = Font(bold=True, size=14)
    ws = wb.create_sheet('Эпизоды')
    head = ['Месяц', 'Конфликтность GDELT', 'Превышение нормы (SD)', 'Действия из реестра (t-1..t)',
            'Самые жёсткие реплики парламентов (t-1..t)', 'Слои выше нормы за 1–3 мес. до',
            'Черновик: повод', 'Черновик: глубинная причина', 'Черновик: тип', 'Уверенность модели',
            'Верно?', 'Тип причины (эксперт)', 'Глубинная причина (эксперт)', 'Повод (эксперт)',
            'Материальная причина была? (да/нет/вторым слоем)', 'Комментарий']
    ws.append(head)
    for e in episodes:
        m = e['month']
        win = {month_add(m, -1), m}
        acts = '\n'.join(f"{t['event_date']}: {t['description']}" for t in truth if t['event_date'][:7] in win)
        turns = sorted([(r['rung'], units[u]['date'], u[:2].upper(), units[u].get('speaker') or '', r['summary_ru'],
                         r['reason_ru']) for u, r in done.items()
                        if units[u]['date'][:7] in win and r['relevance'] == 'core' and r['rung'] >= 2],
                       key=lambda x: (-x[0], x[1]))[:6]
        turns_txt = '\n'.join(f'R{a} {b} {c} {d}: {f}' for a, b, c, d, _, f in turns) or '—'
        elevated = []
        i = idx.get(m)
        if i is not None:
            for label, col in FEATURES.items():
                x = np.array([r[col] for r in feat_rows], dtype=float)
                pre = np.nanmean(x[max(0, i - 3): i]) if i >= 1 else np.nan
                ref = x[calm]
                ref = ref[~np.isnan(ref)]
                if not np.isnan(pre) and len(ref) and pre > np.percentile(ref, 75):
                    elevated.append(label)
        d = DRAFT.get(m, ('', '', 'неясно / возможный артефакт', 'нет черновика'))
        ws.append([m, e['conflict_share'], e['gap_sd'], acts or '—', turns_txt, '; '.join(elevated) or '—',
                   d[0], d[1], d[2], d[3], None, None, None, None, None, None])
    widths = [9, 12, 11, 45, 70, 40, 45, 45, 18, 14, 10, 20, 40, 35, 18, 35]
    for k, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1, k).column_letter].width = w
    yellow, grey = PatternFill('solid', fgColor='FFF2CC'), PatternFill('solid', fgColor='EEEEEE')
    for row in ws.iter_rows(min_row=1):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')
            if c.row > 1:
                c.fill = yellow if c.column >= 11 else grey
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = 'B2'
    n = ws.max_row
    for col, opts in (('K', ['да', 'частично', 'нет']), ('L', TYPES), ('O', ['да', 'нет', 'вторым слоем'])):
        dv = DataValidation(type='list', formula1='"' + ','.join(opts) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f'{col}2:{col}{n}')
    wb.save(OUT)
    print(f'{OUT.name}: {len(episodes)} episodes')


if __name__ == '__main__':
    main()
