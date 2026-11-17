"""Read-only DRI v0.2 event scoring and conditional monthly aggregation."""
import json
import re
import sqlite3
from collections import Counter,defaultdict
from .analytical_sample import load_sample,digest
from .analytics import calendar_months
from .contextual import ContextClassifier
from .paths import ROOT

def aggregate(units, config, require_bilateral=False):
    available=[u for u in units if not u['exclusion_reason']]
    classified=[u for u in available if u['classification_status']=='rule_supported']
    n=len(available);k=len(classified);unknown=n-k
    total=sum(u['intensity'] for u in classified)
    mean=total/k if k else None
    share=k/n if n else None
    countries=sorted({u['country'] for u in classified})
    if not n:status='no_data'
    elif not k:status='no_classified_units'
    elif k<config['min_classified_units']:status='low_classified_volume'
    elif share<config['min_classified_share']:status='high_abstention'
    elif require_bilateral and len(countries)<2:status='one_sided_coverage'
    else:status='operational_support_not_validated_accuracy'
    return {'available_units':n,'classified_units':k,'confrontational_signals':sum(u['direction']=='confrontational' for u in classified),
        'neutral_signals':sum(u['direction']=='neutral' for u in classified),'cooperative_signals':sum(u['direction']=='cooperative' for u in classified),
        'intensity_distribution':{str(i):sum(u['intensity']==i for u in classified) for i in range(4)},
        'undetermined_units':unknown,'undetermined_share':unknown/n if n else None,'classified_share':share,
        'observed_intensity_0_3':mean,
        'dri_v02':mean,
        'coverage_supported':status=='operational_support_not_validated_accuracy',
        'measurement_status':status,'classified_countries':countries,
        'abstention_only_lower_bound':total/n if n else None,
        'abstention_only_upper_bound':(total+3*unknown)/n if n else None,
        'source_composition':dict(sorted(Counter(u['source_id'] for u in available).items())),
        'classified_source_composition':dict(sorted(Counter(u['source_id'] for u in classified).items())),
        'institution_composition':dict(sorted(Counter(u['institution'] for u in available).items())),
        'classified_institution_composition':dict(sorted(Counter(u['institution'] for u in classified).items())),
        'institution_type_composition':dict(sorted(Counter(u.get('institution_type','unknown') for u in available).items())),
        'classified_institution_type_composition':dict(sorted(Counter(u.get('institution_type','unknown') for u in classified).items())),
        'language_composition':dict(sorted(Counter(u['language'] for u in available).items())),
        'theme_composition':dict(sorted(Counter(u['selection_theme'] for u in available).items()))}

def monthly_rows(units,config):
    rows=[]
    source_ids=sorted({u['source_id'] for u in units if not u['exclusion_reason']})
    for scope in ('pooled_sample','ROK','JPN'):
        for month in calendar_months(config['period_start'],config['period_end']):
            us=[u for u in units if u['date'] and u['date'][:7]==month and (scope=='pooled_sample' or u['country']==scope)]
            row={'scope':scope,'month':month,**aggregate(us,config,scope=='pooled_sample')}
            sensitivity={}
            for source in source_ids:
                reduced=aggregate([u for u in us if u['source_id']!=source],config,scope=='pooled_sample')
                sensitivity['without_source:'+source]={k:reduced[k] for k in ('available_units','classified_units','observed_intensity_0_3','measurement_status')}
            for theme in ('historical_disputes','territorial_disputes','security'):
                reduced=aggregate([u for u in us if u['selection_theme']!=theme],config,scope=='pooled_sample')
                sensitivity['without_selection_theme:'+theme]={k:reduced[k] for k in ('available_units','classified_units','observed_intensity_0_3','measurement_status')}
            for institution in ('parliament','foreign_ministry','government','head_of_state_administration','unknown'):
                reduced=aggregate([u for u in us if u.get('institution_type','unknown')!=institution],config,scope=='pooled_sample')
                sensitivity['without_institution_type:'+institution]={k:reduced[k] for k in ('available_units','classified_units','observed_intensity_0_3','measurement_status')}
            row['sensitivity']=sensitivity;rows.append(row)
    return rows

def report_context_links(db,units):
    """Candidate context only. A shared date/theme is NOT proof of one event."""
    docs=[]
    for r in db.execute("SELECT id,url,published_date,metadata_json FROM documents WHERE source='mofa_kr'"):
        m=json.loads(r['metadata_json'])
        if m.get('text_completeness')=='complete_published_body' and m.get('observation_type')=='official_activity_report':
            docs.append(dict(r)|{'theme':m.get('theme')})
    for u in units:
        exact=[d['id'] for d in docs if d['url'] in u['source_urls']]
        candidates=[d['id'] for d in docs if d['published_date']==u['date'] and d['theme']==u['selection_theme'] and d['id'] not in exact]
        u['context_report_document_ids']=exact
        u['possible_context_report_document_ids']=candidates
        u['context_report_status']='same_publication_only' if exact else 'date_theme_candidate_requires_event_verification' if candidates else 'no_verified_context_link'
        u['context_reports_used_in_score']=False
    return {'full_activity_reports':len(docs),
        'reports_with_same_publication_link':len({d for u in units for d in u['context_report_document_ids']}),
        'reports_with_date_theme_candidate_link':len({d for u in units for d in u['possible_context_report_document_ids']}),
        'units_with_possible_context':sum(bool(u['possible_context_report_document_ids']) for u in units),
        'reports_added_as_signals':0,'context_body_used_for_automatic_scoring':False}

def calculate_v02(db_path,config,rules):
    units,snapshot=load_sample(db_path)
    db=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('BEGIN')
    themes={r['id']:r['theme'] for r in db.execute('SELECT id,theme FROM statements')}
    offices={r['id']:r['speaker_office'] for r in db.execute('SELECT id,speaker_office FROM statements')}
    institution_types={r['statement_id']:r['institution_type'] for r in db.execute('SELECT statement_id,institution_type FROM statement_metadata')}
    runs=defaultdict(set)
    selection_rows=[dict(r) for r in db.execute('SELECT i.document_id,r.run_key FROM collection_items i JOIN collection_runs r ON r.id=i.run_id WHERE i.document_id IS NOT NULL ORDER BY i.document_id,r.run_key')]
    for r in selection_rows:
        runs[r['document_id']].add(r['run_key'])
    classifier=ContextClassifier(rules)
    private_fragments={}
    for u in units:
        u['selection_theme']=themes[u['statement_ids'][0]] or 'unknown'
        u['institution_type']=institution_types.get(u['statement_ids'][0]) or 'unknown'
        u['speaker_office']=offices[u['statement_ids'][0]]
        u['collection_run_keys']=sorted({key for d in u['document_ids'] for key in runs[d]})
        u.update(classifier.classify(u))
        private_fragments[u['unit_id']]=u.pop('fragments')
    context=report_context_links(db,units);db.close()
    monthly=monthly_rows(units,config)
    included=[u for u in units if not u['exclusion_reason']]
    classified=[u for u in included if u['classification_status']=='rule_supported']
    summary={**snapshot,'model':'DRI v0.2','available_units':len(included),'classified_units':len(classified),
        'selection_runs_sha256':digest(selection_rows),
        'automatically_classified_share':len(classified)/len(included) if included else None,
        'full_units':sum(u['component_role']=='main' for u in included),
        'partial_units':sum(u['component_role']!='main' for u in included),
        'classified_full_units':sum(u['component_role']=='main' for u in classified),
        'classified_partial_units':sum(u['component_role']!='main' for u in classified),
        'needs_review_units':len(included)-len(classified),'excluded_units':len(units)-len(included),
        'directions':dict(Counter(u['direction'] for u in included)),
        'intensities':dict(Counter(str(u['intensity']) for u in classified)),
        'review_reasons':dict(Counter(u['classification_reason'] for u in included if u['classification_status']=='needs_review')),
        'supported_months_by_scope':{scope:sum(r['coverage_supported'] for r in monthly if r['scope']==scope) for scope in ('pooled_sample','ROK','JPN')},
        'observed_months_by_scope':{scope:sum(r['dri_v02'] is not None for r in monthly if r['scope']==scope) for scope in ('pooled_sample','ROK','JPN')},
        'context_reports':context,'expert_accuracy_established':False,'probability_model':False}
    return {'units':units,'monthly':monthly,'summary':summary},private_fragments

def compare_v01(result,v01_units,v01_monthly,config):
    fields=('country','language','source_type','source_id','text_form','version')
    byunit={u['unit_id']:u for u in v01_units};v2={u['unit_id']:u for u in result['units']}
    comparisons=[]
    for old in v01_monthly:
        ids=[i for i,u in byunit.items() if not u['exclusion_reason'] and u['date'][:7]==old['month']
             and '|'.join(u[k] for k in fields)==old['component_id']]
        known=[v2[i] for i in ids if v2[i]['classification_status']=='rule_supported']
        coverage=aggregate([v2[i] for i in ids],config)
        comparisons.append({'component_id':old['component_id'],'month':old['month'],'available_units':len(ids),
            'v01_rate_per_1000':old['raw_rate_per_1000'],'v01_supported':old['status']=='supported',
            'v02_classified_units':len(known),'v02_observed_intensity_0_3':sum(u['intensity'] for u in known)/len(known) if known else None,
            'v02_confrontational_units':sum(u['direction']=='confrontational' for u in known),
            'v02_undetermined_units':len(ids)-len(known),
            'v02_classified_share':coverage['classified_share'],'v02_coverage_supported':coverage['coverage_supported'],
            'v02_measurement_status':coverage['measurement_status']})
    return comparisons
