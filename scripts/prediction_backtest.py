"""Publication-aware 90-day rhetoric score and chronological 30-day experiment."""
import argparse
import calendar
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
from statistics import mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.paths import DATA, ROOT, write_generated
from scripts.annotate_llm_pilot import DB, data

DAY = timedelta(days=1)
DYAD_TIME = timezone(timedelta(hours=9))
SCORE_MIN_N = 5
MINIMUMS = (1, 3, SCORE_MIN_N)
MODES = ('strict', 'retrospective')
PROXY_SOURCES = {'kokkai_jp', 'assembly_kr', 'korea_government_kr'}
EXCLUDED_DIRECTIONS = {'irrelevant', 'uncertain'}
ALERT_THRESHOLD = 1.0
BASELINE_THRESHOLD = 0.5
SCENARIOS = ('all_escalations', 'exclude_court_judgments')
INPUTS = [DB, *(DATA / name for name in ('dri_llm_annotations.jsonl', 'dri_llm_monthly.csv',
                                          'dri_event_truth.csv', 'dri_event_calendar.csv'))]


@dataclass(frozen=True)
class Speech:
    spoken: date
    strict_available: date | None
    retrospective_available: date | None
    strict_basis: str
    retrospective_basis: str
    speaker: str | None
    institution: str | None
    direction: str
    intensity: int | None
    cooperation: bool
    unit_id: int | str | None = None


@dataclass(frozen=True)
class Escalation:
    identity: str
    day: date
    public: date
    court: bool


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def load_speeches(corpus=None):
    units, annotations = data() if corpus is None else corpus
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro', uri=True) as db:
        documents = {row[0]: (row[1], row[2], row[3], json.loads(row[4])) for row in db.execute(
            'SELECT id,source,source_type,published_date,metadata_json FROM documents')}
        statement_meta = {row[0]: row[1:] for row in db.execute(
            'SELECT id,spoken_date,published_date,speaker_id FROM statements')}
        observed = {}
        for identity, stamp in db.execute('SELECT document_id,fetched_at FROM observations'):
            if stamp:
                when = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                if when.tzinfo is not None:
                    local = when.astimezone(DYAD_TIME).date()
                    observed[identity] = min(local, observed.get(identity, local))
    speeches, unknown = [], 0
    for annotation in annotations:
        unit = units[annotation['unit_id']]
        metadata = [statement_meta[key] for key in unit['statement_ids']]
        spoken = date.fromisoformat(unit['date'])
        known_dates = [spoken, *(date.fromisoformat(value) for row in metadata for value in row[:2] if value)]
        strict_dates, retrospective_dates = list(known_dates), list(known_dates)
        strict_basis = retrospective_basis = 'document_publication'
        for identity in {fragment['ref']['document_id'] for fragment in unit['fragments']}:
            source, source_type, published, document = documents[identity]
            if published:
                publication = date.fromisoformat(published)
                strict_dates.append(publication)
                retrospective_dates.append(publication)
                continue
            capture = observed.get(identity)
            strict_dates.append(capture)
            strict_basis = 'collector_capture_bound'
            # The local minutes/speech metadata confirms the date of delivery.
            # It provides no dated evidence that the annotated text was public then.
            if (source in PROXY_SOURCES and source_type == 'primary'
                    and unit['date_basis'] == 'speech_date'
                    and document.get('event_date') == spoken.isoformat()):
                retrospective_dates.append(spoken)
                retrospective_basis = 'speech_date_proxy'
            else:
                retrospective_dates.append(capture)
                if retrospective_basis != 'speech_date_proxy':
                    retrospective_basis = 'collector_capture_bound'
        strict = None if None in strict_dates else max(strict_dates)
        retrospective = None if None in retrospective_dates else max(retrospective_dates)
        if strict is None and retrospective is None:
            unknown += 1
            continue
        speaker_id = metadata[0][2]
        name = ' '.join((unit['speaker_name'] or '').casefold().split())
        speaker = f'id:{speaker_id}' if speaker_id is not None else (
            f'{unit["country"]}:{name}' if name else None)
        institution = (unit['institution'] or '').strip()
        speeches.append(Speech(spoken, strict, retrospective, strict_basis, retrospective_basis, speaker,
                               f'{unit["country"]}:{institution}' if institution and institution != 'unknown' else None,
                               annotation['direction'], annotation['confrontation_intensity'],
                               annotation['cooperation_present'], unit_id=unit['unit_id']))
    return speeches, unknown


def select_speeches(as_of, speeches, *, mode='strict'):
    """Return the exact units admitted by the historical availability rule."""
    if mode not in MODES:
        raise ValueError('Unknown availability mode')
    start = as_of - 89*DAY
    selected = []
    for speech in speeches:
        when = speech.strict_available if mode == 'strict' else speech.retrospective_available
        basis = speech.strict_basis if mode == 'strict' else speech.retrospective_basis
        if when is not None and start <= speech.spoken <= when <= as_of:
            selected.append((speech, when, basis))
    return selected


def risk_signal(as_of, speeches=None, *, mode='strict', min_units=SCORE_MIN_N):
    """Calculate a historical score from information available by the end of as_of."""
    if speeches is None:
        speeches, _ = load_speeches()
    if min_units not in MINIMUMS:
        raise ValueError('Unknown observation minimum')
    start = as_of - 89*DAY
    recent_start = as_of - 44*DAY
    selected = select_speeches(as_of, speeches, mode=mode)
    available = [s for s,_,_ in selected]
    scored = [s for s in available if s.direction not in EXCLUDED_DIRECTIONS]
    basis_counts = Counter(basis for s,_,basis in selected if s.direction not in EXCLUDED_DIRECTIONS)
    earlier = [s.intensity for s in scored if s.spoken < recent_start]
    recent = [s.intensity for s in scored if s.spoken >= recent_start]
    earlier_mean = mean(earlier) if earlier else None
    recent_mean = mean(recent) if recent else None
    delta = recent_mean - earlier_mean if earlier and recent else None
    average = mean(s.intensity for s in scored) if scored else None
    score = min(3., average + max(0., delta or 0.)) if len(scored) >= min_units else None
    return dict(mode=mode, min_units=min_units, assessment_date=as_of.isoformat(), feature_start=start.isoformat(),
                available_units=len(available), scored_units=len(scored),
                capture_bound_units=basis_counts['collector_capture_bound'],
                publication_dated_units=basis_counts['document_publication'],
                speech_proxy_units=basis_counts['speech_date_proxy'],
                speech_proxy_share=basis_counts['speech_date_proxy']/len(scored) if scored else None,
                scored_by_time_basis=json.dumps(basis_counts,sort_keys=True),
                latest_scored_available_date=max((when for s,when,_ in selected
                                                  if s.direction not in EXCLUDED_DIRECTIONS),default=None),
                confrontational_count=sum(s.direction=='confrontational' for s in scored),
                mixed_count=sum(s.direction=='mixed' for s in scored),
                max_intensity=max((s.intensity for s in scored),default=None), mean_intensity=average,
                cooperation_share=sum(s.cooperation for s in scored)/len(scored) if scored else None,
                previous_45d_units=len(earlier), recent_45d_units=len(recent), delta_45d=delta,
                distinct_known_speakers=len({s.speaker for s in scored if s.speaker}),
                distinct_known_institutions=len({s.institution for s in scored if s.institution}),
                scored_speech_dates=len({s.spoken for s in scored}),
                coverage_status='adequate' if score is not None else 'insufficient_speech',
                coverage_band='0' if not scored else '1–2' if len(scored)<3 else '3–4' if len(scored)<5 else '5+',
                score=score, alert=int(score >= ALERT_THRESHOLD) if score is not None else None)


def load_outcomes():
    existing = {date.fromisoformat(row['assessment_date']): row
                for row in csv_rows(DATA/'dri_event_calendar.csv')}
    events = [Escalation(row['event_id'], date.fromisoformat(row['event_date']),
                         date.fromisoformat(row['first_public_date']), row['action_type']=='court_judgment')
              for row in csv_rows(DATA/'dri_event_truth.csv')
              if row['direction']=='escalation' and row['verification_status']=='confirmed']
    return events, existing


def outcome(day, events, existing):
    end = day + 30*DAY
    row = existing.get(day)
    if end > max(existing):
        return None, 'right_censored', []
    if row is None:
        return None, 'outcome_unavailable', []
    matches = [e for e in events if day < e.day <= end]
    if matches:
        return 1, '1', matches
    if row['target_30d'] == '0':
        return 0, '0_confirmed', []
    if row['status'] not in {'insufficient_coverage', 'confirmed_escalation'}:
        return None, 'outcome_unavailable', []
    return 0, '0_provisional', []


def historical_experiment(speeches, events, existing, *, mode='strict', min_units=SCORE_MIN_N):
    snapshots, backtest = [], []
    history = {scenario: [] for scenario in SCENARIOS}
    for year in range(2015, 2027):
        for month in range(1, 13):
            day = date(year, month, calendar.monthrange(year, month)[1])
            features = risk_signal(day, speeches, mode=mode, min_units=min_units)
            snap = {**features, 'window_end': (day+30*DAY).isoformat(),
                    'source_calendar_status': existing.get(day, {}).get('status')}
            for scenario in SCENARIOS:
                included = [e for e in events if scenario == SCENARIOS[0] or not e.court]
                label,status,matches = outcome(day,included,existing)
                if scenario == SCENARIOS[0] and label is not None:
                    expected = set(filter(None, existing[day]['escalation_event_ids'].split('|')))
                    if expected != {e.identity for e in matches}:
                        raise ValueError(f'Registry and existing calendar disagree at {day}')
                suffix = '' if scenario == SCENARIOS[0] else '_without_courts'
                snap['target_30d'+suffix] = label
                snap['label_status'+suffix] = status
                snap['event_ids'+suffix] = '|'.join(e.identity for e in matches)
                if label is None:
                    continue
                # Use only earlier, matured and publicly observable outcomes for the frequency baseline.
                matured = [(y, end) for y,end,known in history[scenario] if end <= day and known <= day]
                n_train = len(matured)
                train_positives = sum(y for y,_ in matured)
                baseline = (train_positives+1)/(n_train+2)
                if features['score'] is not None:
                    leads = [f'{e.identity}:{(e.day-day).days}' for e in matches]
                    backtest.append(dict(mode=mode, min_units=min_units, scenario=scenario, assessment_date=day.isoformat(),
                                         window_end=snap['window_end'], target_30d=label, label_status=status,
                                         evaluation_scope='conditional_on_current_event_registry',
                                         score=features['score'], alert=features['alert'],
                                         baseline=baseline, baseline_alert=int(baseline>=BASELINE_THRESHOLD),
                                         baseline_training_dates=n_train, baseline_training_positives=train_positives,
                                         baseline_latest_window_end=max((end for _,end in matured),default=None),
                                         **{key:features[key] for key in (
                                             'scored_units','coverage_band','scored_by_time_basis','latest_scored_available_date',
                                             'speech_proxy_units','speech_proxy_share','publication_dated_units','capture_bound_units')},
                                         event_ids=snap['event_ids'+suffix],
                                         event_lead_days='|'.join(leads) if features['alert'] else ''))
                end = day + 30*DAY
                known = min(e.public for e in matches) if matches else end
                history[scenario].append((label,end,known))
            snapshots.append(snap)
    return snapshots, backtest


def quality(rows, score_key):
    groups = Counter((row[score_key], row['target_30d']) for row in rows)
    positives = sum(row['target_30d'] for row in rows)
    negatives = len(rows)-positives
    if not positives or not negatives:
        return dict(average_precision=None, roc_auc=None)
    true_positives = false_positives = 0
    ap = auc_numerator = 0.
    for value in sorted({value for value,_ in groups}, reverse=True):
        pos, neg = groups[value,1], groups[value,0]
        auc_numerator += neg * (true_positives + 0.5*pos)
        true_positives += pos
        false_positives += neg
        ap += pos/positives * true_positives/(true_positives+false_positives)
    return dict(average_precision=ap, roc_auc=auc_numerator/(positives*negatives))


def summarize(snapshots, backtest):
    result = {}
    for scenario in SCENARIOS:
        rows = [r for r in backtest if r['scenario']==scenario]
        suffix = '' if scenario == SCENARIOS[0] else '_without_courts'
        completed = [s for s in snapshots if s['target_30d'+suffix] is not None]
        alerted = [r for r in rows if r['alert']]
        warned = {}
        for row in alerted:
            for pair in filter(None,row['event_lead_days'].split('|')):
                identity, lead = pair.split(':')
                warned[identity] = max(int(lead),warned.get(identity,0))
        result[scenario] = dict(complete=len(completed), complete_positives=sum(s['target_30d'+suffix] for s in completed),
            excluded_speech=len(completed)-len(rows), evaluated=len(rows),
            forecast_dates=sum(s['score'] is not None for s in snapshots),
            evaluated_labels=Counter(r['label_status'] for r in rows), alerts=len(alerted),
            proxy_share_scored_window_units=(sum(r['speech_proxy_units'] for r in rows)/sum(r['scored_units'] for r in rows)) if rows else None,
            unmatched_alerts=sum(r['target_30d']==0 for r in alerted), warned_event_leads=warned,
            eligible_events=len({e for r in rows for e in r['event_ids'].split('|') if e}),
            baseline_alerts=sum(r['baseline_alert'] for r in rows),
            score_metrics=quality(rows,'score'), baseline_metrics=quality(rows,'baseline'))
    return result


def export(path, rows):
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    write_generated(path, '\ufeff'+buffer.getvalue())


def plot(snapshots, backtest, events):
    os.environ['MPLCONFIGDIR'] = str(ROOT/'.venv/matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig,(ax,bx,cx) = plt.subplots(3,1,figsize=(14,8),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
    for mode,color in [('retrospective','#1d4ed8'), ('strict','#9a3412')]:
        rows = [s for s in snapshots if s['mode']==mode and s['min_units']==SCORE_MIN_N]
        dates = [date.fromisoformat(s['assessment_date']) for s in rows]
        evaluated = {r['assessment_date'] for r in backtest if r['mode']==mode
                     and r['min_units']==SCORE_MIN_N and r['scenario']==SCENARIOS[0]}
        scores = [s['score'] if s['assessment_date'] in evaluated else float('nan') for s in rows]
        ax.plot(dates,scores,'o-',lw=.8,ms=3,label=mode.capitalize(),color=color)
        bx.plot(dates,[s['scored_units'] for s in rows],lw=1,color=color,label=mode.capitalize())
        if mode == 'retrospective':
            share = [100*s['speech_proxy_share'] if s['speech_proxy_share'] is not None else float('nan') for s in rows]
            cx.plot(dates,share,lw=1,color=color)
    ax.axhline(ALERT_THRESHOLD,ls='--',lw=.9,color='#d97706',label='Warning threshold')
    ax.scatter([e.day for e in events],[3.13]*len(events),marker='v',color='#b91c1c',label='Registered escalation date')
    ax.set_ylim(-.08,3.35); ax.set_ylabel('Score (0–3)')
    ax.legend(ncol=4,loc='lower center',bbox_to_anchor=(.5,1.02),fontsize=8)
    fig.suptitle('Diplomatic Risk Index · 30-day backtest with a minimum of five text units')
    bx.axhline(SCORE_MIN_N,ls='--',color='#475569',lw=.8)
    bx.set_yscale('symlog',linthresh=5)
    bx.set_yticks([0,5,10,30,100],labels=['0','5','10','30','100'])
    bx.set_ylabel('Scored text units')
    cx.set_ylabel('Speech-date\nproxy share (%)'); cx.set_ylim(-4,104)
    cx.xaxis.set_major_locator(mdates.YearLocator()); cx.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    for panel in (ax,bx,cx):
        panel.grid(axis='y',alpha=.2)
    fig.text(.06,.023,'Points show evaluated dates. Negative labels are provisional. Proxy dates reconstruct speech timing.',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.95))
    buffer=io.BytesIO()
    fig.savefig(buffer,format='png',dpi=150)
    plt.close(fig)
    target=ROOT/'docs/DRI_prediction_backtest.png'
    temp=target.with_suffix('.png.tmp')
    temp.write_bytes(buffer.getvalue())
    temp.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat, help='Calculate one signal without using outcomes')
    parser.add_argument('--mode', choices=MODES, default='strict', help='Availability mode for --date')
    parser.add_argument('--min-units', type=int, choices=MINIMUMS, default=SCORE_MIN_N, help='Observation minimum for --date')
    args = parser.parse_args()
    if args.date:
        print(json.dumps(risk_signal(args.date,mode=args.mode,min_units=args.min_units),
                         ensure_ascii=False,indent=2,default=str))
        return
    hashes = [hashlib.sha256(path.read_bytes()).digest() for path in INPUTS]
    speeches, unknown = load_speeches()
    months = csv_rows(DATA/'dri_llm_monthly.csv')
    if sum(int(row['annotated_units']) for row in months)!=len(speeches)+unknown:
        raise ValueError('Monthly checkpoint and annotation set disagree')
    events, existing = load_outcomes()
    snapshots, backtest, results = [], [], {}
    for mode in MODES:
        results[mode] = {}
        for minimum in MINIMUMS:
            mode_snapshots, mode_backtest = historical_experiment(
                speeches,events,existing,mode=mode,min_units=minimum)
            snapshots.extend(mode_snapshots)
            backtest.extend(mode_backtest)
            results[mode][minimum] = summarize(mode_snapshots,mode_backtest)
    export(DATA/'dri_prediction_snapshots.csv',snapshots)
    export(DATA/'dri_backtest.csv',backtest)
    plot(snapshots,backtest,events)
    if hashes != [hashlib.sha256(path.read_bytes()).digest() for path in INPUTS]:
        raise RuntimeError('An input changed during the experiment')
    print(json.dumps(dict(snapshots=len(snapshots), unknown_publication=unknown,
                          source_time_bases={mode:Counter(s.strict_basis if mode=='strict' else s.retrospective_basis
                                                         for s in speeches) for mode in MODES},
                          registered_escalations=len(events), results=results),
                     ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
