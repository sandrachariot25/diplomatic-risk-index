"""Streamlit screen «Монитор DRI v2»: pick a month -> tension index and its layers, risk by triggers ahead,
upcoming triggers, evidence (parliamentary turns, verified actions) and, for past dates, what happened next.

Data: data/dri_v2_monitor.json (scripts/monitor_v2.py). Internal research tool: shows summaries of internal texts.
"""
import json

import altair as alt
import streamlit as st

from dri.paths import DATA

SERIES = '#2a78d6'
TYPE_COLOURS = {'суды и история': '#2a78d6', 'наследие и символы': '#eb6834', 'экономика и рынки': '#1baf7a'}
OTHER = '#898781'
RISK = {  # level -> (icon, colour, explanation)
    'повышен': ('▲', '#d03b3b', 'В ближайшие 3 месяца — решение Верховного суда РК по делам колониального периода '
                               '(после таких месяцев обострение в 73% случаев при среднем 33%).'),
    'внимание': ('●', '#ec835a', 'В ближайшие 3 месяца — решение нижестоящего суда в пользу истцов или дата наследия '
                                 '(ЮНЕСКО, Садо); обострений чаще обычного не дают.'),
    'обычный': ('—', '#52514e', 'Острых поводов в ближайшие 3 месяца в календаре нет.'),
}
KIND = {'court': 'Суд', 'heritage': 'Наследие', 'recurring': 'Ежегодная дата', 'election': 'Выборы'}


@st.cache_data
def load(path, mtime):
    return json.loads(path.read_text(encoding='utf-8'))


def label(m):
    y, mm = m.split('-')
    names = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь',
             'ноябрь', 'декабрь']
    return f'{names[int(mm) - 1]} {y}'


def monitor_page():
    path = DATA / 'dri_v2_monitor.json'
    if not path.exists():
        st.error('Нет data/dri_v2_monitor.json. Запустите: python scripts/monitor_v2.py')
        return
    data = load(path, path.stat().st_mtime)
    months = data['months']
    by = {m['month']: m for m in months}
    st.header('Монитор DRI v2 · Республика Корея — Япония')
    st.caption('Выберите месяц: индекс напряжённости и его источники, риск обострения на 3 месяца по поводам впереди, '
               'основания и — для прошлых дат — что произошло дальше. Внутренний исследовательский инструмент.')
    choice = st.select_slider('Месяц', options=[m['month'] for m in months], value=months[-1]['month'],
                              format_func=label, key='monitor_month')
    cur = by[choice]
    icon, colour, why = RISK[cur['risk']]

    c1, c2, c3 = st.columns(3)
    c1.metric('Индекс напряжённости', f"{cur['index']:.0f} / 100",
              help='Место месяца среди всех месяцев 2016–2026 по сводке слоёв (100 — самый напряжённый). '
                   'Описывает текущее состояние; в проверке на истории он сам обострений не предсказывал.')
    c2.markdown(f"<div style='font-size:0.875rem;color:#52514e'>Риск обострения на 3 месяца</div>"
                f"<div style='font-size:2rem;font-weight:600;color:{colour}'>{icon} {cur['risk'].capitalize()}</div>"
                f"<div style='font-size:0.8rem;color:#52514e'>{why}</div>", unsafe_allow_html=True)
    c3.metric('Конфликтность в новостях', f"{100 * cur['gdelt_conflict_share']:.0f}%",
              help='Доля конфликтных событий среди событий Корея–Япония в GDELT за месяц.')

    st.subheader('Индекс напряжённости по месяцам')
    line = [dict(month=m['month'] + '-15', index=m['index'], risk=m['risk']) for m in months]
    base = alt.Chart(alt.Data(values=line)).encode(x=alt.X('month:T', title=None, axis=alt.Axis(format='%Y')))
    chart = base.mark_line(color=SERIES, strokeWidth=2).encode(
        y=alt.Y('index:Q', title='Индекс (0–100)', scale=alt.Scale(domain=[0, 100])))
    hover = base.mark_point(size=80, opacity=0).encode(
        y='index:Q', tooltip=[alt.Tooltip('month:T', title='Месяц', format='%m.%Y'),
                             alt.Tooltip('index:Q', title='Индекс', format='.0f'), alt.Tooltip('risk:N', title='Риск')])
    eps = sorted({(o['month'], o['type'], o['trigger']) for m in months for o in m['outcome']})
    ep_vals = [dict(month=e[0] + '-15', index=by[e[0]]['index'] if e[0] in by else None, type=e[1], trigger=e[2])
               for e in eps if e[0] in by]
    points = alt.Chart(alt.Data(values=ep_vals)).mark_point(filled=True, size=90, stroke='#fcfcfb', strokeWidth=2).encode(
        x='month:T', y='index:Q',
        color=alt.Color('type:N', title='Обострение: тип причины',
                        scale=alt.Scale(domain=[*TYPE_COLOURS, 'внутренняя политика', 'здравоохранение / прочее',
                                                'неясно / возможный артефакт'],
                                        range=[*TYPE_COLOURS.values(), OTHER, OTHER, OTHER])),
        tooltip=[alt.Tooltip('month:T', title='Обострение', format='%m.%Y'), alt.Tooltip('type:N', title='Тип'),
                 alt.Tooltip('trigger:N', title='Повод')])
    rule = alt.Chart(alt.Data(values=[dict(month=choice + '-15')])).mark_rule(color='#52514e', strokeWidth=1).encode(x='month:T')
    st.altair_chart((chart + hover + points + rule).properties(height=260), width='stretch')

    if True:
        st.subheader('Из чего складывается индекс')
        st.caption('Отклонение каждого слоя от его средней за 2016–2026 (в стандартных отклонениях; больше нуля — напряжённее).')
        lay = [dict(label=l['label'], group=l['group'], z=l['z'], sign='напряжённее' if l['z'] > 0 else 'спокойнее')
               for l in cur['layers'] if l['z'] is not None]
        bars = alt.Chart(alt.Data(values=lay)).mark_bar(cornerRadiusEnd=4, height=14).encode(
            y=alt.Y('label:N', title=None, sort='-x', axis=alt.Axis(labelLimit=320)),
            x=alt.X('z:Q', title='Отклонение от нормы, SD'),
            color=alt.Color('sign:N', title=None, scale=alt.Scale(domain=['напряжённее', 'спокойнее'],
                                                                  range=['#e34948', '#2a78d6'])),
            tooltip=[alt.Tooltip('label:N', title='Слой'), alt.Tooltip('group:N', title='Группа'),
                     alt.Tooltip('z:Q', title='Отклонение', format='+.2f')])
        st.altair_chart(bars.properties(height=34 * len(lay)), width='stretch')
    left, right = st.columns(2)
    with left:
        st.subheader('Поводы на ближайшие 3 месяца')
        if cur['triggers_ahead']:
            st.dataframe([{'Месяц': label(t['month']), 'Тип': KIND.get(t['kind'], t['kind']), 'Повод': t['trigger']}
                          for t in cur['triggers_ahead']], hide_index=True, width='stretch')
        else:
            st.write('В календаре нет поводов.')
        if choice == months[-1]['month'] and data.get('pipeline'):
            st.markdown('**Дела в очереди (дата оглашения не назначена)**')
            st.dataframe([{'Суд': p['court'], 'Ответчик': p['defendant'], 'Стадия': p['stage'], 'Примечание': p['note'],
                           'Источник': p['source']} for p in data['pipeline']], hide_index=True, width='stretch',
                         column_config={'Источник': st.column_config.LinkColumn(display_text='Открыть')})
    with right:
        st.subheader('Что произошло дальше')
        if cur['outcome']:
            for o in cur['outcome']:
                st.markdown(f"**{label(o['month'])} — обострение** · {o['type']}  \nПовод: {o['trigger']}  \n"
                            f"Глубинная причина: {o['deep_cause']}")
        elif choice <= '2026-07':
            st.write('В следующие 3 месяца обострений по GDELT не было.')
        else:
            st.write('Ещё не известно: 3 месяца после выбранной даты не прошли.')

    st.subheader('Основания: самые жёсткие реплики парламентов за последние 3 месяца')
    if cur['evidence_turns']:
        st.dataframe([{'Дата': t['date'], 'Страна': t['country'], 'Говорящий': t['speaker'], 'Уровень': t['level'],
                       'Ступень': f"R{t['rung']}", 'Суть': t['summary'], 'Источник': t['url']}
                      for t in cur['evidence_turns']], hide_index=True, width='stretch',
                     column_config={'Источник': st.column_config.LinkColumn(display_text='Открыть')})
    else:
        st.write('Реплик со ступенью R2 и выше за этот период нет.')
    if cur['evidence_actions']:
        st.subheader('Проверенные дипломатические действия за последние 3 месяца')
        st.dataframe([{'Дата': a['date'], 'Направление': 'эскалация' if a['direction'] == 'escalation' else
                       'сотрудничество' if a['direction'] == 'cooperation' else a['direction'],
                       'Действие': a['description'], 'Источник': a['url']} for a in cur['evidence_actions']],
                     hide_index=True, width='stretch',
                     column_config={'Источник': st.column_config.LinkColumn(display_text='Открыть')})

    chk = data['rule_check']
    with st.expander('Как это работает и насколько можно доверять'):
        st.markdown(
            f"- **Индекс напряжённости** — сводка 10 слоёв: новости (GDELT), парламенты РК и Японии, экономика "
            f"(торговый баланс, соперничество в чипах, цикл памяти), внешний фон (Китай, КНДР). Он объясняет текущее "
            f"состояние, но обострений сам не предсказывает: при индексе ≥ 70 обострение в следующие 3 месяца было в "
            f"{100 * chk['index_ge_70_share']:.0f}% месяцев при базовой частоте {100 * chk['base_rate']:.0f}%.\n"
            f"- **Риск** определяется поводами впереди. «Повышен» — в ближайшие 3 месяца решение корейского суда "
            f"(реестр из {len(data['court_check']['groups'])and data['court_check']['groups']['все решения']['n']} "
            f"решений 2018–2026, все исходы): обострение последовало в {100 * chk['повышен']['share']:.0f}% таких "
            f"месяцев; «внимание» — {100 * chk['внимание']['share']:.0f}%; «обычный» — "
            f"{100 * chk['обычный']['share']:.0f}% (в среднем {100 * chk['base_rate']:.0f}%).\n"
            f"- **Сами решения судов** — сильнейший известный заранее повод: в месяц решения конфликтность в среднем "
            f"выше нормы на {data['court_check']['groups']['все решения']['mean_gap_sd']:+.1f} SD (Верховный суд — "
            f"{data['court_check']['groups']['Верховный суд']['mean_gap_sd']:+.1f} SD); обострение начинается в том же "
            f"или следующем месяце в {100 * data['court_check']['groups']['все решения']['share']:.0f}% случаев против "
            f"{100 * data['court_check']['base']:.0f}% в среднем. Около половины обострений — не от судов "
            f"(наследие, внутренняя политика, экономика, внешние шоки), поэтому флажок за 3 месяца даёт умеренный прирост.\n"
            f"- **Обострения** — 14 эпизодов 2017–2026 по GDELT; тип причины — экспертная разметка.\n"
            f"- Подробности: docs/MODEL_RESULTS_2026-11-12.md.")
