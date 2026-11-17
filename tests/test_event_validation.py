"""Independent outcomes must not turn gaps or repeat actions into successes."""
import unittest

from scripts.validate_dri_events import episode_results, recheck, warning_metrics


def action(identity, day, episode='same', kind='wto_complaint'):
    return dict(event_id=identity, event_date=day, episode_id=episode,
                direction='escalation', action_type=kind)


def forecast(day='2019-07-31', end='2019-08-30', scenario='all_escalations'):
    return dict(assessment_date=day, window_end=end, scenario=scenario,
                score='1.18', alert='1', baseline='0.1', baseline_alert='0',
                label_status='0_provisional', event_ids='')


def calendar(day='2019-07-31', end='2019-08-30', reviewed='0', ids=''):
    return dict(assessment_date=day, window_end=end, reviewed_days=reviewed, escalation_event_ids=ids)


class EventValidationTests(unittest.TestCase):
    def test_partial_coverage_is_unknown_and_never_a_false_alert(self):
        source = forecast()
        row, = recheck([source], [], [calendar(reviewed='29')])
        self.assertIsNone(row['target_30d'])
        self.assertEqual(row['label_status'], 'insufficient_coverage')
        self.assertEqual(row['prior_label_status'], '0_provisional')
        for key in ('score', 'alert', 'baseline', 'baseline_alert'):
            self.assertEqual(row[key], source[key])
        metrics = warning_metrics([row], 'alert')
        self.assertEqual(metrics['false_alerts'], 0)
        self.assertIsNone(metrics['precision'])
        self.assertEqual(metrics['precision_bounds'], (0., 1.))
        verified, = recheck([source], [], [calendar(reviewed='30')])
        self.assertEqual(verified['target_30d'], 0)
        self.assertEqual(warning_metrics([verified], 'alert')['false_alerts'], 1)

    def test_episode_uses_onset_and_keeps_later_action_match(self):
        events = [action('prior', '2019-07-01'), action('next', '2019-08-30'),
                  action('too-late', '2019-08-31')]
        row, = recheck([forecast()], events, [calendar(ids='next')])
        self.assertEqual(row['event_lead_days'], 'next:30')
        self.assertEqual(row['onset_episode_ids'], '')
        episode, = episode_results(events, [row], {'2019-06-30', '2019-07-31'}, 'alert')
        self.assertEqual(episode['outcome'], 'no_forecast')
        first, = episode_results(events, [forecast(day='2019-06-30')], {'2019-06-30'}, 'alert')
        self.assertEqual(first['lead_days'], 1)

    def test_excluding_courts_does_not_confirm_absence(self):
        events = [action('court', '2019-08-01', kind='court_judgment')]
        row, = recheck([forecast(scenario='exclude_court_judgments')], events, [calendar(ids='court')])
        self.assertEqual(row['label_status'], 'insufficient_coverage')

    def test_disagreement_between_truth_and_calendar_fails(self):
        with self.assertRaises(ValueError):
            list(recheck([forecast()], [action('next', '2019-08-30')], [calendar()]))
