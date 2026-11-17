"""DRI v0.1 components. One rate definition, no pooled score or probabilities."""
from collections import Counter,defaultdict
from dataclasses import asdict
from statistics import median
import json
import math
from .analytical_sample import load_sample,digest
from .tokenization import Segmenter,prepare
from .rhetoric import Matcher

def month_number(month):
    year,m=map(int,month.split('-'));return year*12+m-1

def calendar_months(start,end):
    return [f'{n//12:04}-{n%12+1:02}' for n in range(month_number(start),month_number(end)+1)]

def robust_background(current,history,config):
    """Only earlier supported months in a fixed calendar window. No zero filling."""
    now=month_number(current['month'])
    eligible=[h['raw_rate_per_1000'] for h in history
        if h['status']=='supported' and 0<now-month_number(h['month'])<=config['background_window_months']]
    out={'background_months':len(eligible),'background_median':None,'background_mad':None,
         'robust_deviation':None,'anomaly_flag':None,'background_status':'insufficient_history'}
    if current['status']!='supported':out['background_status']='current_month_unsupported';return out
    if len(eligible)<config['min_background_months']:return out
    center=median(eligible);mad=median(abs(x-center) for x in eligible)
    out.update(background_median=center,background_mad=mad)
    if sum(x>0 for x in eligible)<config['min_background_nonzero']:
        out['background_status']='sparse_nonzero_history';return out
    if mad<=1e-12:out['background_status']='zero_mad_no_standardization';return out
    dev=(current['raw_rate_per_1000']-center)/(1.4826*mad)
    out.update(robust_deviation=dev,anomaly_flag=dev>=config['anomaly_robust_deviation_threshold'],background_status='available')
    return out

def monthly_components(units,config):
    strata={};buckets=defaultdict(list)
    fields=('country','language','source_type','source_id','text_form','version')
    for unit in units:
        if unit['exclusion_reason']:continue
        key=tuple(unit[k] for k in fields);component='|'.join(key)
        strata[component]={**dict(zip(fields,key)),'component_role':unit['component_role']}
        buckets[(component,unit['date'][:7])].append(unit)
    result=[]
    for component,metadata in sorted(strata.items()):
        history=[]
        for month in calendar_months(config['period_start'],config['period_end']):
            sample=buckets.get((component,month),[]);n=len(sample)
            tokens=sum(u['token_count'] for u in sample);hits=sum(u['expression_count'] for u in sample)
            suppressed=sum(u['suppressed_candidates'] for u in sample)
            status='no_data' if n==0 else ('supported' if n>=config['min_month_units'] and tokens>=config['min_month_tokens'] else 'insufficient_volume')
            rate=1000*hits/tokens if tokens else None
            row={**metadata,'component_id':component,'month':month,'status':status,
                'unit_count':n,'statement_records':sum(len(u['statement_ids']) for u in sample),
                'token_count':tokens,'expression_count':hits if n else None,
                'suppressed_candidates':suppressed if n else None,'raw_rate_per_1000':rate,
                'dri_component':rate if status=='supported' else None,
                'measurement_state':'no_texts' if not n else ('observed_positive' if hits else ('observed_lexicon_zero_with_suppressed_candidates' if suppressed else 'observed_lexicon_zero')),
                'publication_date_units':sum(u['date_basis']!='speech_date' for u in sample)}
            row.update(robust_background(row,history,config));history.append(row);result.append(row)
    return result

def calculate(db_path,config,lexicon):
    units,snapshot=load_sample(db_path);segmenter=Segmenter();matcher=Matcher(lexicon,segmenter)
    matches=[]
    for unit in units:
        token_count=0;ledger=[];fragment_provenance=[]
        for index,fragment in enumerate(unit['fragments']):
            if unit['language'] not in {'en','ko','ja'}:continue
            text=prepare(fragment['text'])
            if unit['exclusion_reason']:
                tokens=segmenter.tokenize(text,unit['language']);found=[]
            else:tokens,found=matcher.match(text,unit['language'],unit['target_country'])
            token_count+=len(tokens);ledger.append([asdict(t) for t in tokens])
            fragment_provenance.append({'fragment_index':index,'ref':fragment['ref'],'analysis_text_sha256':digest(text),'tokens':len(tokens)})
            for m in found:
                record={**m,'unit_id':unit['unit_id'],'fragment_index':index,'language':unit['language'],
                    'source_ref':fragment['ref'],'input_text_sha256':unit['input_text_sha256']}
                record['match_id']=digest({k:record[k] for k in ('unit_id','fragment_index','expression_id','char_start','char_end','input_text_sha256')})[:24]
                matches.append(record)
        unit['token_count']=token_count
        if token_count<config['min_unit_tokens']:
            unit['exclusion_reason']=unit['exclusion_reason'] or 'too_few_tokens_for_attributed_context'
            matches=[m for m in matches if m['unit_id']!=unit['unit_id']]
        owned=[m for m in matches if m['unit_id']==unit['unit_id']]
        unit['expression_count']=sum(m['decision']=='counted' for m in owned)
        unit['suppressed_candidates']=sum(m['decision']=='suppressed' for m in owned)
        unit['token_ledger_sha256']=digest(ledger);unit['fragment_provenance']=fragment_provenance
        unit.pop('fragments')
    monthly=monthly_components(units,config)
    included=[u for u in units if not u['exclusion_reason']]
    lengths=[]
    groups=defaultdict(list)
    for u in included:groups[(u['country'],u['language'],u['source_id'],u['text_form'])].append(u['token_count'])
    for key,values in sorted(groups.items()):
        values=sorted(values)
        lengths.append(dict(zip(('country','language','source_id','text_form'),key))|
            {'units':len(values),'min_tokens':values[0],'median_tokens':median(values),'max_tokens':values[-1]})
    years=[]
    for year in range(2015,2027):
        for country in ('ROK','JPN'):
            group=[u for u in included if u['country']==country and u['date'].startswith(str(year))]
            years.append({'year':year,'country':country,'included':len(group),
                'main_complete_units':sum(u['component_role']=='main' for u in group),
                'diagnostic_partial_units':sum(u['component_role']!='main' for u in group)})
    japanese=[u for u in included if u['country']=='JPN' and u['text_form'] in {'sentence_excerpt','legacy_excerpt'}]
    summary={**snapshot,'included_units':len(included),
        'included_statement_records':sum(len(u['statement_ids']) for u in included),
        'main_complete_units':sum(u['component_role']=='main' for u in included),
        'diagnostic_partial_units':sum(u['component_role']!='main' for u in included),
        'excluded_statement_records':sum(len(u['statement_ids']) for u in units if u['exclusion_reason']),
        'excluded_reasons':dict(Counter(u['exclusion_reason'] for u in units if u['exclusion_reason'])),
        'component_count':len({r['component_id'] for r in monthly}),
        'monthly_states':dict(Counter(r['status'] for r in monthly)),
        'supported_main_component_months':sum(r['status']=='supported' and r['component_role']=='main' for r in monthly),
        'robust_background_states':dict(Counter(r['background_status'] for r in monthly)),
        'counted_expressions':sum(m['decision']=='counted' for m in matches),
        'suppression_reasons':dict(Counter(m['reason'] for m in matches if m['decision']=='suppressed')),
        'lengths':lengths,'coverage_by_year':years,
        'short_japanese_sensitivity':{'removed_units':len(japanese),'remaining_japanese_units':sum(u['country']=='JPN' for u in included)-len(japanese),
            'removed_tokens':sum(u['token_count'] for u in japanese),'removed_counted_expressions':sum(u['expression_count'] for u in japanese),
            'effect_on_unified_dri':None,'reason':'No comparable full Japanese speeches remain; pooled index is undefined, not zero.'},
        'unified_dri':None,'unified_dri_status':'not_identifiable_from_noncomparable_and_sparse_components',
        'scale':config['scale'],'probability_model':False}
    return {'units':units,'matches':sorted(matches,key=lambda m:(m['unit_id'],m['fragment_index'],m['char_start'])),
            'monthly':monthly,'summary':summary}
