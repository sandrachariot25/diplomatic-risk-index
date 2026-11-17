"""Integration checks for the optional local Streamlit interface."""
from datetime import date
import importlib.util
import unittest
from unittest.mock import patch

from dri.paths import DATA, ROOT
from scripts.bilateral_dri import OUTPUT
from scripts.prediction_backtest import csv_rows


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Web extras are optional')
class WebAppTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=25)

    def assert_renders(self):
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)

    @unittest.skipUnless((DATA/'dri_llm_annotations.jsonl').exists(), 'Requires local annotated corpus')
    def test_forecast_matches_csv_and_keeps_future_events_off_screen(self):
        self.app.run()
        self.assert_renders()
        snapshot = next(row for row in csv_rows(DATA/'dri_prediction_snapshots.csv')
                        if row['mode']=='retrospective' and row['min_units']=='5'
                        and row['assessment_date']=='2019-07-31')
        self.assertEqual(self.app.metric[0].value, f'{float(snapshot["score"]):.2f}'.replace('.', ','))
        self.assertEqual(self.app.metric[2].value, snapshot['scored_units'])
        charts = self.app.get('arrow_vega_lite_chart')
        expanded = (DATA/OUTPUT).exists()
        self.assertEqual(len(charts), 3 if expanded else 2)
        self.assertTrue(charts[1].proto.datasets)
        events, speech = [table.value for table in self.app.dataframe[:2]]
        self.assertTrue((events['Дата'] <= '2019-07-31').all())
        self.assertTrue((events['Первое сообщение'] <= '2019-07-31').all())
        self.assertNotIn('Описание', events.columns)
        self.assertTrue((speech['Доступно с'] <= '2019-07-31').all())
        self.assertEqual(speech[speech['В расчёте']]['ID'].nunique(), int(snapshot['scored_units']))
        self.assertTrue(speech['Ссылка'].str.startswith('https://').all())
        self.assertTrue(any('Порог предупреждения превышен' in item.value for item in self.app.warning))
        if expanded:
            scores = {item.label: item.value for item in self.app.metric}
            self.assertEqual(scores['Расширенный корпус · общий пул'], '0,97')
            self.assertEqual(scores['Равный вес стран'], '0,35')
            detail = self.app.dataframe[2].value
            self.assertEqual(detail['Единиц'].iloc[0], 13)
            self.assertEqual(detail['Известных говорящих'].iloc[0], 12)

        self.app.date_input(key='as_of').set_value(date(2022,7,15)).run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '0,00')
        self.assertEqual(self.app.metric[2].value, '9')
        self.assertTrue(any('Конфронтационный сигнал не выявлен' in item.value for item in self.app.info))
        self.assertTrue(any('Доля кооперативных сигналов 66,7%' in item.value for item in self.app.caption))
        self.assertTrue(any('16.07.2022 — 14.08.2022' in item.value for item in self.app.markdown))
        self.assertTrue(any('Перекос выборки' in item.value for item in self.app.caption))
        self.assertTrue(any('[Первоисточник' in item.value for item in self.app.markdown))

        self.app.date_input(key='as_of').set_value(date(2019,7,31)).run()
        self.app.radio(key='mode').set_value('strict').run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '—')
        self.assertEqual(self.app.metric[1].value, 'Недостаточно данных')
        self.app.date_input(key='as_of').set_value(date(2017,3,31)).run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '2,50')
        self.app.date_input(key='as_of').set_value(date(2015,1,1)).run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '—')

    def test_backtest_2019_and_empty_interval(self):
        self.app.run()
        self.app.radio(key='page').set_value('Backtest').run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '110 / 141')
        self.assertEqual(self.app.metric[1].value, '92')
        self.assertEqual(self.app.metric[2].value, '23')
        self.assertEqual(self.app.metric[3].value, '3')
        example = self.app.dataframe[3].value
        self.assertEqual(sorted(example['Опережение, дней']), [2,11,23,25])
        self.assertEqual(example['Предупреждение'].nunique(), 2)
        self.assertEqual(example['До начала эпизода'].sum(), 1)
        comparison = self.app.dataframe[0].value
        self.assertEqual(comparison['Без действия (проверено)'].tolist(), [0, 0])
        self.assertEqual(comparison['Неопределённых предупреждений'].tolist(), [20, 0])
        self.assertEqual(comparison['Начал эпизодов обнаружено'].tolist(), [2, 0])
        self.assertTrue(example['Источник'].str.startswith('https://').all())
        self.assertTrue(self.app.get('arrow_vega_lite_chart')[-1].proto.datasets)
        self.app.radio(key='mode').set_value('strict').run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '3 / 141')
        self.assertEqual(self.app.metric[3].value, '0')
        if (DATA/OUTPUT).exists():
            self.app.selectbox[0].set_value('Общие для всех методов').run()
            self.assert_renders()
            self.assertTrue(any('нет общих дат' in item.value for item in self.app.info))
        self.app.slider(key='backtest_interval').set_value((date(2015,1,1),date(2015,1,2))).run()
        self.assert_renders()
        self.assertEqual(self.app.metric[0].value, '0 / 0')

    def test_missing_artifact_shows_readable_error(self):
        with patch('dri.paths.DATA', ROOT/'nonexistent_dri_test_data'):
            self.app.run()
        self.assertFalse(self.app.exception)
        self.assertIn('Не удалось прочитать данные DRI', self.app.error[0].value)

    def test_live_page_displays_sealed_issue_and_sources(self):
        import sqlite3
        from scripts.live_dri import DB, verify_journal
        with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] < 6:
                self.skipTest('Live pilot schema not initialized')
            history = verify_journal(db)
        if not history:
            self.skipTest('Live pilot has not issued a forecast')
        self.app.run()
        self.app.radio(key='page').set_value('Актуальный DRI').run()
        self.assert_renders()
        latest = history[-1]
        self.assertTrue(any(latest['horizon_end'] in item.value for item in self.app.markdown))
        history_table = next(table.value for table in self.app.dataframe if 'SHA-256' in table.value.columns)
        sources = next(table.value for table in self.app.dataframe if 'Источник' in table.value.columns)
        self.assertIn(latest['record_hash'], history_table['SHA-256'].tolist())
        self.assertTrue(sources['Источник'].str.startswith('https://').all())

    def test_three_research_cases_render(self):
        if not (ROOT/'data/dri_research_cases.json').exists():
            self.skipTest('Case calculations not built')
        self.app.run()
        self.app.radio(key='page').set_value('Исследовательские кейсы').run()
        for title in ['2019 · экспортные ограничения','2023 · нормализация отношений','2026 · сотрудничество и Садо']:
            self.app.selectbox[0].set_value(title).run()
            self.assert_renders()
            self.assertGreater(len(self.app.dataframe),3)
