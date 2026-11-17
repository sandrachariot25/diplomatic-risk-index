"""Resumable, rights-gated conversion of existing discovery, not a URL-count target."""
import json
import re
from dataclasses import replace
from .storage import now
from .identity import fingerprint,normalize_url
from .repository import start_run,queue_item,finish_run,ingest,register_sources
from .connectors.korea import KoreaMOFA
from .collection import retained
from .statements import extract_korean_institutional,theme_for
from .http import Client,AccessBlocked
from .html import Tree,one

PREFIX='expansion-2015-2026'
COUNTS=('documents','statements','quotes','discovery_results')
def counts(db):
    row=db.execute('SELECT '+','.join('(SELECT count(*) FROM '+t+')' for t in COUNTS)).fetchone()
    return dict(zip(COUNTS,row))

def baseline(store):
    key=PREFIX+'-baseline'
    row=store.db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(key,)).fetchone()
    if row:return json.loads(row[0])
    result={'counts':counts(store.db),'last_document_id':store.db.execute('SELECT coalesce(max(id),0) FROM documents').fetchone()[0],
            'last_statement_id':store.db.execute('SELECT coalesce(max(id),0) FROM statements').fetchone()[0],
            'last_quote_id':store.db.execute('SELECT coalesce(max(id),0) FROM quotes').fetchone()[0],
            'created_at':now()}
    finish_run(store,start_run(store,key,result))
    return result

def candidates(db, size):
    rows=db.execute('''SELECT r.id,r.normalized_url,r.title FROM discovery_results r
       WHERE r.source_id='mofa_kr' AND r.status='unreviewed' AND NOT EXISTS
       (SELECT 1 FROM document_aliases a WHERE a.source=r.source_id AND a.normalized_url=r.normalized_url)
       ORDER BY r.id''').fetchall()
    # Spread over the queue, not exclusively latest items or conflict terms.
    if len(rows)<=size:return rows
    return [rows[i*(len(rows)-1)//(size-1)] for i in range(size)] if size>1 else rows[:1]

def convert(html,url):
    full=KoreaMOFA().parse(html,url)
    if not '2015-01-01'<=full.published_date<='2026-10-31':return None
    if not re.search(r'\bJapan(?:ese)?\b|Dokdo|Takeshima',full.title+' '+full.text,re.I):return None
    if not re.search(r'\bROK\b|Republic of Korea|\bSouth Korea(?:n)?\b|\bKorea(?:n)?[-– ]Japan\b|\bJapan[-– ]Korea\b',full.title+' '+full.text,re.I):return None
    detail=one(Tree(html).root.find(cls='board_detail'),'board_detail')
    prose=full.text
    # Applicable only to MOFA-authored press release prose; never attachments/photos,
    # outside-author speeches, joint works, translations credited to third parties.
    notices=detail.text()+' '+' '.join(str(value) for node in detail.find() for value in node.attrs.values())
    restricted=bool(re.search(r'Reuters|Yonhap|Associated Press|reproduced|permission|copyright|all rights reserved|joint statement|joint declaration|provided by|저작권|제\s*[234]\s*유형|licenseType[234]|(?:img_open|kogl)[_ -]?[234]',
                         notices,re.I))
    full_allowed=not restricted and not re.search(r'\bspeech\b|\baddress by\b|\bstatement by\b',full.title,re.I)
    doc=retained(full,'full_text_permitted' if full_allowed else 'excerpt_only')
    return replace(doc,country_scope='ROK',institution=full.publisher,
        observation_addressee='JPN: topic; direct recipient unverified',
        observation_type='official_institutional_statement' if extract_korean_institutional(doc) else 'official_activity_report',
        text_completeness='complete_published_body' if full_allowed else 'restricted_excerpt',
        analysis_status='text_frequency_candidate_not_statement_frequency' if full_allowed else 'insufficient_text_pending_rights',
        verification_status='needs_review',theme=theme_for(full.title+' '+full.text),
        rights_evidence='https://www.mofa.go.kr/www/wpge/m_4190/contents.do; MOFA own press-release prose; item-specific conditions take precedence',
        rights='MOFA default KOGL Type 1 attribution for own text; credit Ministry, title, date and URL; no attachment/photo rights inferred' if full_allowed else 'Restricted excerpt; rights unresolved')

def run_batch(store,size=20,execute=False,retry_errors=False):
    if not 1<=size<=20:raise ValueError('Batch size must be 1..20')
    db=store.db
    states=('running','interrupted','completed_with_errors') if retry_errors else ('running','interrupted')
    pending=db.execute('SELECT id,config_json FROM collection_runs WHERE run_key LIKE ? AND run_key NOT LIKE ? AND status IN ('+','.join('?' for _ in states)+') ORDER BY id LIMIT 1',(PREFIX+'-queue-%','%-checkpoint',*states)).fetchone()
    selected=json.loads(pending[1])['selected'] if pending else candidates(db,size)
    print(json.dumps({'plan':'existing discovery only; >=5.5s; robots/TLS; no full response retention; stop host on denial',
        'selected':selected,'document_urls_max':len(selected),'redirects':'bounded by HTTP client; each validated','target':2000,'eligible_does_not_include_urls_or_metadata':True},ensure_ascii=True),flush=True)
    if not execute or not selected:return None
    base=baseline(store);register_sources(store)
    config={'selected':selected,'retention':'mofa-own-prose-default-kogl1-otherwise-excerpt','ruleset':'expansion-queue-v1'}
    key=PREFIX+'-queue-'+fingerprint(selected)[:16]
    rid=start_run(store,key,config,resume=True)
    client=Client(store,'windows',retain_body=False)
    state='completed';new_ids=[];repeat=[]
    try:
        for discovery_id,url,title in selected:
            qkey=queue_item(store,rid,'mofa_kr',url)
            done=db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,qkey)).fetchone()[0]
            if done in ('processed','excluded'):continue
            if done.endswith('_error'):
                previous=db.execute('SELECT error FROM collection_items WHERE run_id=? AND item_key=?',(rid,qkey)).fetchone()[0] or ''
                allowed=retry_errors and ('timed out' in previous.lower() or 'TimeoutExpired' in previous) and not re.search(r'HTTP\s*(401|403|429)',previous)
                if not allowed:
                    state='completed_with_errors';break
            existing=db.execute('SELECT document_id FROM document_aliases WHERE source=? AND normalized_url=?',('mofa_kr',normalize_url(url))).fetchone()
            if existing:
                with db:
                    db.execute("UPDATE discovery_results SET status='already_imported' WHERE id=?",(discovery_id,))
                    db.execute("UPDATE collection_items SET status='excluded',error='Previously imported; no fetch',updated_at=? WHERE run_id=? AND item_key=?",(now(),rid,qkey))
                continue
            try:
                html,raw,final=client.get(url)
                doc=convert(html,final)
                if doc is None:
                    with db:
                        db.execute("UPDATE discovery_results SET status='excluded_outside_scope' WHERE id=?",(discovery_id,))
                        db.execute("UPDATE collection_items SET status='excluded',updated_at=? WHERE run_id=? AND item_key=?",(now(),rid,qkey))
                    continue
                # Activity reports remain documents, not reconstructed political statements.
                statements=extract_korean_institutional(doc) if doc.observation_type=='official_institutional_statement' else []
                result=ingest(store,doc,raw,statements,rid,qkey)
                before=counts(db)
                second=ingest(store,doc,raw,statements)
                assert second['documents_added']==second['statements_added']==second['quotes_added']==0
                repeat.append(result['document_id'])
                if result['documents_added']:new_ids.append(result['document_id'])
                with db:db.execute("UPDATE discovery_results SET status=?,published_date=? WHERE id=?",('converted_full_text' if doc.content_policy=='full_text_permitted' else 'converted_restricted_excerpt',doc.published_date,discovery_id))
                print(json.dumps({'discovery_id':discovery_id,**result,'repeat_passed':True,'text_frequency_candidate':doc.content_policy=='full_text_permitted'}),flush=True)
            except Exception as error:
                store.error('mofa_kr',url,'expansion_queue',error)
                with db:
                    db.execute("UPDATE collection_items SET status='access_error',error=?,updated_at=? WHERE run_id=? AND item_key=?",(str(error),now(),rid,qkey))
                    db.execute("UPDATE discovery_results SET status='expansion_access_error' WHERE id=?",(discovery_id,))
                state='completed_with_errors'
                if isinstance(error,(AccessBlocked,OSError)):break
    except BaseException:
        state='interrupted';raise
    finally:
        finish_run(store,rid,state);store.export()
    full_count=db.execute("SELECT count(*) FROM documents WHERE id>? AND content_policy='full_text_permitted'",(base['last_document_id'],)).fetchone()[0]
    new_ids=[r[0] for r in db.execute('SELECT document_id FROM collection_items WHERE run_id=? AND documents_added=1',(rid,))]
    # Also verify committed items from an interrupted process, using their stored
    # evidence rather than fetching the page again.
    from .models import Document
    repeat=[]
    for did,metadata in db.execute("SELECT d.id,d.metadata_json FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? AND i.status='processed'",(rid,)).fetchall():
        stored=Document(**json.loads(metadata));before=counts(db)
        outcome=ingest(store,stored,statements=extract_korean_institutional(stored) if stored.observation_type=='official_institutional_statement' else [])
        assert outcome['documents_added']==outcome['statements_added']==outcome['quotes_added']==0
        repeat.append(did)
    verification={'batch_run_id':rid,'added_document_ids':new_ids,'repeat_verified_document_ids':repeat,
                  'counts_after':counts(db),'full_texts_added_since_baseline':full_count,'text_frequency_candidates_since_baseline':full_count,
                  'mandatory_missing':db.execute("SELECT count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? AND (coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')) IS NULL OR d.language IS NULL OR d.url='' OR d.text='')",(rid,)).fetchone()[0],
                  'theme_distribution':db.execute("SELECT json_extract(d.metadata_json,'$.theme'),count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? GROUP BY 1",(rid,)).fetchall(),
                  'year_country_distribution':db.execute("SELECT substr(coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')),1,4),json_extract(d.metadata_json,'$.country_scope'),d.source,count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? GROUP BY 1,2,3",(rid,)).fetchall()}
    prior=db.execute('SELECT id FROM collection_runs WHERE run_key=?',(key+'-checkpoint',)).fetchone()
    if prior:
        with db:db.execute('UPDATE collection_runs SET config_json=? WHERE id=?',(json.dumps(verification,ensure_ascii=False),prior[0]))
        finish_run(store,prior[0])
    else:finish_run(store,start_run(store,key+'-checkpoint',verification))
    from .expansion_outputs import update
    if store.root.name=='data':update(store)
    return verification
