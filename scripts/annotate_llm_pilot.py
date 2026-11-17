"""Local I/O and aggregation only; semantic labels are supplied by the session model."""
import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dri.analytical_sample import load_sample

OUT = ROOT / 'data/dri_llm_annotations.jsonl'
DB = ROOT / 'data/dri.sqlite3'
FROZEN_CORPUS = {
    'core_input_sha256': '7d693db0dd6f705d2bf8e24be733afdb2a487e197ddefa73a2c111f352349f87',
    'qa_sha256': 'b38065d9a670fe7157cd8a4c12c953711a75cd0efa4a65c808daa8f103dbcac8',
    'completeness_review_sha256': 'f0d0538fb4f9439f5aa48d4e514d092a6acc9a43d13c3a00e4141170d4889616',
    'assembly_extraction_sha256': '0a136c49e7b991f5a62c05f99db27a0530ad29f44ba7afe2de12f975c6985135',
}
FIELDS = ['unit_id', 'direction', 'confrontation_intensity', 'cooperation_present',
          'target_country', 'position_ownership', 'confidence', 'reason_ru', 'summary_ru']


def data():
    units, snapshot = load_sample(DB, frozen=True)
    assert all(snapshot[k] == v for k, v in FROZEN_CORPUS.items()), 'Source corpus changed; review checkpoint first'
    units = {u['unit_id']: u for u in units if not u['exclusion_reason']}
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as conn:
        types=dict(conn.execute('SELECT statement_id,institution_type FROM statement_metadata'))
    for u in units.values():
        u['institution_type']=';'.join(sorted({types.get(i) or 'unknown' for i in u['statement_ids']}))
    # Only identity/hash fields are read from the old predictions, never their labels.
    old = {r['unit_id']: r['input_text_sha256'] for r in
           map(json.loads, (ROOT/'data/dri_v02_units.jsonl').read_text(encoding='utf-8').splitlines())}
    assert all(old[i] == u['input_text_sha256'] for i, u in units.items())
    rows = [json.loads(s) for s in OUT.read_text(encoding='utf-8').splitlines()] if OUT.exists() else []
    assert len({r['unit_id'] for r in rows}) == len(rows)
    for r in rows:
        validate(r, units)
    return units, rows


def validate(r, units):
    u = units[r['unit_id']]
    assert r['input_text_sha256'] == u['input_text_sha256']
    assert r['statement_ids'] == u['statement_ids']
    assert r['direction'] in {'confrontational','cooperative','mixed','neutral','irrelevant','uncertain'}
    n = r['confrontation_intensity']
    if r['direction'] == 'uncertain': assert n is None
    elif r['direction'] in {'confrontational','mixed'}: assert type(n) is int and n in (1,2,3)
    else: assert type(n) is int and n == 0
    assert type(r['cooperation_present']) is bool
    assert r['direction'] not in {'cooperative','mixed'} or r['cooperation_present']
    assert r['target_country'] in {'ROK','JPN','DPRK','multiple','unknown',None}
    assert r['position_ownership'] in {'own','reported','quoted','historical','unclear','mixed'}
    assert r['confidence'] in {'high','medium','low'}
    assert r['reason_ru'].strip() and r['summary_ru'].strip()
    assert r['annotation_method'] == 'codex_contextual_model'
    assert r['annotation_version'] == 'DRI-LLM-pilot-1'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['read','save','aggregate'])
    p.add_argument('--count', type=int, default=60)
    args = p.parse_args()
    units, rows = data()
    if args.action == 'read':
        done = {r['unit_id'] for r in rows}
        with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as conn:
            for u in [u for i,u in units.items() if i not in done][:args.count]:
                context=[]
                for doc_id in u['document_ids']:
                    body=conn.execute('SELECT text FROM documents WHERE id=?',(doc_id,)).fetchone()[0]
                    if len(body)>sum(len(f['text']) for f in u['fragments'])+10:
                        context.append({'document_id':doc_id,'text':body,
                                        'note':'Linked document context; do not attribute other speakers to this unit'})
                print(json.dumps({**{k:u[k] for k in ['unit_id','date','country','language','speaker_name','institution','text_form','document_ids']},
                                  'text':[f['text'] for f in u['fragments']], 'linked_context':context}, ensure_ascii=False))
    elif args.action == 'save':
        batch = json.load(sys.stdin)
        done = {r['unit_id']:r for r in rows}
        for values in batch:
            assert len(values) == len(FIELDS)
            r = dict(zip(FIELDS, values)); u = units[r['unit_id']]
            r.update(statement_ids=u['statement_ids'], input_text_sha256=u['input_text_sha256'],
                     annotation_method='codex_contextual_model', annotation_version='DRI-LLM-pilot-1',
                     model_id=None, model_identity_note='Codex session; exact backend model identifier unavailable')
            validate(r, units)
            if r['unit_id'] in done:
                assert done[r['unit_id']] == r, 'Conflicting repeat annotation'
            else:
                rows.append(r); done[r['unit_id']] = r
        body=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in sorted(rows,key=lambda r:r['unit_id']))
        tmp=OUT.with_suffix('.jsonl.tmp'); tmp.write_text(body,encoding='utf-8');tmp.replace(OUT)
        print(json.dumps({'saved':len(rows),'remaining':len(units)-len(rows),'next_unit_id':next((i for i in units if i not in done),None)}))
    else:
        aggregate(units, rows)


def aggregate(units, annotations):
    database_sha = hashlib.sha256(DB.read_bytes()).hexdigest()
    os.environ['MPLCONFIGDIR']=str(ROOT/'.venv/matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    lookup={r['unit_id']:r for r in annotations}
    result=[]
    for y in range(2015,2027):
        for m in range(1,13):
            month=f'{y:04}-{m:02}'
            us=[u for u in units.values() if u['date'][:7]==month]
            rs=[lookup[u['unit_id']] for u in us if u['unit_id'] in lookup]
            scored=[r for r in rs if r['direction'] not in {'uncertain','irrelevant'}]
            def count(field, selected):return json.dumps(dict(sorted(Counter(u[field] or 'unknown' for u in selected).items())),ensure_ascii=False)
            annotated=[u for u in us if u['unit_id'] in lookup]
            row={'month':month,'source_units':len(us),'annotated_units':len(rs),'scored_units':len(scored),
                 'annotation_share':len(rs)/len(us) if us else None,
                 'low_volume':0<len(scored)<5,
                 'confrontational_signals':sum(r['direction']=='confrontational' for r in rs),
                 'mixed_signals':sum(r['direction']=='mixed' for r in rs),
                 'cooperative_signals':sum(r['direction']=='cooperative' for r in rs),
                 'conflict_including_mixed':sum(r['direction'] in {'confrontational','mixed'} for r in rs),
                 'mean_confrontation_intensity':sum(r['confrontation_intensity'] for r in scored)/len(scored) if scored else None,
                 'uncertain_units':sum(r['direction']=='uncertain' for r in rs),
                 'irrelevant_units':sum(r['direction']=='irrelevant' for r in rs),
                 'uncertain_share':sum(r['direction']=='uncertain' for r in rs)/len(rs) if rs else None,
                 'irrelevant_share':sum(r['direction']=='irrelevant' for r in rs)/len(rs) if rs else None,
                 'source_country_composition':count('country',us),'annotated_country_composition':count('country',annotated),
                 'source_institution_composition':count('institution',us),'annotated_institution_composition':count('institution',annotated),
                 'source_institution_type_composition':count('institution_type',us),'annotated_institution_type_composition':count('institution_type',annotated),
                 'source_id_composition':count('source_id',annotated),
                 'status':'outside_input_period' if month>'2026-10' else 'no_source_data' if not us else 'not_annotated' if not rs else 'completed_annotation' if len(rs)==len(us) else 'preliminary_partial_corpus',
                 'country_results':json.dumps({c:{'annotated':sum(units[r['unit_id']]['country']==c for r in rs),
                     'source_units':sum(u['country']==c for u in us),
                     'scored_units':sum(units[r['unit_id']]['country']==c for r in scored),
                     'low_volume':0<sum(units[r['unit_id']]['country']==c for r in scored)<5,
                     'categories':dict(Counter(r['direction'] for r in rs if units[r['unit_id']]['country']==c)),
                     'mean_intensity':(sum(r['confrontation_intensity'] for r in scored if units[r['unit_id']]['country']==c)/sum(units[r['unit_id']]['country']==c for r in scored)) if any(units[r['unit_id']]['country']==c for r in scored) else None}
                     for c in ['ROK','JPN']},ensure_ascii=False)}
            result.append(row)
    stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    target=ROOT/'data/dri_llm_monthly.csv';target.write_text(stream.getvalue(),encoding='utf-8-sig',newline='')
    fig,(ax,bx)=plt.subplots(2,1,figsize=(13,7),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    ys=[r['mean_confrontation_intensity'] if r['mean_confrontation_intensity'] is not None else float('nan') for r in result]
    ax.plot(range(144),ys,marker='o',markersize=3,linewidth=.8)
    ax.set_ylim(-.1,3.1);ax.set_ylabel('Mean intensity (0–3)');ax.grid(alpha=.25)
    ax.set_title(f'DRI LLM pilot — experimental, unvalidated: {len(annotations)}/{len(units)} annotated')
    low=[i for i,r in enumerate(result) if r['low_volume']]
    ax.scatter(low,[ys[i] for i in low],facecolors='none',edgecolors='#dc2626',s=45,label='Only 1–4 scored units')
    ax.legend(loc='upper right')
    rok=[json.loads(r['country_results'])['ROK']['annotated'] for r in result]
    jpn=[json.loads(r['country_results'])['JPN']['annotated'] for r in result]
    bx.bar(range(144),rok,label='ROK annotated',color='#d97706')
    bx.bar(range(144),jpn,bottom=rok,label='JPN annotated',color='#2563eb')
    bx.set_ylabel('Units');bx.legend();bx.set_xticks(list(range(0,144,12)),list(range(2015,2027)))
    fig.text(.05,.02,'Selected corpus, not representative. Uncertain/irrelevant excluded from mean; missing ≠ zero. No institutional weights.',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(ROOT/'docs/DRI_llm_pilot.png',dpi=150);plt.close(fig)
    assert hashlib.sha256(DB.read_bytes()).hexdigest()==database_sha, 'Database changed during aggregation'
    summary={'annotated':len(annotations),'remaining':len(units)-len(annotations),
             'categories':dict(Counter(r['direction'] for r in annotations)),
             'months_with_annotations':sum(r['annotated_units']>0 for r in result),
             'months_with_numeric_mean':sum(r['mean_confrontation_intensity'] is not None for r in result),
             'by_language':{},'by_country':{},'by_institution':{},'by_institution_type':{},'database_sha256':database_sha}
    for name,field in [('by_language','language'),('by_country','country'),('by_institution','institution'),('by_institution_type','institution_type')]:
        for value in sorted({u[field] or 'unknown' for u in units.values()}):
            selected=[r for r in annotations if (units[r['unit_id']][field] or 'unknown')==value]
            summary[name][value]=dict(Counter(r['direction'] for r in selected))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
