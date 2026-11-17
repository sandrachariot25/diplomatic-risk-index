"""Join the frozen stage-2 forecasts to the independently reviewed event calendar."""
import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.paths import DATA
from scripts.update_event_truth import AS_OF, save_csv

FROZEN_HASH = 'f785d2ef98be7d83516d66a484459d90d9d9fed347c9472b902117248780b41c'
FROZEN = DATA / 'dri_backtest_stage2.csv'
EVIDENCE_2019 = {
    'minutes': 'https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=43902',
    'kang': 'https://mobile.newsis.com/view/NISX20190730_0000726455',
    'song': 'https://mobile.newsis.com/view/NISX20190730_0000726313',
    'official_august': 'https://overseas.mofa.go.kr/eg-ar/brd/m_11448/view.do?seq=760641',
}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as file:
        return list(csv.DictReader(file))


def scenario_events(events, scenario):
    if scenario not in {'all_escalations', 'exclude_court_judgments'}:
        raise ValueError(f'Unknown event scenario: {scenario}')
    return [row for row in events if row['direction'] == 'escalation'
            and (scenario == 'all_escalations' or row['action_type'] != 'court_judgment')]


def episode_starts(events):
    starts = {}
    for event in sorted(events, key=lambda row: (row['event_date'], row['event_id'])):
        starts.setdefault(event['episode_id'], event)
    return starts


def recheck(rows, events, calendar):
    by_date = {row['assessment_date']: row for row in calendar}
    by_scenario = {}
    for row in rows:
        scenario = row['scenario']
        if scenario not in by_scenario:
            actions = scenario_events(events, scenario)
            by_scenario[scenario] = actions, episode_starts(actions)
        actions, starts = by_scenario[scenario]
        assessment = row['assessment_date']
        as_of = date.fromisoformat(assessment)
        end = row['window_end']
        day = by_date[assessment]
        if end != day['window_end'] or end != (as_of + timedelta(days=30)).isoformat():
            raise ValueError(f'Forecast and target windows differ at {assessment}')
        hits = [event for event in actions if assessment < event['event_date'] <= end]
        ids = [event['event_id'] for event in hits]
        if scenario == 'all_escalations' and set(ids) != set(filter(None, day['escalation_event_ids'].split('|'))):
            raise ValueError(f'Event registry and calendar differ at {assessment}')
        if hits:
            label, target = 'confirmed_escalation', 1
        elif end > AS_OF.isoformat():
            label, target = 'right_censored', None
        elif int(day['reviewed_days']) == 30:
            label, target = 'reviewed_no_escalation', 0
        else:
            label, target = 'insufficient_coverage', None
        episodes = list(dict.fromkeys(event['episode_id'] for event in hits))
        yield {**row, 'target_30d': target, 'label_status': label,
               'evaluation_scope': 'independent_event_review',
               'event_ids': '|'.join(ids),
               'event_lead_days': '|'.join(f"{event['event_id']}:{(date.fromisoformat(event['event_date'])-as_of).days}"
                                          for event in hits),
               'reviewed_days': day['reviewed_days'], 'episode_ids': '|'.join(episodes),
               'onset_episode_ids': '|'.join(episode for episode in episodes
                                             if starts[episode]['event_id'] in ids),
               'prior_label_status': row['label_status'], 'prior_event_ids': row['event_ids']}


def warning_metrics(rows, alert_key):
    def status(row):
        return row['label_status']

    alerts = [row for row in rows if int(row[alert_key])]
    positive = sum(status(row) == 'confirmed_escalation' for row in rows)
    negative = sum(status(row) == 'reviewed_no_escalation' for row in rows)
    hits = sum(status(row) == 'confirmed_escalation' for row in alerts)
    misses = sum(status(row) == 'reviewed_no_escalation' for row in alerts)
    unknown = len(alerts) - hits - misses
    return dict(alerts=len(alerts), hits=hits, false_alerts=misses, unknown_alerts=unknown,
                positive=positive, negative=negative, unknown=len(rows)-positive-negative,
                precision=hits/len(alerts) if alerts and not unknown else None,
                precision_bounds=(hits/len(alerts), (hits+unknown)/len(alerts)) if alerts else None,
                registry_recall=hits/positive if positive else None)


def episode_results(events, rows, assessment_dates, alert_key):
    scored = {row['assessment_date']: row for row in rows}
    for episode, event in episode_starts(events).items():
        onset = date.fromisoformat(event['event_date'])
        planned = sorted(day for day in assessment_dates
                         if 0 < (onset - date.fromisoformat(day)).days <= 30)
        available = [day for day in planned if day in scored]
        warned = [day for day in available if int(scored[day][alert_key])]
        yield dict(episode=episode, event=event, forecasts=len(available),
                   outcome=('detected' if warned else 'missed' if available else
                            'no_forecast' if planned else 'no_scheduled_window'),
                   first_alert=warned[0] if warned else None,
                   lead_days=(onset-date.fromisoformat(warned[0])).days if warned else None)


def audit_2019():
    from scripts.prediction_backtest import EXCLUDED_DIRECTIONS, load_speeches, risk_signal, select_speeches

    speeches, _ = load_speeches()
    for day in (date(2019, 7, 31), date(2019, 8, 31)):
        strict = risk_signal(day, speeches, mode='strict')
        retro = risk_signal(day, speeches, mode='retrospective')
        material = [s.unit_id for s, _, _ in select_speeches(day, speeches, mode='retrospective')
                    if s.direction not in EXCLUDED_DIRECTIONS and s.intensity]
        # Even treating both press excerpts as sufficient evidence for the full units
        # cannot bring either date to five. Do not actually substitute publication dates.
        ceiling = strict['scored_units'] + len(set(material) & {1036, 1038})
        yield dict(date=day.isoformat(), strict_units=strict['scored_units'], strict_score=strict['score'],
                   retrospective_units=retro['scored_units'], retrospective_score=retro['score'],
                   proxy_units=retro['speech_proxy_units'], nonzero_intensity_ids=material,
                   units_if_both_reported_excerpt_units_were_admitted=ceiling)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if sha256(FROZEN.read_bytes()).hexdigest() != FROZEN_HASH:
        raise ValueError('Frozen stage-2 forecasts or baseline have changed')
    events = read_csv(DATA/'dri_event_truth.csv')
    rows = list(recheck(read_csv(FROZEN), events, read_csv(DATA/'dri_event_calendar.csv')))
    save_csv(DATA/'dri_backtest.csv', rows)
    print(f'Forecast rows: {len(rows)}; verified actions: {len(events)}')
    snapshots = read_csv(DATA/'dri_prediction_snapshots.csv')
    for mode in ('strict', 'retrospective'):
        planned = {row['assessment_date'] for row in snapshots if row['mode'] == mode
                   and row['min_units'] == '5' and row['window_end'] <= AS_OF.isoformat()}
        for scenario in ('all_escalations', 'exclude_court_judgments'):
            group = [row for row in rows if row['mode'] == mode and row['min_units'] == '5'
                     and row['scenario'] == scenario]
            for key in ('alert', 'baseline_alert'):
                episodes = list(episode_results(scenario_events(events, scenario), group, planned, key))
                outcomes = {status: sum(row['outcome'] == status for row in episodes)
                            for status in ('detected', 'missed', 'no_forecast', 'no_scheduled_window')}
                print(mode, scenario, key, len(group), warning_metrics(group, key), outcomes)
                print('Episode leads:', {e['episode']: e['lead_days'] for e in episodes if e['lead_days']})
            # The expanded Dokdo drill has its own history, but overlapped the wider trade crisis.
            merged = [{**e, 'episode_id': 'labor-trade'} if e['episode_id'] == 'dokdo-exercise-2019' else e
                      for e in scenario_events(events, scenario)]
            print(mode, scenario, '2019 merged episode sensitivity:',
                  {e['episode']: e['lead_days'] for e in episode_results(merged, group, planned, 'alert')
                   if e['outcome'] == 'detected'})
    for review in audit_2019():
        print('2019 publication check:', review)


if __name__ == '__main__':
    main()
