"""Local Streamlit interface for the existing DRI experiment."""
from collections import Counter
import csv
import json
from datetime import date, timedelta
import sqlite3

import altair as alt
import streamlit as st

from dri.paths import DATA
from dri.economy_ui import economy_page
from dri.monitor_ui import monitor_page
from scripts.annotate_llm_pilot import DB, data
from scripts.bilateral_dri import (
    ADDITIONS, OUTPUT as BILATERAL_OUTPUT, calculate as calculate_bilateral,
    changed_warnings, evaluate as evaluate_bilateral, load_corpora as load_bilateral_corpora,
)
from scripts.live_dri import MOSCOW, canonical, instant, review_rows, verify_journal
from scripts.prediction_backtest import (
    ALERT_THRESHOLD, EXCLUDED_DIRECTIONS, SCORE_MIN_N, SCENARIOS,
    csv_rows, load_speeches, risk_signal, select_speeches,
)
from scripts.validate_dri_events import AS_OF, EVIDENCE_2019, episode_results, scenario_events, warning_metrics

START = date(2015, 1, 1)
CORPUS_END = date(2026, 10, 31)
SERIES_END = date(2026, 12, 31)
SOURCE_NAMES = {
    'kokkai_jp': 'Парламент Японии · NDL',
    'assembly_kr': 'Национальное собрание Республики Корея',
    'mofa_kr': 'МИД Республики Корея',
    'korea_government_kr': 'Правительственный портал Республики Корея',
}
DATE_BASES = {
    'document_publication': 'Публикация',
    'collector_capture_bound': 'Подтверждено к дате получения',
    'speech_date_proxy': 'Дата выступления · прокси',
}
DIRECTIONS = {
    'confrontational': 'Конфронтационная',
    'cooperative': 'Кооперативная',
    'mixed': 'Смешанная',
    'neutral': 'Нейтральная',
    'irrelevant': 'Нерелевантная',
    'uncertain': 'Неопределённая',
}
COUNTRIES = {'ROK': 'Республика Корея', 'JPN': 'Япония'}
BILATERAL_MODELS = {
    'original': 'Исходный корпус',
    'expanded': 'Расширенный корпус · общий пул',
    'balanced': 'Равный вес стран',
    'baseline': 'Baseline · историческая частота',
}
RHETORIC_INSTITUTIONS = {'parliament': 'Парламент', 'government': 'Правительство и МИД', 'other': 'Прочие'}
EVENT_DIRECTIONS = {
    'escalation': 'Эскалация',
    'cooperation': 'Сотрудничество',
    'neutral': 'Нейтральное действие',
}
EVENT_TYPES = {
    'agreement': 'Соглашение', 'agreement_restoration': 'Восстановление соглашения',
    'agreement_termination_notice': 'Уведомление о прекращении соглашения',
    'border_restriction': 'Пограничное ограничение', 'border_retaliation': 'Ответная мера на границе',
    'court_judgment': 'Судебное решение', 'defense_cooperation': 'Оборонное сотрудничество',
    'diplomatic_restoration': 'Восстановление дипломатических контактов',
    'diplomatic_retaliation': 'Дипломатическая ответная мера',
    'export_restrictions': 'Экспортное ограничение', 'settlement_decision': 'Решение об урегулировании',
    'transport_restoration': 'Восстановление сообщения', 'wto_complaint': 'Запрос консультаций ВТО',
    'wto_panel_request': 'Запрос панели ВТО', 'wto_withdrawal': 'Отзыв жалобы ВТО',
    'military_encounter': 'Военный инцидент', 'military_exercise': 'Военные учения',
    'maritime_survey': 'Морское обследование', 'official_withdrawal': 'Отзыв делегации',
    'foundation_dissolution_decision': 'Решение о роспуске фонда',
    'treaty_arbitration_request': 'Запрос арбитража', 'treaty_consultation_request': 'Запрос консультаций',
    'export_restoration': 'Снятие экспортного ограничения', 'border_cooperation': 'Возобновление поездок',
}
EVENT_OUTCOMES = {
    'confirmed_escalation': 'Подтверждённое действие',
    'reviewed_no_escalation': 'Подтверждённое отсутствие',
    'insufficient_coverage': 'Недостаточное событийное покрытие',
    'right_censored': 'Горизонт не завершён',
}
EPISODE_NAMES = {
    'ds495': 'ВТО · импорт продовольствия (DS495)',
    'ds504': 'ВТО · пневматические клапаны (DS504)',
    'ds553': 'ВТО · прутки из нержавеющей стали (DS553)',
    'shipbuilding': 'ВТО · судостроение',
    'comfort-accord': 'Спор о выполнении соглашения 2015 года',
    'labor-trade': 'Принудительный труд, экспортные меры и GSOMIA',
    'radar': 'Инцидент с кораблём и патрульным самолётом',
    'covid-border': 'Ответные пограничные меры в пандемию',
    'state-immunity': 'Иски против японского государства',
    'labor-after-settlement': 'Новые судебные решения после плана компенсаций',
    'dokdo-visits-2016': 'Докто / Такэсима · высадка депутатов',
    'dokdo-exercise-2019': 'Докто / Такэсима · расширенные учения',
    'dokdo-survey-2022': 'Докто / Такэсима · обследование 2022 года',
    'dokdo-survey-2024': 'Докто / Такэсима · обследование 2024 года',
    'sado': 'Садо · отказ от участия в церемонии',
}
SNAPSHOT_FIELDS = ('mode', 'min_units', 'assessment_date', 'score', 'alert', 'scored_units', 'speech_proxy_share')


def signature(path):
    info = path.stat()
    return info.st_mtime_ns, info.st_size


@st.cache_data(show_spinner=False)
def load_table(filename, revision, required):
    path = DATA / filename
    rows = csv_rows(path)
    if not rows or not set(required) <= rows[0].keys():
        raise ValueError(f'{filename} пуст или имеет несовместимые столбцы.')
    return rows


def table_file(filename, required):
    return load_table(filename, signature(DATA / filename), required)


@st.cache_data(show_spinner=False)
def bilateral_history(path, revision):
    return json.loads(path.read_text(encoding='utf-8'))['modes']


@st.cache_data(show_spinner=False)
def bilateral_corpora(revision):
    return load_bilateral_corpora()


@st.cache_data(show_spinner='Читаем разметку и метаданные корпуса…')
def load_corpus(revision):
    units, annotations = data()
    speeches, _ = load_speeches((units, annotations))
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as db:
        documents = {
            identity: (url, source, source_type)
            for identity, url, source, source_type in db.execute(
                'SELECT id,url,source,source_type FROM documents'
            )
        }
    metadata = {}
    summaries = {row['unit_id']: row.get('summary_ru') for row in annotations}
    for unit in units.values():
        references = sorted({fragment['ref']['document_id'] for fragment in unit['fragments']})
        metadata[unit['unit_id']] = (
            unit['speaker_name'], unit['institution'], unit['country'],
            [documents[identity] for identity in references], summaries[unit['unit_id']],
        )
    return speeches, metadata


def number(value, places=2):
    if value is None or value == '':
        return '—'
    return f'{float(value):.{places}f}'.replace('.', ',')


def percent(value):
    return '—' if value in ('', None) else number(100 * float(value), 1) + '%'


def risk_state(score, alert):
    if score in (None, ''):
        return 'Недостаточно данных'
    return 'Предупреждение' if int(alert) else 'Без предупреждения'


def interval_widget(end, key):
    if end == START:
        return START, START
    return st.slider('Интервал графика и таблиц', min_value=START, max_value=end,
                     value=(START, end), format='DD.MM.YYYY', key=key)


def filtered_events(events, start, end, *, known_at=None):
    return [row for row in events if start <= date.fromisoformat(row['event_date']) <= end
            and (known_at is None or date.fromisoformat(row['first_public_date']) <= known_at)]


def event_table(events, *, include_description=True):
    if not events:
        st.caption('В выбранном интервале нет доступных записей о событиях.')
        return
    st.dataframe([
        {'Дата': row['event_date'], 'Первое сообщение': row['first_public_date'],
         'Действие': EVENT_TYPES.get(row['action_type'], row['action_type']),
         'Направление': EVENT_DIRECTIONS.get(row['direction'], row['direction']),
         **({'Описание': row['description']} if include_description else {}),
         'Источник': row['primary_source']}
        for row in events
    ], hide_index=True, column_config={'Источник': st.column_config.LinkColumn('Первоисточник', display_text='Открыть')})


def plot_series(snapshots, events, start, end, mode, selected=None):
    if not snapshots and not events:
        st.info('В этом интервале нет месячных срезов и маркеров событий. Расширьте интервал графика.')
        return
    chart_rows, segment = [], 0
    for row in snapshots:
        score = float(row['score']) if row['score'] else None
        if score is None:
            segment += 1
        state = risk_state(score, row['alert'])
        day_label = date.fromisoformat(row['assessment_date']).strftime('%d.%m.%Y')
        chart_rows.append({
            'date': row['assessment_date'], 'day_label': day_label, 'score': score,
            'n': int(row['scored_units']), 'proxy': percent(row['speech_proxy_share']),
            'status': state, 'segment': segment,
            'aria_label': f'{day_label} · {state} · балл {number(score)} · единиц {row["scored_units"]}',
            'position': score if score is not None else -.18,
        })
    # Show a one-day interval on an axis with finite width.
    axis_end = max(end, start + timedelta(days=1))
    x = alt.X('date:T', title=None, scale=alt.Scale(type='utc', domain=[start.isoformat(), axis_end.isoformat()]))
    y = alt.Y('position:Q', title='Балл DRI', scale=alt.Scale(domain=[-.32, 3.25]),
              axis=alt.Axis(values=[0, 1, 2, 3]))
    base = alt.Chart(alt.InlineData(values=chart_rows)).encode(x=x, y=y)
    trend = base.transform_filter('isValid(datum.score)').mark_line(color='#167a89', strokeWidth=2).encode(
        detail='segment:N', order='date:T')
    points = base.mark_point(filled=True, size=53, opacity=.9).encode(
        color=alt.Color('status:N', title='Состояние',
                        scale=alt.Scale(domain=['Без предупреждения', 'Предупреждение', 'Недостаточно данных'],
                                        range=['#167a89', '#b54736', '#8291a3'])),
        shape=alt.Shape('status:N', legend=None,
                        scale=alt.Scale(domain=['Без предупреждения','Предупреждение','Недостаточно данных'],
                                        range=['circle','circle','cross'])),
        description='aria_label:N',
        tooltip=[alt.Tooltip('day_label:N', title='Дата'),
                 alt.Tooltip('score:Q', title='Балл', format='.2f'),
                 alt.Tooltip('n:Q', title='Единиц'),
                 alt.Tooltip('proxy:N', title='Прокси'), alt.Tooltip('status:N', title='Статус')])
    threshold = alt.Chart(alt.InlineData(values=[{'position': ALERT_THRESHOLD}])).mark_rule(
        color='#b54736', strokeDash=[4, 5], opacity=.65).encode(y=y)
    event_points = alt.Chart(alt.InlineData(values=[
        {'date': row['event_date'], 'position': 3.13,
         'day_label': date.fromisoformat(row['event_date']).strftime('%d.%m.%Y'),
         'aria_label': f'{row["event_date"]} · {EVENT_TYPES.get(row["action_type"], row["action_type"])}',
         'direction': EVENT_DIRECTIONS.get(row['direction'], row['direction']),
         'action': EVENT_TYPES.get(row['action_type'], row['action_type']),
         'description': row['description'] if selected is None else None} for row in events
    ])).mark_point(shape='triangle-down', filled=True, color='#604295', size=82, opacity=.9).encode(
        x=x, y=y, description='aria_label:N', tooltip=[alt.Tooltip('day_label:N', title='Дата события'),
                           alt.Tooltip('direction:N', title='Направление'),
                           alt.Tooltip('action:N', title='Действие'),
                           *([alt.Tooltip('description:N', title='Описание')] if selected is None else [])])
    layers = [threshold, trend, points, event_points]
    if selected is not None and start <= selected <= end:
        layers.insert(0, alt.Chart(alt.InlineData(values=[{'date': selected.isoformat()}]))
                      .mark_rule(color='#536780', opacity=.55).encode(x=x))
    chart = alt.layer(*layers).properties(height=290).configure_view(strokeOpacity=0)
    st.vega_lite_chart(spec=chart.to_dict(), width='stretch')
    st.caption(f'{mode.capitalize()} · фиолетовые треугольники обозначают события · '
               'серые кресты ниже шкалы показывают месяцы с недостатком данных.')


def explain_signal(signal):
    score = signal['score']
    if score is None:
        st.info(f'Недостаточно данных. В окне {signal["scored_units"]} содержательных единиц '
                f'при минимуме {SCORE_MIN_N}. Балл не рассчитан.')
    elif score == 0:
        st.info('Конфронтационный сигнал не выявлен в доступных высказываниях. '
                'Нулевой балл описывает риторику в этом окне. Дипломатический риск может сохраняться.')
    elif signal['alert']:
        threshold = 'превышен' if score > ALERT_THRESHOLD else 'достигнут'
        st.warning(f'Порог предупреждения {threshold}. Балл {number(score)} при пороге '
                   f'{number(ALERT_THRESHOLD, 1)}.')
    else:
        st.info(f'В доступной риторике есть конфронтационный сигнал. Балл {number(score)} '
                f'ниже порога предупреждения {number(ALERT_THRESHOLD, 1)}.')


def corpus_context(selected, metadata, cooperation_share):
    directions, countries, institutes = Counter(), Counter(), Counter()
    rows = []
    ordered = sorted(selected, key=lambda item: (item[0].spoken, item[0].unit_id), reverse=True)
    for speech, when, basis in ordered:
        speaker, institution, country, documents, _ = metadata[speech.unit_id]
        included = speech.direction not in EXCLUDED_DIRECTIONS
        if included:
            directions[speech.direction] += 1
            countries[country] += 1
            institutes[country, institution or 'Не указан'] += 1
        for url, source, source_type in documents:
            rows.append({
                'ID': speech.unit_id, 'Дата высказывания или публикации': speech.spoken.isoformat(),
                'Доступно с': when.isoformat(), 'Основание даты': DATE_BASES[basis],
                'Автор': speaker or 'Не указан', 'Институт': institution or 'Не указан',
                'Издатель': SOURCE_NAMES.get(source, source),
                'Тип': {'primary':'Первоисточник','secondary':'Вторичный'}.get(source_type, source_type),
                'В расчёте': included, 'Ссылка': url,
            })
    st.subheader('Контекст окна')
    st.caption('Распределения, доля кооперации и состав источников описывают выборку. '
               'Отдельных коэффициентов для них в формуле нет.')
    total = sum(directions.values())
    st.markdown('**Состав политической риторики**')
    for column, (key, label) in zip(st.columns(4), list(DIRECTIONS.items())[:4]):
        count = directions[key]
        column.metric(label, f'{count} · {percent(count/total) if total else "—"}')
    st.caption(f'Доля кооперативных сигналов {percent(cooperation_share)}. '
               'Этот показатель учитывает признак кооперации и в смешанных единицах.')
    st.markdown('**Государства и институты**')
    if total:
        for key, label in COUNTRIES.items():
            count = countries[key]
            st.progress(count/total, text=f'{label} · {count} из {total} · {percent(count/total)}')
        if countries['ROK'] == countries['JPN']:
            st.caption('В окне поровну единиц от обеих стран.')
        else:
            dominant = max(COUNTRIES, key=lambda key: countries[key])
            st.caption(f'Перекос выборки: больше высказываний со стороны «{COUNTRIES[dominant]}». '
                       f'Доля составляет {percent(countries[dominant]/total)}. '
                       'Распределение отражает покрытие корпуса.')
        st.markdown('**Институты в окне прогноза**')
        for (country, name), count in institutes.most_common():
            st.progress(count/total, text=f'{name} · {COUNTRIES.get(country, country)} · '
                        f'{count} из {total} · {percent(count/total)}')
    else:
        st.caption('В окне нет содержательных единиц для распределения.')
    st.subheader('Источники высказываний')
    if rows:
        page_size = 6
        page_count = (len(ordered) + page_size - 1) // page_size
        page = st.selectbox('Страница карточек', range(1, page_count+1),
                            format_func=lambda item: f'{item} из {page_count}') if page_count > 1 else 1
        st.caption(f'Доступно карточек: {len(ordered)}. Резюме взяты из сохранённой разметки.')
        for speech, when, basis in ordered[(page-1)*page_size:page*page_size]:
            speaker, institution, country, documents, summary = metadata[speech.unit_id]
            with st.container(border=True):
                st.markdown(f'**{speech.spoken:%d.%m.%Y} · {speaker or "Автор не указан"}**')
                st.write(f'{institution or "Институт не указан"} · {COUNTRIES.get(country, country)}')
                intensity = '—' if speech.intensity is None else f'{speech.intensity}/3'
                st.caption(f'{DIRECTIONS[speech.direction]} · интенсивность {intensity} · '
                           f'доступно с {when:%d.%m.%Y} · {DATE_BASES[basis]}')
                st.write(summary or 'Русскоязычное резюме отсутствует.')
                for url, source, source_type in documents:
                    label = 'Первоисточник' if source_type == 'primary' else 'Документ'
                    st.markdown(f'[{label} · {SOURCE_NAMES.get(source, source)}](<{url}>)')
        st.caption('Одна аналитическая единица может ссылаться на несколько документов. '
                   'Столбец «В расчёте» отмечает содержательные единицы. При недостаточном покрытии балл отсутствует.')
        st.dataframe(rows, hide_index=True, column_config={
            'Ссылка': st.column_config.LinkColumn('Документ', display_text='Открыть')})
    else:
        st.info('По правилам выбранного режима в 90-дневном окне нет доступных высказываний.')


def forecast_page(snapshots, events, mode, as_of):
    revision = (signature(DB), signature(DATA/'dri_llm_annotations.jsonl'))
    speeches, metadata = load_corpus(revision)
    signal = risk_signal(as_of, speeches, mode=mode, min_units=SCORE_MIN_N)
    selected = select_speeches(as_of, speeches, mode=mode)
    st.caption(f'ИСТОРИЧЕСКИЙ ПРОГНОЗ · {as_of:%d.%m.%Y} · ГОРИЗОНТ 30 ДНЕЙ')
    left, middle, right = st.columns(3)
    left.metric('Исходный балл риска · 0–3', number(signal['score']))
    middle.metric('Статус', risk_state(signal['score'], signal['alert']))
    right.metric('Единиц в расчётном окне', signal['scored_units'],
                 help=f'Минимум для расчёта балла — {SCORE_MIN_N} содержательных единиц.')
    explain_signal(signal)
    st.write(f'**Прогнозный горизонт:** {as_of + timedelta(days=1):%d.%m.%Y} — '
             f'{as_of + timedelta(days=30):%d.%m.%Y} включительно.')
    st.caption(f'Доля прокси-дат {percent(signal["speech_proxy_share"])} · '
               f'дней с содержательными единицами {signal["scored_speech_dates"]} · '
               'балл выражен в единицах экспериментальной шкалы.')
    st.subheader('Из чего складывается балл')
    mean_col, delta_col, added_col = st.columns(3)
    mean_col.metric('Средняя интенсивность · 90 дней', number(signal['mean_intensity']))
    delta_col.metric('Изменение · 45 дней к предыдущим 45', number(signal['delta_45d']))
    addition = max(0., signal['delta_45d'] or 0.)
    added_col.metric('Добавка за рост', number(addition) if signal['score'] is not None else '—')
    st.caption(f'Средняя интенсивность плюс положительное изменение, максимум 3. '
               f'Порог предупреждения {number(ALERT_THRESHOLD, 1)}. '
               'Снижение интенсивности не прибавляет баллов.')
    st.write(f'**Первые 45 дней** · {as_of - timedelta(days=89):%d.%m.%Y} — '
             f'{as_of - timedelta(days=45):%d.%m.%Y} · {signal["previous_45d_units"]} ед.  \n'
             f'**Последние 45 дней** · {as_of - timedelta(days=44):%d.%m.%Y} — '
             f'{as_of:%d.%m.%Y} · {signal["recent_45d_units"]} ед.')
    st.subheader('Исторический ряд')
    start, end = interval_widget(as_of, 'forecast_interval')
    visible = series_rows(snapshots, mode, start, end)
    known = filtered_events(events, start, end, known_at=as_of)
    plot_series(visible, known, start, end, mode, as_of)
    with st.expander('События, известные к дате прогноза'):
        event_table(known, include_description=False)
    corpus_context(selected, metadata, signal['cooperation_share'])
    path = DATA / BILATERAL_OUTPUT
    if path.exists():
        bilateral_forecast(bilateral_history(path, signature(path))[mode], mode, as_of, start, end)


def bilateral_forecast(history, mode, as_of, start, end):
    revision = tuple(signature(path) for path in (DB, DATA/'dri_llm_annotations.jsonl', DATA/ADDITIONS))
    window = calculate_bilateral(as_of, mode, *bilateral_corpora(revision))
    st.subheader('Двусторонняя риторика · окно 90 дней')
    for column, key in zip(st.columns(3), ('original', 'expanded', 'balanced')):
        signal = window[key]
        column.metric(BILATERAL_MODELS[key], number(signal['score']),
                      help=risk_state(signal['score'], signal['alert']))
    st.caption('Общий пул использует прежнюю формулу для всех реплик. Баланс — среднее двух страновых '
               'баллов с весами 50/50 при ≥5 единицах каждой страны. Порог предупреждения для DRI — 1,0.')
    series = []
    for country, name in COUNTRIES.items():
        segment = 0
        for row in history['windows']:
            day = date.fromisoformat(row['assessment_date'])
            if not start <= day <= min(end, as_of):
                continue
            signal = row['countries'][country]
            if signal['score'] is None:
                segment += 1
                continue
            series.append(dict(day=row['assessment_date'], country=name, segment=segment,
                               score=signal['score'], n=signal['n'], speakers=signal['speakers']))
    if series:
        chart = alt.Chart(alt.Data(values=series)).mark_line(point=True).encode(
            x=alt.X('day:T', title='Дата оценки'),
            y=alt.Y('score:Q', title='Балл риторики', scale=alt.Scale(domain=[0, 3])),
            color=alt.Color('country:N', title='Страна'),
            detail='segment:N', tooltip=['day:T', 'country:N', 'score:Q', 'n:Q', 'speakers:Q'])
        st.altair_chart(chart, width='stretch')
    else:
        st.caption('В выбранном интервале нет месячных дат с достаточным числом реплик для странового балла.')
    details = []
    for country, name in COUNTRIES.items():
        signal = window['countries'][country]
        for label, stats in [('Все источники', signal), *(
            (RHETORIC_INSTITUTIONS[key], value) for key, value in signal['institutions'].items()
        )]:
            details.append({
                'Страна': name, 'Институт автора': label, 'Единиц': stats['n'],
                'Известных говорящих': stats['speakers'], 'Без имени': stats['unknown_speaker_units'],
                'Прокси-дат': stats['proxy_units'], 'Балл': stats['score'],
                'Средняя за 90 дней': stats['mean_90'],
                'Первые 45 · ед.': stats['n_previous'], 'Первые 45 · средняя': stats['mean_previous'],
                'Последние 45 · ед.': stats['n_recent'], 'Последние 45 · средняя': stats['mean_recent'],
                'Изменение': stats['delta'],
            })
    st.dataframe(details, hide_index=True)
    st.caption('Известные говорящие сгруппированы по нормализованным именам внутри страны и окна. '
               'Средние показаны и для малых выборок. Для сопоставления изменений нужны ≥5 единиц '
               'в каждой группе и данные в обеих половинах окна.')
    if window['comparable_changes']:
        if window['simultaneous_rise']:
            st.write('Конфронтационность выросла в обеих странах.')
        elif window['unilateral_rise']:
            name = COUNTRIES[window['unilateral_rise']]
            st.write(f'Рост только на одной стороне · {name}.' +
                     (' В другой стране интенсивность снизилась.' if window['opposite_directions'] else ''))
        else:
            st.write('Рост конфронтационности в этих двух отрезках не выявлен.')
    else:
        st.caption('Данных для сравнения направления изменений двух стран недостаточно.')
    for country, name in COUNTRIES.items():
        gap = window['countries'][country]['institution_delta_gap']
        if gap is not None:
            st.write(f'{name} · разность изменений парламента и правительства {number(gap)}.')


def series_rows(rows, mode, start, end):
    return sorted(
        ({field: row[field] for field in SNAPSHOT_FIELDS}
         for row in rows if row['mode']==mode and int(row['min_units'])==SCORE_MIN_N
         and start <= date.fromisoformat(row['assessment_date']) <= end),
        key=lambda row: row['assessment_date'],
    )


def backtest_rows(rows, mode, start, end):
    return [
        {**row, 'score': float(row['score']), 'baseline': float(row['baseline']),
         'target_30d': int(row['target_30d']) if row['target_30d'] else None, 'alert': int(row['alert']),
         'baseline_alert': int(row['baseline_alert'])}
        for row in rows if row['mode']==mode and int(row['min_units'])==SCORE_MIN_N
        and row['scenario']==SCENARIOS[0]
        and start <= date.fromisoformat(row['assessment_date']) <= end
    ]


def warning_table(rows, by_id):
    warnings = []
    for row in rows:
        if not row['alert']:
            continue
        leads = [entry.split(':', 1) for entry in row['event_lead_days'].split('|') if entry]
        for identity, lead in leads or [('', None)]:
            event = by_id.get(identity)
            warnings.append({
                'Предупреждение': row['assessment_date'], 'Балл': row['score'],
                'Единиц': int(row['scored_units']), 'Исход': EVENT_OUTCOMES[row['label_status']],
                'Дата события': event['event_date'] if event else None,
                'Действие': event['description'] if event else None,
                'Эпизод': EPISODE_NAMES.get(event['episode_id'], event['episode_id']) if event else None,
                'До начала эпизода': (event['episode_id'] in row['onset_episode_ids'].split('|')
                                      if event else None),
                'Опережение, дней': int(lead) if lead else None,
                'Источник': event['primary_source'] if event else None,
            })
    if warnings:
        st.dataframe(warnings, hide_index=True, column_config={
            'Балл': st.column_config.NumberColumn('Балл', format='%.2f'),
            'Источник': st.column_config.LinkColumn('Первоисточник', display_text='Открыть')})
    else:
        st.caption('В этом интервале нет предупреждений с завершённым 30-дневным окном.')


def backtest_page(snapshots, events, mode):
    st.caption('РЕТРОСПЕКТИВНАЯ ПРОВЕРКА · СОБЫТИЯ ПОСЛЕ ДАТЫ ПРОГНОЗА')
    st.info('События проверены отдельно от прогноза. Если в реестре нет действия и не проверены '
            'все 30 дней, исход остаётся неопределённым.')
    start, end = interval_widget(SERIES_END, 'backtest_interval')
    raw_rows = table_file('dri_backtest.csv', (
        'mode','min_units','scenario','assessment_date','score','baseline','target_30d',
        'alert','baseline_alert','scored_units','event_lead_days','label_status','onset_episode_ids'))
    rows = backtest_rows(raw_rows, mode, start, end)
    planned = {row['assessment_date'] for row in snapshots
               if (date.fromisoformat(row['assessment_date']) + timedelta(days=30)) <= AS_OF
               and row['mode']==mode and int(row['min_units'])==SCORE_MIN_N
               and start <= date.fromisoformat(row['assessment_date']) <= end}
    dri = warning_metrics(rows, 'alert')
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('Покрытие завершённых окон', f'{len(rows)} / {len(planned)}')
    c2.metric('Неопределённых исходов', dri['unknown'])
    c3.metric('Дат с предупреждением', dri['alerts'])
    c4.metric('Предупреждений с действием', dri['hits'])
    st.caption(f'Оценённых окон: {dri["positive"]} с действием, {dri["negative"]} с проверенным '
               f'отсутствием действия, {dri["unknown"]} с неопределённым исходом.')
    st.subheader('Сравнение на одних и тех же датах')
    escalations = scenario_events(events, SCENARIOS[0])
    comparison = []
    for name, alert_key in [('DRI · риторика','alert'), ('Baseline · историческая частота','baseline_alert')]:
        metrics = warning_metrics(rows, alert_key)
        episodes = Counter(row['outcome'] for row in episode_results(escalations, rows, planned, alert_key))
        bounds = metrics['precision_bounds']
        comparison.append({
            'Метод': name, 'С действием': metrics['hits'], 'Без действия (проверено)': metrics['false_alerts'],
            'Неопределённых предупреждений': metrics['unknown_alerts'],
            'Precision': percent(metrics['precision']), 'Границы precision': ' — '.join(map(percent,bounds)) if bounds else '—',
            'Recall по известным действиям': percent(metrics['registry_recall']),
            'Начал эпизодов обнаружено': episodes['detected'],
            'Начал пропущено при наличии прогноза': episodes['missed'],
            'Начал без доступного прогноза': episodes['no_forecast'],
        })
    st.dataframe(comparison, hide_index=True)
    st.caption('Recall ограничен известными положительными окнами с прогнозом. Границы precision '
               'соответствуют двум крайним исходам всех неопределённых предупреждений. '
               'Baseline сохранён из прежнего эксперимента.')
    if rows and not dri['negative']:
        st.caption('Нет окон с проверенным отсутствием событий. Надёжное сравнение качества с baseline невозможно.')
    by_id = {row['event_id']: row for row in events}
    st.subheader('Предупреждения и последующие действия')
    st.caption('Интервал фильтрует даты прогнозов. Связанные действия в их 30-дневных окнах могут лежать за его пределами.')
    warning_table(rows, by_id)
    with st.expander('Все оценённые окна, включая даты без предупреждения'):
        if rows:
            st.dataframe([{'Дата прогноза': row['assessment_date'], 'Конец горизонта': row['window_end'],
                           'Балл': row['score'], 'Предупреждение': bool(row['alert']),
                           'Исход': EVENT_OUTCOMES[row['label_status']],
                           'Действия': '; '.join(by_id[identity]['event_date']+' · '+by_id[identity]['description']
                                                 for identity in filter(None, row['event_ids'].split('|')))}
                          for row in rows], hide_index=True)
        else:
            st.caption('В этом интервале нет оценённых окон.')
    example = backtest_rows(raw_rows, 'retrospective', date(2019,7,31), date(2019,8,31))
    with st.expander('Пример 2019 · что известно о публикации', expanded=mode=='retrospective'):
        st.markdown('Даты 31 июля и 31 августа предупреждают о последующих действиях. Основной торговый '
                    f'кризис уже начался. СМИ процитировали [Кан]({EVIDENCE_2019["kang"]}) и '
                    f'[Сона]({EVIDENCE_2019["song"]}) 30 июля, но дата публикации полного '
                    f'[протокола]({EVIDENCE_2019["minutes"]}) не подтверждена. '
                    f'[Публикация МИД от 28 августа]({EVIDENCE_2019["official_august"]}) '
                    'уже учтена в Strict. Там доступны 0 из 21 и 1 из 15 единиц соответственно, '
                    'поэтому обе даты не набирают минимум 5 единиц.')
        warning_table(example, by_id)
    st.subheader('Начала независимых эпизодов')
    episodes = list(episode_results(escalations, rows, planned, 'alert'))
    labels = {'detected':'Предупреждение до начала', 'missed':'Пропущен при наличии прогноза',
              'no_forecast':'Недостаточно речевых данных', 'no_scheduled_window':'Начало вне окон интервала'}
    visible_episodes = [item for item in episodes if item['outcome'] != 'no_scheduled_window'
                        or start.isoformat() <= item['event']['event_date'] <= end.isoformat()]
    if visible_episodes:
        st.dataframe([{'Эпизод': EPISODE_NAMES.get(item['episode'], item['episode']),
                       'Начало': item['event']['event_date'],
                       'Первое действие': item['event']['description'],
                       'Исход': labels[item['outcome']], 'Опережение, дней': item['lead_days'],
                       'Источник': item['event']['primary_source']} for item in visible_episodes],
                     hide_index=True, column_config={'Источник': st.column_config.LinkColumn(display_text='Открыть')})
    st.subheader('Исторический ряд и события')
    visible_events = filtered_events(events, start, end)
    plot_series(series_rows(snapshots, mode, start, end), visible_events, start, end, mode)
    event_table(visible_events)
    path = DATA / BILATERAL_OUTPUT
    if path.exists():
        bilateral_backtest(bilateral_history(path, signature(path))[mode], escalations, by_id, start, end)


def bilateral_backtest(history, escalations, by_id, start, end):
    st.subheader('Backtest · сравнение после расширения корпуса')
    st.caption('Горизонт 30 дней. DRI с порогом 1,0 и baseline с порогом 0,5 проверены '
               'на одном реестре действий. Пропущенный эпизод имеет доступный прогноз, '
               'но до его начала предупреждения не было.')
    scope = st.selectbox('Даты сравнения', ['Все доступные для каждого метода', 'Общие для всех методов',
                                           'Общие для исходного и расширенного общего пула'])
    required = {
        'Все доступные для каждого метода': (),
        'Общие для всех методов': tuple(BILATERAL_MODELS),
        'Общие для исходного и расширенного общего пула': ('original', 'expanded'),
    }[scope]
    windows = [row for row in history['windows'] if start.isoformat() <= row['assessment_date'] <= end.isoformat()]
    metrics = evaluate_bilateral(windows, escalations, required=required)
    st.dataframe([{
        'Метод': BILATERAL_MODELS[key], 'Дат с прогнозом': row['dates'], 'Предупреждений': row['alerts'],
        'Из них с действием': row['hits'], 'Исход предупреждения неизвестен': row['unknown_alerts'],
        'Известных окон с действием': row['positive'], 'Начал обнаружено': row['episodes'].get('detected', 0),
        'Начал пропущено': row['episodes'].get('missed', 0), 'Начал без прогноза': row['episodes'].get('no_forecast', 0),
        'Начал вне выбранных окон': row['episodes'].get('no_scheduled_window', 0),
    } for key, row in metrics.items()], hide_index=True)
    st.caption('Исходы с неполным покрытием остаются неизвестными. Baseline использует историческую '
               'частоту зарегистрированных действий с прежней формулой сглаживания на текущем реестре.')
    if not metrics['baseline']['dates']:
        st.info('В выбранном режиме и интервале нет общих дат для этого сравнения.')
    with st.expander('Эпизоды и опережение по методам'):
        rows = []
        outcomes = {'detected': 'Предупреждение', 'missed': 'Пропуск', 'no_forecast': 'Нет прогноза',
                    'no_scheduled_window': 'Вне выбранных окон'}
        for i, episode in enumerate(metrics['original']['episode_details']):
            row = {'Начало': episode['start'], 'Эпизод': EPISODE_NAMES.get(episode['id'], episode['id'])}
            for key, model in metrics.items():
                detail = model['episode_details'][i]
                result = outcomes[detail['outcome']]
                if detail['lead_days'] is not None:
                    result += f' · {detail["lead_days"]} дн. ({detail["first_alert"]})'
                row[BILATERAL_MODELS[key]] = result
            rows.append(row)
        st.dataframe(rows, hide_index=True)
    with st.expander('Появившиеся и исчезнувшие предупреждения'):
        st.caption('В этом списке действуют даты выбранного интервала. Отдельный статус «Нет балла» '
                   'показывает, что двусторонний порог покрытия не достигнут.')
        statuses = {1: 'Предупреждение', 0: 'Без предупреждения', None: 'Нет балла'}
        rows = [{
            'Дата': row['date'], 'Вариант': BILATERAL_MODELS[row['model']],
            'Исходный корпус': statuses[row['before']], 'После расширения': statuses[row['after']],
            'Исход окна': EVENT_OUTCOMES[row['label_status']],
            'Действия и опережение': '; '.join(
                f'{by_id[identity]["event_date"]} · {lead} дн. · {by_id[identity]["description"]}'
                for identity, lead in (item.split(':') for item in row['event_lead_days'].split('|') if item)
            ),
        } for row in changed_warnings(windows)]
        if rows:
            st.dataframe(rows, hide_index=True)
        else:
            st.caption('В выбранном интервале предупреждения не изменились.')


def research_cases_page():
    st.subheader('Три исследовательских кейса')
    path = DATA/'dri_research_cases.json'
    if not path.exists():
        st.info('Выполните python scripts/research_cases.py.')
        return
    report = json.loads(path.read_text(encoding='utf-8'))
    st.caption('Исходные смысловые оценки сохранены. Темы — отдельные лексические признаки оригинала, '
               'не новый индекс и не экспертно подтверждённая оценка позиции по каждой теме.')
    st.dataframe([{'Кейс':c['title'],'Единиц':c['summary']['n'],
                   'Говорящих':c['summary']['speakers'],'Кооперация':percent(c['summary']['cooperation_share']),
                   'Конфронтация / смешанные':percent(c['summary']['confrontation_share'])}
                  for c in report['cases']],hide_index=True)
    choice = st.selectbox('Исторический кейс', [c['title'] for c in report['cases']])
    case = next(c for c in report['cases'] if c['title']==choice)
    conclusions = {
        '2019':'До 1 июля в сохранённой выборке нет конфронтационных единиц; корейское покрытие отсутствует. '
               'Обострение в последующих репликах — реакция, а не доказанный ранний сигнал экспортных ограничений.',
        '2023':'Кооперативная риторика японского правительства присутствует до 6 марта. '
               'Рост после объявления плана, но до саммита 16 марта, нельзя считать независимым предсказанием всего эпизода. '
               'Сохраняются территориальные и исторические противоречия; низкий общий DRI не описывает их исчезновение.',
        '2026':'Сотрудничество сосуществует с территориальными противоречиями. Общий предсентябрьский сигнал '
               'нельзя автоматически связать с Садо: проверяйте наличие именно этой темы в исходных единицах. '
               'Первое сообщение об отказе датировано 8 сентября; 9 сентября — последующее публичное сообщение.'}
    st.info(conclusions[case['id']])
    for event in case['events']:
        st.markdown(f"**{event['date']} — {event['name']}** · [Источник]({event['source']}) · {event['status']}")
        if event.get('earlier_source'):
            st.markdown(f"[Первое сообщение {event['first_report']}]({event['earlier_source']})")
    institutions = st.multiselect('Институты в кейсе', ['government','parliament','other'],
                                  default=['government','parliament','other'], key='case_institutions')
    plotted = []
    for row in case['monthly']:
        if row['institution'] not in institutions:
            continue
        for field,label in [('cooperation_share','Сотрудничество'),('confrontation_share','Конфронтация / смешанные')]:
            plotted.append(dict(month=row['month'],country=COUNTRIES[row['country']],institution=row['institution'],
                                signal=label,share=row[field],n=row['n'],coverage=row['coverage']))
    chart = alt.Chart(alt.Data(values=plotted)).mark_line(point=True).encode(
        x=alt.X('month:O',title='Месяц'),y=alt.Y('share:Q',title='Доля единиц',scale=alt.Scale(domain=[0,1])),
        color=alt.Color('signal:N',title='Риторика'),strokeDash='institution:N',
        column=alt.Column('country:N',title=None),tooltip=['month:N','country:N','institution:N','signal:N','share:Q','n:Q','coverage:N'])
    st.altair_chart(chart,width='stretch')
    st.caption('Пустые месяцы — пропуски. При 1–4 единицах колебания ненадёжны; число реплик не равно числу источников. '
               'Other включает неустановленный институт: парламентское место публикации само по себе не определяет должность говорящего.')
    st.subheader('До события · прежняя формула DRI')
    st.dataframe([{'Событие':r['event'],'На дату':r['assessment_date'],'Режим':r['mode'],
                   'DRI':r['expanded']['score'],'Равный вес стран':r['balanced']['score'],
                   'Корея, n':r['countries']['ROK']['n'],'Япония, n':r['countries']['JPN']['n']}
                  for r in case['pre_event_dri']],hide_index=True)
    st.subheader('Тематические противоречия и сотрудничество')
    themes=[]
    for row in case['monthly']:
        if row['institution'] not in institutions:
            continue
        for topic,name in report['topics'].items():
            themes.append(dict(month=row['month'],country=COUNTRIES[row['country']],institution=row['institution'],
                               topic=name,units=row['topics'].get(topic,0),
                               cooperative=row['topic_cooperation'].get(topic,0),
                               confrontational=row['topic_conflicts'].get(topic,0)))
    thematic_chart = alt.Chart(alt.Data(values=themes)).transform_fold(
        ['cooperative','confrontational'],as_=['direction','count']).mark_bar().encode(
        x=alt.X('month:O',title='Месяц'), y=alt.Y('sum(count):Q',title='Единиц с темой'),
        color='direction:N',row=alt.Row('topic:N',title=None),column=alt.Column('country:N',title=None),
        tooltip=['month:N','topic:N','country:N','direction:N',alt.Tooltip('sum(count):Q')])
    st.altair_chart(thematic_chart,width='stretch')
    st.dataframe(themes,hide_index=True)
    st.caption('Одна единица может иметь несколько тем. Конфронтационность относится к целой единице, '
               'а не обязательно ко всем упомянутым темам. Ноль упоминаний — не подтверждённое отсутствие противоречия.')
    with st.expander('Окна до / во время / после события и качество покрытия'):
        st.dataframe(case['windows'],hide_index=True)
    units=[r for r in report['units'] if r['id'] in case['unit_ids'] and r['institution'] in institutions]
    st.dataframe([{'ID':str(r['id']),'Дата':r['date'],'Страна':COUNTRIES[r['country']],
                   'Институт':r['institution'],'Автор':r['speaker'],'Оценка':r['direction'],
                   'Темы':', '.join(report['topics'][t] for t in r['topics']) or 'Не определены',
                   'Содержание':r['summary'],'Источник':r['urls'][0] if r['urls'] else None}
                  for r in units],hide_index=True,column_config={'Источник':st.column_config.LinkColumn(display_text='Открыть')})
    st.download_button('Расчёты, тематические основания и ссылки',path.read_bytes(),
                       file_name=path.name,mime='application/json')


def live_page():
    st.subheader('Актуальный DRI')
    st.caption('Перспективный пилот · подтверждённая доступность · горизонт 30 дней')
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] < 6:
            st.info('Пилот ещё не инициализирован. Команды сбора и выпуска приведены в README.')
            return
        history = verify_journal(db)
        reviews = review_rows(db)
    st.caption(f'В очереди {sum(row["annotation"] is None for row in reviews)} · '
               f'размечено {sum(row["annotation"] is not None for row in reviews)}.')
    if not history:
        st.info('Первая партия ещё ожидает выпуска перспективного прогноза.')
    else:
        latest = history[-1]
        issued = instant(latest['issued_at']).astimezone(MOSCOW)
        st.write(f'**Выпущен {issued:%d.%m.%Y в %H:%M:%S} МСК** · '
                 f'горизонт с {latest["horizon_start"]} по {latest["horizon_end"]} включительно.')
        calculation = latest['calculation']
        context = latest.get('research_context')
        if context:
            st.write('Сбор завершён: '+instant(context['collection_cutoff']).astimezone(MOSCOW).isoformat(timespec='seconds'))
            st.info(context['interpretation'])
            with st.expander('Известные события и заранее установленная проверка'):
                st.dataframe(context['known_events'],hide_index=True,
                             column_config={'source':st.column_config.LinkColumn(display_text='Источник')})
                st.write(context['verification_plan'])
                st.caption('Тематические и институциональные признаки — контекст; формула и порог не менялись.')
                st.json(context.get('thematic_inputs',{}))
        signals = [('Общий DRI', calculation['expanded']), *(
            (name, calculation['countries'][country]) for country, name in COUNTRIES.items()
        ), ('Равный вес стран', calculation['balanced'])]
        for column, (label, signal) in zip(st.columns(4), signals):
            column.metric(label, number(signal['score']))
            column.caption(risk_state(signal['score'], signal['alert']))
        st.caption('Нужно ≥5 единиц для балла. Вариант с равным весом требует ≥5 единиц каждой страны. '
                   'При неизвестной дате публикации используется подтверждённое время получения.')
        rows = []
        for country, signal in calculation['countries'].items():
            for label, group in [('Все институты', signal), *(
                (RHETORIC_INSTITUTIONS[key], value) for key, value in signal['institutions'].items()
            )]:
                rows.append({'Страна': COUNTRIES[country], 'Институт': label,
                             'Единиц': group['n'], 'Говорящих по имени': group['speakers'],
                             'Без имени': group['unknown_speaker_units'],
                             'Конфронтационных': group['confrontational'], 'Смешанных': group['mixed'],
                             'Кооперация': percent(group['cooperation_share']),
                             'Средняя за 90 дней': group['mean_90'], 'Изменение за 45 дней': group['delta']})
        st.dataframe(rows, hide_index=True)
        st.subheader('История сохранённых прогнозов')
        st.dataframe([{
            'Выпуск МСК': instant(row['issued_at']).astimezone(MOSCOW).isoformat(timespec='seconds'),
            'До даты': row['horizon_end'], 'Балл': row['calculation']['expanded']['score'],
            'Статус': risk_state(row['calculation']['expanded']['score'], row['calculation']['expanded']['alert']),
            'Новых входов': row['new_inputs'], 'Версия': row['method'], 'SHA-256': row['record_hash'],
        } for row in reversed(history)], hide_index=True)
        st.download_button('Скачать запись последнего прогноза', canonical(latest),
                           file_name=f'dri-live-{latest["assessment_date"]}.json', mime='application/json')
        st.caption('Проверена цепочка SHA-256. В записи сохранены входы, время выпуска и границы горизонта.')
    if reviews:
        st.subheader('Новые официальные материалы')
        st.dataframe([{
            'Страна': COUNTRIES[row['country']], 'Дата материала': row['spoken_date'],
            'Публикация': row['published_date'], 'Получено МСК': instant(row['available_at']).astimezone(MOSCOW).isoformat(timespec='minutes'),
            'Автор': row['speaker'], 'Институт': RHETORIC_INSTITUTIONS.get(row['institution'], row['institution']),
            'Документ': row['title'], 'Оценка': (row['annotation'] or {}).get('direction', 'Ожидает разметки'),
            'Содержание': (row['annotation'] or {}).get('summary_ru'),
            'Источник': row['url'],
        } for row in reversed(reviews)], hide_index=True,
            column_config={'Источник': st.column_config.LinkColumn(display_text='Открыть')})


def main():
    st.set_page_config(page_title='Diplomatic Risk Index', page_icon='📈', layout='wide')
    st.title('Diplomatic Risk Index')
    st.markdown('**Республика Корея — Япония** · исторический риск-сигнал на 30 дней')
    coverage_path = DATA/'kr_hearings_coverage.json'
    if coverage_path.exists():
        with st.expander('Покрытие расширенного корпуса · отдельно от прежнего прогноза'):
            coverage = json.loads(coverage_path.read_text(encoding='utf-8'))
            st.caption('Этот график описывает состав корпуса. В Retrospective для новых текстов '
                       'даты выступлений используются как прокси публикации. '
                       'Число реплик не равно числу независимых выступающих.')
            before,after=coverage['summary']['before'],coverage['summary']['after']
            st.write(f'90-дневные окна с ≥5 единицами каждой страны: '
                     f'{before["both_at_least_5"]} → {after["both_at_least_5"]}. '
                     f'Односторонние окна: {before["one_country_only"]} → {after["one_country_only"]}.')
            chart=alt.Chart(alt.Data(values=coverage['annual'])).mark_bar().encode(
                x=alt.X('year:O',title='Год'),y=alt.Y('units:Q',title='Размеченные единицы'),
                color=alt.Color('institution:N',title='Институт'),
                column=alt.Column('country:N',title='Государство'),
                tooltip=['year:O','country:N','institution:N','units:Q'])
            st.altair_chart(chart,width='stretch')
    page = st.sidebar.radio('Экран', ['Монитор DRI v2','Исторический прогноз','Backtest','Актуальный DRI','Исследовательские кейсы','Экономические отношения'], key='page')
    if page == 'Монитор DRI v2':
        monitor_page()
        return
    if page == 'Экономические отношения':
        economy_page()
        return
    if page == 'Исследовательские кейсы':
        research_cases_page()
        return
    if page == 'Актуальный DRI':
        try:
            live_page()
        except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
            st.error(f'Не удалось проверить журнал перспективного пилота. {error}')
        return
    mode = st.sidebar.radio('Режим данных', ['retrospective','strict'], format_func=str.capitalize, key='mode')
    st.sidebar.caption('Retrospective использует даты выступлений как прокси при отсутствии дат публикации. '
                       'Strict использует подтверждённые границы доступности текста.')
    if page == 'Исторический прогноз':
        as_of = st.sidebar.date_input('Дата исторического прогноза', date(2019,7,31),
                                      min_value=START, max_value=CORPUS_END, format='DD.MM.YYYY', key='as_of')
    try:
        snapshots = table_file('dri_prediction_snapshots.csv', (*SNAPSHOT_FIELDS, 'label_status'))
        events = table_file('dri_event_truth.csv', (
            'event_id','event_date','first_public_date','direction','action_type','description','primary_source'))
        if page == 'Исторический прогноз':
            forecast_page(snapshots, events, mode, as_of)
        else:
            backtest_page(snapshots, events, mode)
    except (OSError, ValueError, TypeError, KeyError, AssertionError, csv.Error, sqlite3.Error) as error:
        st.error(f'Не удалось прочитать данные DRI. Проверьте исходные файлы в папке data. '
                 f'{error or type(error).__name__}')


if __name__ == '__main__':
    main()
