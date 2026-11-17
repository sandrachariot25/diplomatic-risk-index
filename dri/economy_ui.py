"""Read-only presentation of the economic trade exports."""
import altair as alt
import pandas as pd
import streamlit as st

from dri.paths import DATA
from scripts.economic_trade import SECTORS, SOURCES

COUNTRY = {'JPN': 'Япония', 'KOR': 'Республика Корея'}


def load(name):
    return pd.read_csv(DATA / name, dtype={'commodity': str, 'period': str})


def series(frame, field, title, *, format=None, category='Страна', detail=None):
    encoding = {
        'x': alt.X('Дата:T', title=None),
        'y': alt.Y(f'{field}:Q', title=title, axis=alt.Axis(format=format) if format else alt.Axis()),
        'color': alt.Color(f'{category}:N', title=category),
        'tooltip': ['period:N', f'{category}:N', alt.Tooltip(f'{field}:Q', format=format or ',.2f')],
    }
    if detail:
        encoding['detail'] = alt.Detail(f'{detail}:N')
        encoding['tooltip'].append(f'{detail}:N')
    chart = alt.Chart(frame).mark_line(point=True).encode(**encoding)
    st.altair_chart(chart, width='stretch')


def economy_page():
    st.subheader('Экономические отношения')
    if not (DATA/'trade_monthly.csv').exists():
        st.info('Экономические ряды появятся после импорта официальных выгрузок.')
        return
    monthly = load('trade_monthly.csv')
    structure = load('trade_structure.csv')
    dependencies = load('trade_dependency.csv')
    available_months = monthly['period'].tolist()
    native_path = DATA/'trade_japan_check.csv'
    native = load(native_path.name) if native_path.exists() else None
    if native is not None:
        available_months += native['period'].tolist()
    months = sorted(set(available_months))
    start, end = st.select_slider('Период', months, value=(months[0], months[-1]))
    selected = st.multiselect('Страны-репортёры', list(COUNTRY), default=list(COUNTRY), format_func=COUNTRY.get)
    st.caption('Историческая реконструкция по загруженным версиям источников. Суммы в текущих ценах. '
               'Пустые значения означают пробел в источнике или отсутствие сопоставимого знаменателя.')
    overview, industry, products, coverage = st.tabs(['Месячная торговля', 'Отрасли', 'Зависимость HS6', 'Покрытие и сверка'])
    frame = monthly[monthly.period.between(start, end) & monthly.reporter.isin(selected)].copy()
    frame['Дата'] = pd.to_datetime(frame.period)
    frame['Страна'] = frame.reporter.map(COUNTRY)
    with overview:
        choices = {'Оборот':'turnover_usd','Экспорт':'exports_usd','Импорт':'imports_usd',
                   'Сальдо':'balance_usd','Средняя за 3 месяца':'turnover_ma3_usd',
                   'Средняя за 12 месяцев':'turnover_ma12_usd','Изменение год к году':'turnover_yoy',
                   'Экспорт год к году':'exports_yoy','Импорт год к году':'imports_yoy',
                   'Доля партнёра в импорте':'import_share','Доля партнёра в экспорте':'export_share'}
        metric = st.selectbox('Показатель', list(choices))
        field = choices[metric]
        if field.endswith('_usd'):
            frame['usd_billion'] = frame[field]/1e9
            series(frame,'usd_billion',f'{metric}, млрд USD')
        else:
            series(frame,field,metric,format='.1%')
        st.caption('МВФ IMTS и бюллетени KCS для дополнительных месяцев Кореи. Для каждой стороны оборот равен сумме её экспорта и импорта. '
                   'Два ряда описывают один торговый коридор с разных сторон.')
    with industry:
        sectors = {'CPA_2_1_'+code: label for code,label in SECTORS.items()}
        chosen = st.selectbox('Отрасль (CPA 2.1)', list(sectors), format_func=sectors.get)
        flow = st.radio('Поток', ['M','X'], horizontal=True, format_func={'M':'Импорт','X':'Экспорт'}.get)
        subset = structure[structure.period.between(start[:4],end[:4]) & structure.reporter.isin(selected)
                           & structure.commodity.eq(chosen) & structure.flow.eq(flow)].copy()
        subset['Дата'] = pd.to_datetime(subset.period,format='%Y')
        subset['Страна'] = subset.reporter.map(COUNTRY)
        subset['usd_billion'] = subset.bilateral_usd/1e9
        series(subset,'usd_billion','Торговля с партнёром, млрд USD')
        if flow == 'M':
            series(subset,'partner_share','Доля партнёра в импорте отрасли',format='.1%')
            if subset.hhi_lower.notna().any():
                series(subset,'hhi_lower','Концентрация поставщиков (нижняя граница HHI)')
        st.dataframe(subset[['period','Страна','bilateral_usd','bilateral_structure_share','partner_share',
                             'largest_supplier','largest_supplier_share','supplier_coverage','hhi_lower','hhi_upper']],
                     hide_index=True)
        st.caption('ОЭСР BTiGE, годовые данные. Доля в структуре рассчитана от торговли с партнёром; доля '
                   'зависимости — от торговли с миром. Границы HHI учитывают остаток вне идентифицированных поставщиков.')
        with st.expander('Сравнить отрасли и концентрацию'):
            ranking = structure[structure.period.between(start[:4],end[:4])
                                & structure.reporter.isin(selected) & structure.commodity.isin(sectors)
                                & structure.flow.eq(flow)].copy()
            ranking['Отрасль'] = ranking.commodity.map(sectors)
            ranking['Страна'] = ranking.reporter.map(COUNTRY)
            st.dataframe(ranking[['period','Страна','Отрасль','bilateral_usd','bilateral_structure_share',
                                  'partner_share','supplier_coverage','hhi_lower','hhi_upper']]
                         .sort_values(['period','bilateral_usd'],ascending=False),hide_index=True)
    with products:
        hs = dependencies[dependencies.source.eq('un_comtrade')]
        labels = dict(zip(hs.commodity,hs.label))
        if labels:
            code = st.selectbox('Товар HS6', sorted(labels), format_func=lambda key:f'{key} · {labels[key]}')
            goods = hs[hs.frequency.eq('M') & hs.period.between(start,end) & hs.reporter.isin(selected)
                       & hs.commodity.eq(code)].copy()
            goods['Дата'] = pd.to_datetime(goods.period)
            goods['Страна'] = goods.reporter.map(COUNTRY)
            series(goods,'partner_share','Доля партнёра в импорте товара',format='.1%',detail='comparison_classification')
            st.dataframe(goods[['period','Страна','classification','bilateral_usd','world_usd','partner_share',
                               'partner_share_change_pp_yoy']],hide_index=True)
            suppliers = hs[hs.frequency.eq('A') & hs.period.between(start[:4],end[:4])
                           & hs.reporter.isin(selected) & hs.commodity.eq(code)].copy()
            if not suppliers.empty:
                st.markdown('**Годовая концентрация поставщиков**')
                suppliers['Дата'] = pd.to_datetime(suppliers.period,format='%Y')
                suppliers['Страна'] = suppliers.reporter.map(COUNTRY)
                series(suppliers,'hhi_lower','Нижняя граница HHI',detail='comparison_classification')
                st.dataframe(suppliers[['period','Страна','classification','named_suppliers','largest_supplier',
                                        'largest_supplier_share','supplier_coverage','hhi_lower','hhi_upper']],
                             hide_index=True)
        st.caption('UN Comtrade, девять выбранных подкатегорий. Редакции HS соединяются только для однозначных '
                   'совпадений кода в таблице ООН. Исходная редакция видна в таблице.')
    with coverage:
        st.dataframe(monthly.dropna(subset=['turnover_usd']).groupby(['source','reporter']).period
                     .agg(['min','max','count']).reset_index(),hide_index=True)
        st.caption('Зеркальная сверка сравнивает заявленный экспорт с импортом, который заявил партнёр. '
                   'FOB, CIF, сроки регистрации и определения партнёра различаются.')
        st.dataframe(frame[['period','Страна','exports_usd','partner_reported_import_usd',
                            'export_minus_mirror_usd','mirror_gap_relative_to_export','source','source_url']],
                     hide_index=True,column_config={'source_url':st.column_config.LinkColumn('Исходные данные')})
        if native is not None:
            st.markdown('**Национальный ряд Минфина Японии**')
            national = native[native.period.between(start,end)].copy()
            national['Дата'] = pd.to_datetime(national.period)
            national['Поток'] = national.flow.map({'X':'Экспорт','M':'Импорт'})
            national['jpy_billion'] = national.korea_value_thousand_jpy/1e6
            series(national,'jpy_billion','Торговля Японии с Кореей, млрд JPY',category='Поток')
            st.dataframe(national[['period','flow','korea_value_thousand_jpy','world_sum_thousand_jpy',
                                  'japan_mof_share','imf_share','share_gap','publication_date','source_url']],
                         hide_index=True,column_config={'source_url':st.column_config.LinkColumn('Исходный CSV')})
        for source, url in SOURCES.items():
            st.markdown(f'[{source}]({url})')
        for name in ('trade_monthly.csv','trade_structure.csv','trade_dependency.csv','trade_hs6.csv',
                     'trade_japan_check.csv','trade_hs_alignment.csv'):
            path = DATA/name
            if path.exists():
                st.download_button(name, path.read_bytes(), file_name=name, mime='text/csv')
