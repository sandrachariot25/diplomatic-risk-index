from datetime import date, timedelta
import unittest

from scripts.bilateral_dri import Rhetoric, calculate, changed_warnings
from scripts.prediction_backtest import Speech


class BilateralDRITests(unittest.TestCase):
    day = date(2020, 8, 31)

    def record(self, country, intensity, days_ago, *, strict=True):
        spoken = self.day - timedelta(days=days_ago)
        return Rhetoric(Speech(spoken, spoken if strict else None, spoken,
                               'document_publication', 'document_publication' if strict else 'speech_date_proxy',
                               'one speaker', 'institution', 'confrontational' if intensity else 'neutral',
                               intensity, False), country, 'parliament')

    def test_equal_country_weights_and_strict_exclusion(self):
        original = [self.record('JPN', 0, 0)] * 50
        expanded = original + [self.record('ROK', 2, 0, strict=False)] * 5
        retro = calculate(self.day, 'retrospective', original, expanded)
        self.assertEqual(retro['balanced'], {'score': 1, 'alert': 1})
        self.assertAlmostEqual(retro['expanded']['score'], 10/55)
        self.assertEqual(retro['countries']['ROK']['speakers'], 1)
        self.assertFalse(retro['comparable_changes'])
        strict = calculate(self.day, 'strict', original, expanded)
        self.assertEqual(strict['expanded'], strict['original'])
        self.assertIsNone(strict['balanced']['score'])

    def test_inclusive_window_and_opposite_movements(self):
        records = [
            self.record('ROK', 0, 89), self.record('ROK', 3, 90),
            *[self.record('ROK', 1, 44)] * 4,
            self.record('JPN', 2, 45), *[self.record('JPN', 1, 0)] * 4,
        ]
        result = calculate(self.day, 'strict', records, records)
        self.assertEqual(result['countries']['ROK']['n'], 5)
        self.assertEqual(result['countries']['ROK']['delta'], 1)
        self.assertEqual(result['countries']['JPN']['delta'], -1)
        self.assertEqual(result['unilateral_rise'], 'ROK')
        self.assertTrue(result['opposite_directions'])

    def test_missing_score_is_distinct_from_removed_alert(self):
        row = dict(assessment_date='2020-08-31', completed=True, original={'alert': 1},
                   expanded={'alert': 0}, balanced={'alert': None}, label_status='insufficient_coverage',
                   event_ids='', event_lead_days='', onset_episode_ids='')
        self.assertEqual([(r['model'], r['after']) for r in changed_warnings([row])],
                         [('expanded', 0), ('balanced', None)])
