"""Reproduce bilateral DRI and its backtest from the read-only project corpus."""
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from statistics import mean
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.paths import DATA, write_generated
from scripts.annotate_llm_pilot import DB, data
from scripts.prediction_backtest import (
    ALERT_THRESHOLD, BASELINE_THRESHOLD, EXCLUDED_DIRECTIONS, MODES, SCORE_MIN_N,
    Speech, csv_rows, load_outcomes, load_speeches, outcome, risk_signal, select_speeches,
)
from scripts.validate_dri_events import AS_OF, episode_results, recheck, scenario_events, warning_metrics

END = date(2026, 10, 31)
COUNTRIES = ('ROK', 'JPN')
MODELS = ('original', 'expanded', 'balanced', 'baseline')
OUTPUT = 'dri_bilateral.json'
ADDITIONS = 'kr_hearings_annotations.jsonl'


@dataclass(frozen=True)
class Rhetoric:
    speech: Speech
    country: str
    institution_type: str


def named_speaker(name):
    return ' '.join(unicodedata.normalize('NFKC', name or '').casefold().split()) or None


def load_corpora():
    units, annotations = data()
    frozen, _ = load_speeches((units, annotations))
    original = [
        Rhetoric(replace(speech, speaker=named_speaker(units[speech.unit_id]['speaker_name'])),
                 units[speech.unit_id]['country'], units[speech.unit_id]['institution_type'])
        for speech in frozen
    ]
    new = [json.loads(line) for line in (DATA / ADDITIONS).read_text(encoding='utf-8').splitlines()]
    if len({row['unit_id'] for row in new}) != len(new):
        raise ValueError('Duplicate expansion annotation ID')
    added = []
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as db:
        for row in new:
            doc_id, = row['document_ids']
            statement_id, = row['statement_ids']
            evidence = db.execute(
                '''SELECT d.text, d.published_date, s.spoken_date, s.country, s.published_date
                   FROM documents d JOIN statement_sources ss ON d.id=ss.document_id
                   JOIN statements s ON s.id=ss.statement_id WHERE d.id=? AND s.id=?''',
                (doc_id, statement_id),
            ).fetchone()
            if not evidence or evidence[2:4] != (row['date'], row['country']):
                raise ValueError(f'Invalid expansion source link for {row["unit_id"]}')
            if sha256(evidence[0].encode()).hexdigest() != row['input_text_sha256']:
                raise ValueError(f'Expansion text hash mismatch for {row["unit_id"]}')
            if not row['analysis_eligible']:
                continue
            spoken = date.fromisoformat(row['date'])
            publication = [date.fromisoformat(value) for value in (row['published_date'], evidence[1], evidence[4]) if value]
            strict = max([spoken, *publication]) if publication else None
            if strict is None and row['availability_basis'] != 'speech_date_proxy':
                raise ValueError(f'Unknown availability basis for {row["unit_id"]}')
            retro = strict or spoken
            added.append(Rhetoric(Speech(
                spoken, strict, retro, 'document_publication' if strict else 'unknown',
                'document_publication' if strict else 'speech_date_proxy',
                named_speaker(row['speaker']), row['institution'], row['direction'],
                row['confrontation_intensity'], row['cooperation_present'], row['unit_id'],
            ), row['country'], row['institution_type']))
    return original, original + added


def stats(day, records, mode):
    speeches = [record.speech for record in records]
    signal = risk_signal(day, speeches, mode=mode)
    selected = [speech for speech, _, _ in select_speeches(day, speeches, mode=mode)
                if speech.direction not in EXCLUDED_DIRECTIONS]
    previous = [speech.intensity for speech in selected if speech.spoken < day - timedelta(days=44)]
    recent = [speech.intensity for speech in selected if speech.spoken >= day - timedelta(days=44)]
    return dict(
        score=signal['score'], alert=signal['alert'], mean_90=signal['mean_intensity'],
        mean_previous=mean(previous) if previous else None, mean_recent=mean(recent) if recent else None,
        delta=signal['delta_45d'], n=len(selected), n_previous=len(previous), n_recent=len(recent),
        speakers=signal['distinct_known_speakers'], unknown_speaker_units=sum(s.speaker is None for s in selected),
        proxy_units=signal['speech_proxy_units'], confrontational=signal['confrontational_count'],
        mixed=signal['mixed_count'], cooperation_share=signal['cooperation_share'],
    )


def institution_group(kind):
    if kind in {'government', 'foreign_ministry', 'head_of_state_administration'}:
        return 'government'
    return kind if kind == 'parliament' else 'other'


def adequate_delta(signal):
    return signal['delta'] if signal['n'] >= SCORE_MIN_N else None


def calculate(day, mode, original, expanded):
    original_score = stats(day, original, mode)
    expanded_score = stats(day, expanded, mode)
    countries = {}
    for country in COUNTRIES:
        records = [row for row in expanded if row.country == country]
        signal = stats(day, records, mode)
        signal['institutions'] = {
            group: stats(day, [row for row in records if institution_group(row.institution_type) == group], mode)
            for group in ('parliament', 'government', 'other')
        }
        parliamentary = adequate_delta(signal['institutions']['parliament'])
        executive = adequate_delta(signal['institutions']['government'])
        signal['institution_delta_gap'] = (
            parliamentary - executive if parliamentary is not None and executive is not None else None
        )
        countries[country] = signal
    scores = [countries[country]['score'] for country in COUNTRIES]
    balanced = mean(scores) if all(score is not None for score in scores) else None
    changes = [adequate_delta(countries[country]) for country in COUNTRIES]
    known = all(change is not None for change in changes)
    return dict(
        assessment_date=day.isoformat(), mode=mode, original=original_score, expanded=expanded_score,
        balanced=dict(score=balanced, alert=int(balanced >= ALERT_THRESHOLD) if balanced is not None else None),
        countries=countries, simultaneous_rise=all(change > 0 for change in changes) if known else None,
        unilateral_rise=next((country for country, change in zip(COUNTRIES, changes) if change > 0), None)
        if known and sum(change > 0 for change in changes) == 1 else None,
        opposite_directions=changes[0] * changes[1] < 0 if known else None,
        comparable_changes=known,
    )


def evaluate(windows, events, *, required=()):
    eligible = [row for row in windows if row['completed']]
    eligible = [row for row in eligible if all(row[key]['score'] is not None for key in required)]
    planned = {row['assessment_date'] for row in eligible}
    result = {}
    for model in MODELS:
        rows = [{**row, 'alert': row[model]['alert']} for row in eligible if row[model]['score'] is not None]
        episodes = list(episode_results(events, rows, planned, 'alert'))
        result[model] = dict(warning_metrics(rows, 'alert'), dates=len(rows),
                             episodes=dict(Counter(episode['outcome'] for episode in episodes)),
                             episode_details=[dict(id=e['episode'], start=e['event']['event_date'],
                                                   outcome=e['outcome'], first_alert=e['first_alert'],
                                                   lead_days=e['lead_days']) for e in episodes])
    return result


def changed_warnings(windows):
    for row in windows:
        if not row['completed']:
            continue
        before = row['original']['alert']
        for model in ('expanded', 'balanced'):
            after = row[model]['alert']
            if before == after or 1 not in (before, after):
                continue
            yield dict(date=row['assessment_date'], model=model, before=before, after=after,
                       label_status=row['label_status'], event_ids=row['event_ids'],
                       event_lead_days=row['event_lead_days'], onset_episode_ids=row['onset_episode_ids'])


def calculate_history():
    original, expanded = load_corpora()
    snapshots = [row for row in csv_rows(DATA/'dri_prediction_snapshots.csv') if int(row['min_units']) == SCORE_MIN_N]
    events = csv_rows(DATA/'dri_event_truth.csv')
    calendar = csv_rows(DATA/'dri_event_calendar.csv')
    escalations = scenario_events(events, 'all_escalations')
    original_test = [row for row in csv_rows(DATA/'dri_backtest.csv')
                     if int(row['min_units']) == SCORE_MIN_N and row['scenario'] == 'all_escalations']
    control = {(row['mode'], row['assessment_date']): row for row in original_test}
    event_objects, calendar_by_date = load_outcomes()
    days = sorted({date.fromisoformat(row['assessment_date']) for row in snapshots if row['assessment_date'] <= END.isoformat()})
    # Same historical-frequency algorithm, using the current fixed registry for all model cohorts.
    history, baseline = [], {}
    for day in days:
        matured = [label for label, horizon, public in history if horizon <= day and public <= day]
        frequency = (sum(matured) + 1) / (len(matured) + 2)
        baseline[day] = dict(score=frequency, alert=int(frequency >= BASELINE_THRESHOLD),
                             matured=len(matured), positives=sum(matured))
        label, _, matches = outcome(day, event_objects, calendar_by_date)
        if label is not None:
            end = day + timedelta(days=30)
            history.append((label, end, min((event.public for event in matches), default=end)))
    by_mode = {}
    for mode in MODES:
        windows = []
        for saved in [row for row in snapshots if row['mode'] == mode and row['assessment_date'] <= END.isoformat()]:
            day = date.fromisoformat(saved['assessment_date'])
            current = calculate(day, mode, original, expanded)
            old_score = float(saved['score']) if saved['score'] else None
            if current['original']['score'] != old_score:
                raise ValueError(f'Control score differs from frozen snapshots at {mode} {day}')
            completed = day + timedelta(days=30) <= AS_OF
            current.update(completed=completed, window_end=saved['window_end'], baseline=baseline[day])
            if completed:
                old_row = control.get((mode, day.isoformat()))
                if bool(old_row) != (old_score is not None):
                    raise ValueError(f'Control coverage differs from frozen backtest at {mode} {day}')
                seed = dict(scenario='all_escalations', assessment_date=day.isoformat(),
                            window_end=saved['window_end'], label_status='', event_ids='')
                validated, = recheck([seed], events, calendar)
                for key in ('label_status', 'target_30d', 'event_ids', 'event_lead_days', 'onset_episode_ids'):
                    current[key] = validated[key]
                    if old_row and key in ('label_status', 'event_ids', 'onset_episode_ids') and old_row[key] != current[key]:
                        raise ValueError(f'Control outcomes differ from frozen backtest at {mode} {day}')
            windows.append(current)
        by_mode[mode] = dict(windows=windows, own=evaluate(windows, escalations),
                             common=evaluate(windows, escalations, required=MODELS),
                             pooled_common=evaluate(windows, escalations, required=('original', 'expanded')),
                             changes=list(changed_warnings(windows)))
    return dict(registry_actions=len(events), corpus_counts=dict(Counter(r.country for r in expanded)),
                modes=by_mode)


if __name__ == '__main__':
    result = calculate_history()
    write_generated(DATA / OUTPUT, json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n')
    for mode, group in result['modes'].items():
        print(mode, {key: {field: value[field] for field in ('dates', 'alerts', 'hits', 'episodes')}
                     for key, value in group['own'].items()})
