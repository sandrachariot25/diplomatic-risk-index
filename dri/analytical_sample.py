"""Read-only selection of dated speech/statement units, never document signals."""
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date
from .identity import normalized
from .paths import ROOT
from .tokenization import prepare
from .connectors.assembly_pdf import floor_episodes
from .connectors.korea import KoreaMOFA

def verified_completeness(document, record, root=ROOT):
    """Fail closed: a legacy body needs exact retained HTML evidence, not length."""
    if (document['source']!='mofa_kr' or document['content_policy']!='legacy_unreviewed'
        or document['id']!=record['document_id'] or document['url']!=record['url']
        or document['language']!=record['language'] or document['published_date']!=record['published_date']
        or record['text_completeness']!='complete_published_body'
        or record['observation_type']!='official_institutional_statement'
        or record['usage']!='internal_research_only_no_publication_permission_inferred'):
        raise ValueError('Legacy completeness identity/policy mismatch')
    path=(root/'data'/record['raw_path']).resolve()
    if not path.is_relative_to((root/'data/raw').resolve()):raise ValueError('Raw evidence outside data/raw')
    body=path.read_bytes()
    if (hashlib.sha256(body).hexdigest()!=record['raw_sha256']
        or hashlib.sha256(document['text'].encode()).hexdigest()!=record['body_sha256']):
        raise ValueError('Legacy completeness evidence hash mismatch')
    parsed=KoreaMOFA().parse(body.decode('utf-8'),document['url'])
    title=parsed.title.casefold()
    if (parsed.text!=document['text'] or parsed.title!=document['metadata']['title']
        or parsed.published_date!=document['published_date']
        or not ('spokesperson' in title and ('commentary' in title or 'statement' in title))):
        raise ValueError('Legacy completeness source body/attribution mismatch')
    return {**document,'metadata':{**document['metadata'],
        'text_completeness':record['text_completeness'],'observation_type':record['observation_type'],
        'completeness_evidence':'sealed_retained_html_exact_reparse_internal_only'}}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def distinct_fragments(fragments):
    """Union overlapping source intervals; different reviewed turns remain distinct."""
    out=[]
    for f in sorted(fragments,key=lambda f:(-len(prepare(f['text'])),str(f['ref']))):
        text=prepare(f['text']);scope=f.get('scope','event')
        if not text:continue
        if any(g.get('scope','event')==scope and text in prepare(g['text']) for g in out):continue
        # Only join partial overlap if both intervals are proven in the same source.
        merged=False
        for g in out:
            if (g.get('scope','event')!=scope or f.get('source_interval') is None
                or g.get('source_interval') is None or f['ref'].get('document_id')!=g['ref'].get('document_id')):continue
            a,b=f['source_interval'];c,d=g['source_interval']
            if a<d and c<b:
                lo,hi=min(a,c),max(b,d)
                source=f.get('_source')
                if source is not None:g['text']=source[lo:hi];g['source_interval']=[lo,hi];merged=True;break
        if not merged:out.append({**f,'text':text})
    # A newly merged interval may bridge two formerly disjoint intervals.
    # Close that union transitively rather than counting the bridge twice.
    changed=True
    while changed:
        changed=False
        for i,g in enumerate(out):
            for j in range(i+1,len(out)):
                f=out[j]
                if (g.get('scope','event')!=f.get('scope','event')
                    or g.get('source_interval') is None or f.get('source_interval') is None
                    or g['ref'].get('document_id')!=f['ref'].get('document_id')):continue
                a,b=g['source_interval'];c,d=f['source_interval']
                if a<d and c<b and g.get('_source') is not None:
                    lo,hi=min(a,c),max(b,d);g['text']=g['_source'][lo:hi]
                    g['source_interval']=[lo,hi];out.pop(j);changed=True;break
            if changed:break
    return sorted(out,key=lambda f:(f['ref'].get('document_id',0),f['ref'].get('turn_id',0),f['ref'].get('quote_id',0),f['ref'].get('source_start',0)))

def author_blocks(text):
    """Contiguous speech blocks; stage directions never enter denominator or features."""
    pattern=r'\((?:장내|영상자료|자료를|발언시간|마이크|｢)[\s\S]*?\)'
    start=0;blocks=[]
    for m in re.finditer(pattern,text):
        if text[start:m.start()].strip():blocks.append((start,m.start(),text[start:m.start()]))
        start=m.end()
    if text[start:].strip():blocks.append((start,len(text),text[start:]))
    return blocks

def assemble_unit(statements,documents,quotes,quote_sources,extractions,review):
    """Pure selector; one unit can have many source documents but one lexical stream."""
    s=statements[0];sid=s['id'];all_docs=sorted(documents,key=lambda d:d['id'])
    # Prefer directly published primary evidence for one unit, not a weighted mix
    # of the same words in official and journalistic publications.
    primary=[d for d in all_docs if d['source_type']=='primary' and d['text'].strip()]
    docs=primary or all_docs
    language=s.get('original_language')
    available={q['published_language'] for q in quotes if q['text'].strip()}
    if language not in available:language=next(iter(sorted(available)),None)
    result={'unit_id':sid,'statement_ids':[s['id'] for s in statements],
        'event_key':s['event_key'],'country':s['country'],'target_country':s['target_country'],
        'speaker_name':s['speaker_name'],'institution':s['institution'],'language':language,
        'document_ids':[d['id'] for d in all_docs],'quote_ids':[q['id'] for q in quotes],
        'source_urls':sorted({d['url'] for d in all_docs}),'fragments':[],
        'date':s.get('spoken_date'),'date_basis':'speech_date','exclusion_reason':None}
    if not result['date']:
        # Publication is a legitimate date for a standalone institutional statement,
        # never a substitute for an unknown parliamentary speech date.
        if s['event_key'].startswith(('official:',)) and s.get('published_date'):
            result.update(date=s['published_date'],date_basis='publication_date_of_official_statement')
        else:result['exclusion_reason']='missing_reliable_statement_date'
    if language not in {'en','ko','ja'}:result['exclusion_reason']=result['exclusion_reason'] or 'unknown_or_unsupported_published_language'
    source=docs[0]['source'] if docs else 'unknown'
    result.update(source_id=source,source_type=docs[0]['source_type'] if docs else 'unknown')
    if docs and all(d['source_type']=='secondary' for d in docs) and not any(q.get('verification_status') in {'verified','source_text_verified'} for q in quotes):
        result['exclusion_reason']='unverified_secondary_attribution'
    if result['exclusion_reason']:return result
    if source=='assembly_kr':
        doc=docs[0];data=extractions.get(doc['url'])
        if not data:result['exclusion_reason']='missing_reviewed_parliamentary_text';return result
        episode=re.search(r':floor:([^:]+):speaker:',s['event_key'])
        if not episode:result['exclusion_reason']='missing_floor_identity';return result
        episode=episode[1];episodes=floor_episodes(data['turns']);byid={t['ordinal']:t for t in data['turns']}
        ids=set()
        for q in quotes:
            for link in quote_sources.get(q['id'],[]):
                try:ids.add(json.loads(link['evidence_locator'])['turn'])
                except (ValueError,KeyError,TypeError):pass
        for ordinal in sorted(ids):
            t=byid.get(ordinal);r=review.get((doc['url'],ordinal))
            if (not t or not r or r['status']!='pass' or not all(r['checks'].values())
                or r['text_sha256']!=hashlib.sha256(t['text'].encode()).hexdigest()
                or r['pdf_sha256']!=data.get('pdf_sha256')):
                result['exclusion_reason']='parliamentary_review_evidence_mismatch';return result
            for start,end,text in author_blocks(t['text']):
                result['fragments'].append({'text':text,'scope':f'turn:{ordinal}:{start}',
                    'ref':{'document_id':doc['id'],'turn_id':ordinal,'source_start':start,'source_end':end}})
        all_ids={t['ordinal'] for t in data['turns'] if episodes[t['ordinal']]==episode
                 and t['speaker_name']==s['speaker_name'] and t['role']==s['speaker_office']}
        result['text_form']='complete_speech' if ids and ids==all_ids else 'selected_turns_partial_floor'
        result['assembly_turn_ids']=sorted(ids);result['all_floor_author_turn_ids']=sorted(all_ids)
    else:
        complete=[d for d in docs if d['metadata'].get('text_completeness')=='complete_published_body'
                  and d['metadata'].get('observation_type') in {'official_speech','official_written_briefing','official_institutional_statement'}
                  and d['language']==language and d['source_type']=='primary']
        if complete:
            doc=sorted(complete,key=lambda d:(-len(d['text']),d['id']))[0]
            result['fragments']=[{'text':doc['text'],'ref':{'document_id':doc['id']},'scope':'complete_statement'}]
            result['text_form']='complete_speech' if doc['metadata']['observation_type']=='official_speech' else 'complete_official_statement'
        else:
            for q in quotes:
                if q['published_language']!=language:continue
                links=sorted(quote_sources.get(q['id'],[]),key=lambda l:l['document_id'])
                links=[l for l in links if l['document_id'] in {d['id'] for d in docs}]
                if not links:continue
                doc=next((d for d in docs if links and d['id']==links[0]['document_id']),docs[0] if docs else None)
                if doc is None:continue
                text=prepare(q['text']);body=prepare(doc['text']);pos=body.find(text)
                f={'text':text,'ref':{'document_id':doc['id'],'quote_id':q['id']},'scope':'event'}
                if pos>=0 and body.count(text)==1:f.update(source_interval=[pos,pos+len(text)],_source=body)
                result['fragments'].append(f)
            m=docs[0]['metadata'] if docs else {}
            if source=='kokkai_jp':
                result['text_form']='sentence_excerpt' if m.get('text_completeness')=='complete_sentence_partial_speech' else 'legacy_excerpt'
            else:
                result['text_form']='legacy_quote_unknown_completeness' if any(d['content_policy']=='legacy_unreviewed' for d in docs) else 'short_quote_fragment'
    result['fragments']=distinct_fragments(result['fragments'])
    result['component_role']='main' if result['text_form'] in {'complete_speech','complete_official_statement'} else 'diagnostic_partial_text'
    result['version']='unofficial_translation' if any(d['metadata'].get('translation_note') for d in docs) else ('published_original_unknown' if not s.get('original_language') else 'original')
    return result

def load_sample(db_path, *, frozen=False):
    db=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    db.execute('BEGIN')
    limits = json.loads((ROOT/'config/dri_frozen_row_limits.json').read_text()) if frozen else {}
    def rows(table):
        if frozen:
            return [dict(r) for r in db.execute('SELECT * FROM '+table+' WHERE rowid<=? ORDER BY rowid', (limits[table],))]
        return [dict(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
    tables={t:rows(t) for t in ('statements','documents','quotes','statement_sources','quote_sources','statement_metadata','statement_assessments','duplicate_candidates','sources')}
    input_sha=digest({t:[{k:v for k,v in r.items() if k not in {'created_at','updated_at'}} for r in rs] for t,rs in tables.items()})
    documents={d['id']:{**d,'metadata':json.loads(d['metadata_json'])} for d in tables['documents']}
    completeness_path=ROOT/'config/dri_v01_completeness.json'
    completeness_json=json.loads(completeness_path.read_text(encoding='utf-8'))
    for record in completeness_json['records']:
        documents[record['document_id']]=verified_completeness(documents[record['document_id']],record)
    links=defaultdict(set)
    for r in tables['statement_sources']:links[r['statement_id']].add(r['document_id'])
    qlinks=defaultdict(list)
    for r in tables['quote_sources']:qlinks[r['quote_id']].append(r)
    quotes=defaultdict(list)
    for q in tables['quotes']:quotes[q['statement_id']].append(q)
    assessments={a['statement_id']:a for a in tables['statement_assessments']}
    extractions={}
    for row in db.execute("SELECT url,result FROM source_checks WHERE source_id='assembly_kr' AND result LIKE '%\"internal_extraction\"%' ORDER BY id"):
        obj=json.loads(row['result']).get('internal_extraction')
        if obj and obj.get('version')=='assembly-pdf-columns-v4':extractions[row['url']]=obj
    review_path=ROOT/'data/assembly_pdf_review.json';review_json=json.loads(review_path.read_text(encoding='utf-8'))
    review={(r['pdf_url'],r['ordinal']):r for r in review_json['reviewed_turns']}
    groups=defaultdict(list)
    for s in tables['statements']:
        key=(s['event_key'],s['country'],s['target_country'],s.get('spoken_date') or s.get('published_date'),normalized(s['speaker_name']),normalized(s['speaker_office']))
        groups[key].append(s)
    units=[]
    for ss in groups.values():
        sids={s['id'] for s in ss};ds=[documents[d] for sid in sids for d in links[sid]]
        ds=list({d['id']:d for d in ds}.values());qs=[q for sid in sids for q in quotes[sid]]
        unit=assemble_unit(ss,ds,qs,qlinks,extractions,review)
        reason=unit['exclusion_reason']
        if any('nonpolitical_witness' in s['verification_status'] for s in ss):reason='known_nonpolitical_witness'
        elif any(assessments.get(sid,{}).get('relevance_category') in {'third_country_only','incidental_reference','indeterminate'} for sid in sids):
            reason='prior_relevance_uncertain_or_nonbilateral'
        if not unit['fragments']:reason=reason or 'no_attributed_text'
        if unit['date']:
            try:
                d=date.fromisoformat(unit['date'])
                if not date(2015,1,1)<=d<=date(2026,10,31):reason=reason or 'outside_period'
            except ValueError:reason='invalid_date'
        unit['exclusion_reason']=reason
        unit['possible_duplicate_candidates']=sum(r['entity_type']=='statement' and (r['left_id'] in sids or r['right_id'] in sids) for r in tables['duplicate_candidates'])
        unit['input_text_sha256']=digest([prepare(f['text']) for f in unit['fragments']])
        units.append(unit)
    linked_docs={r['document_id'] for r in tables['statement_sources']}
    summary={'statement_records':len(tables['statements']),'unique_event_author_date_units':len(units),
        'document_records':len(documents),'document_only_records_not_signals':len(documents)-len(linked_docs),
        'bibliographic_documents_without_text':sum(not d['text'].strip() for d in documents.values()),
        'gdelt_separate':{t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('gdelt_events','gdelt_mentions','gdelt_gkg')},
        'schema_version':db.execute('PRAGMA user_version').fetchone()[0],
        'core_input_sha256':input_sha,'qa_sha256':digest(review_json),
        'completeness_review_sha256':digest(completeness_json),
        'assembly_extraction_sha256':digest({u:hashlib.sha256(d['text'].encode()).hexdigest() for u,d in extractions.items()})}
    db.close()
    return sorted(units,key=lambda u:u['unit_id']),summary
