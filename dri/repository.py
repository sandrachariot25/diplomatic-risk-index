"""Atomic document/statement/quote ingestion with conservative duplicate review."""
import json
from .identity import normalized, fingerprint, token_similarity, normalize_url
from .storage import now
from .paths import ROOT

def register_sources(store):
    rows = json.loads((ROOT / 'config/sources.json').read_text(encoding='utf-8'))
    with store.db:
        for row in rows:
            store.db.execute('''INSERT INTO sources(id,name,country,source_type,base_url,terms_url,access_status,content_policy,audit_json)
              VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,
              country=excluded.country,source_type=excluded.source_type,base_url=excluded.base_url,
              terms_url=excluded.terms_url,content_policy=excluded.content_policy,audit_json=excluded.audit_json''',
              (row['id'],row['name'],row.get('country'),row['source_type'],row['base_url'],row.get('terms_url'),
               row['access_status'],row['content_policy'],json.dumps(row,ensure_ascii=False)))

def normalize_legacy_fingerprint(store, doc):
    """Change ONLY a verified legacy JSON fingerprint into a normalized text SHA.

    The transient full speech must exactly reproduce the prior legacy fingerprint.
    Original document bytes/excerpts, IDs, dates and quotes are never replaced.
    """
    if doc.source!='kokkai_jp' or not doc.legacy_content_fingerprint:return False
    row=store.db.execute('SELECT id,text_sha256,metadata_json FROM documents WHERE source=? AND official_id=?',
                         (doc.source,doc.official_identifier)).fetchone()
    if not row or row[1]==doc.text_sha256:return False
    if row[1]!=doc.legacy_content_fingerprint:
        raise ValueError('Source speech changed; cannot safely normalize its existing fingerprint')
    metadata=json.loads(row[2])
    metadata['legacy_content_fingerprint']=row[1]
    metadata['content_sha256']=doc.text_sha256
    metadata['fingerprint_kind']='normalized_text'
    with store.db:
        store.db.execute('UPDATE documents SET text_sha256=?,metadata_json=? WHERE id=? AND text_sha256=?',
                         (doc.text_sha256,json.dumps(metadata,ensure_ascii=False),row[0],row[1]))
    return True

def _candidate(db, kind, a, b, reason, score):
    if a == b:
        return 0
    a, b = sorted((a,b))
    return db.execute('''INSERT OR IGNORE INTO duplicate_candidates(entity_type,left_id,right_id,reason,similarity)
                       VALUES(?,?,?,?,?)''', (kind,a,b,reason,score)).rowcount

def _statement(db, st, document_id):
    st.validate()
    speaker_id = None
    if st.speaker_name:
        # Role is the observed role for THIS dated record, not a timeless name->office map.
        skey = fingerprint(st.country,normalized(st.speaker_name),normalized(st.speaker_office),st.spoken_date or st.published_date)
        db.execute('''INSERT INTO speakers(country,name,office,valid_from,valid_to,identity_key)
          VALUES(?,?,?,?,?,?) ON CONFLICT(identity_key) DO NOTHING''',
          (st.country,st.speaker_name,st.speaker_office or '',st.spoken_date,st.spoken_date,skey))
        speaker_id = db.execute('SELECT id FROM speakers WHERE identity_key=?',(skey,)).fetchone()[0]
    existing = db.execute('SELECT id FROM statements WHERE identity_key=?',(st.key,)).fetchone()
    added = existing is None
    if added:
        cur = db.execute('''INSERT INTO statements(identity_key,event_key,speaker_id,speaker_name,speaker_office,country,
        institution,target_country,addressee,spoken_date,published_date,context,theme,original_language,
        verification_status,attribution_confidence,attribution_evidence,third_country_context,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (st.key,st.event_key,speaker_id,st.speaker_name,st.speaker_office,st.country,st.institution,st.target_country,
         st.addressee,st.spoken_date,st.published_date,st.context,st.theme,st.original_language,
         st.verification_status,st.attribution_confidence,st.attribution_evidence,int(st.third_country_context),now()))
        sid = cur.lastrowid
    else:
        sid = existing[0]
    from .research import institutional_metadata,insert_metadata
    source_id=db.execute('SELECT source FROM documents WHERE id=?',(document_id,)).fetchone()[0]
    metadata=institutional_metadata(st.__dict__,{source_id})
    for name in ('institution_type','speaker_role','political_affiliation','government_opposition_status','political_status_date','statement_context','position_scope'):
        if getattr(st,name,None) is not None:metadata[name]=getattr(st,name)
    if st.metadata_evidence:
        evidence=json.loads(metadata['evidence_json']);evidence['provided_metadata_evidence']=st.metadata_evidence
        metadata['evidence_json']=json.dumps(evidence,ensure_ascii=False,sort_keys=True)
    insert_metadata(db,sid,metadata,now())
    db.execute('INSERT OR IGNORE INTO statement_sources VALUES(?,?,?,?)',
               (sid,document_id,'primary_statement' if db.execute('SELECT source_type FROM documents WHERE id=?',(document_id,)).fetchone()[0]=='primary' else 'secondary_report',st.verification_status))
    quotes_added = 0
    possible = 0
    for q in st.quotes:
        digest = fingerprint(normalized(q.text))
        cur = db.execute('''INSERT INTO quotes(statement_id,text,text_sha256,published_language,original_language,version_kind,verification_status)
         VALUES(?,?,?,?,?,?,?) ON CONFLICT(statement_id,published_language,text_sha256) DO NOTHING''',
         (sid,q.text,digest,q.language,q.original_language,q.version_kind,st.verification_status))
        quotes_added += cur.rowcount
        qid = db.execute('SELECT id FROM quotes WHERE statement_id=? AND published_language=? AND text_sha256=?',(sid,q.language,digest)).fetchone()[0]
        db.execute('INSERT OR IGNORE INTO quote_sources VALUES(?,?,?)',(qid,document_id,q.locator))
        if cur.rowcount:
            # Search only the same direction; different events/dates remain separate even if exact.
            for other_id, other_sid, text in db.execute('''SELECT q.id,q.statement_id,q.text FROM quotes q JOIN statements s ON s.id=q.statement_id
              WHERE q.id != ? AND q.published_language=? AND s.country=? AND s.target_country=?''',(qid,q.language,st.country,st.target_country)):
                score = token_similarity(q.text,text)
                exact = normalized(q.text) == normalized(text)
                if exact or score >= .72:
                    possible += _candidate(db,'quote',qid,other_id,'exact_text_different_record' if exact else 'partial_text_similarity',score)
                    if sid != other_sid:
                        possible += _candidate(db,'statement',sid,other_sid,'quote_overlap_unverified_event',score)
    return sid,int(added),quotes_added,possible

def ingest(store, doc, raw_ref=None, statements=(), run_id=None, item_key=None, *, on_statement=None):
    """All domain entities and checkpoint commit together; exceptions roll everything back."""
    for st in statements:
        st.validate()
        for q in st.quotes:
            if normalized(q.text) not in normalized(doc.text):
                raise ValueError('Quote is not present in retained document evidence')
    with store.db:
        doc_id, added = store._save(doc,raw_ref)
        sa = qa = pm = 0
        for st in statements:
            sid, n, q, m = _statement(store.db,st,doc_id)
            if on_statement is not None:
                on_statement(doc_id, sid, bool(n))
            sa += n; qa += q; pm += m
        result = dict(document_id=doc_id,documents_added=int(added),statements_added=sa,quotes_added=qa,
                      duplicates_rejected=int(not added) + len(statements)-sa + sum(len(st.quotes) for st in statements)-qa,possible_matches=pm)
        if run_id is not None:
            store.db.execute('''UPDATE collection_items SET status='processed',document_id=?,documents_added=?,statements_added=?,
            quotes_added=?,duplicates_rejected=?,possible_matches=?,error=NULL,updated_at=? WHERE run_id=? AND item_key=?''',
            (doc_id,int(added),sa,qa,result['duplicates_rejected'],pm,now(),run_id,item_key))
        return result

def link_language_versions(store, quote_a, quote_b, evidence_url, verified_by):
    """Manual/officially evidenced association; no multilingual text guessing."""
    if not evidence_url or not verified_by:
        raise ValueError('Explicit translation evidence and reviewer required')
    a,b = sorted((quote_a,quote_b))
    rows = store.db.execute('SELECT id,statement_id,published_language FROM quotes WHERE id IN (?,?)',(a,b)).fetchall()
    if len(rows)!=2 or rows[0][1]!=rows[1][1] or rows[0][2]==rows[1][2]:
        raise ValueError('Language links require different-language quotes in the same verified event')
    with store.db:
        store.db.execute('INSERT OR IGNORE INTO language_links(statement_id,quote_a,quote_b,relation,evidence_url,verified_by) VALUES(?,?,?,?,?,?)',
                         (rows[0][1],a,b,'official_translation',normalize_url(evidence_url),verified_by))

def start_run(store, run_key, config, resume=False):
    found = store.db.execute('SELECT id,config_json FROM collection_runs WHERE run_key=?',(run_key,)).fetchone()
    if found:
        if not resume:
            raise ValueError('Run exists; use --resume or an explicit different run key')
        if json.loads(found[1]) != config:
            raise ValueError('Resume configuration differs from saved run')
        with store.db:
            store.db.execute("UPDATE collection_runs SET status='running',finished_at=NULL WHERE id=?",(found[0],))
        return found[0]
    with store.db:
        return store.db.execute('INSERT INTO collection_runs(run_key,started_at,status,config_json) VALUES(?,?,?,?)',
                               (run_key,now(),'running',json.dumps(config,sort_keys=True))).lastrowid

def queue_item(store, run_id, source, url, *, item_key=None):
    key = item_key or fingerprint(source,normalize_url(url))
    with store.db:
        store.db.execute('INSERT OR IGNORE INTO collection_items(run_id,item_key,url,source,status,updated_at) VALUES(?,?,?,?,?,?)',
                         (run_id,key,url,source,'pending',now()))
    return key

def run_counters(store, run_id):
    counters = dict(store.db.execute('''SELECT 'documents_discovered',count(*) FROM collection_items WHERE run_id=? AND status!='query_completed' ''',(run_id,)).fetchall())
    counters['queries_completed']=store.db.execute("SELECT count(*) FROM collection_items WHERE run_id=? AND status='query_completed'",(run_id,)).fetchone()[0]
    counters['documents_processed'] = store.db.execute("SELECT count(*) FROM collection_items WHERE run_id=? AND status='processed'",(run_id,)).fetchone()[0]
    for name in ('documents_added','statements_added','quotes_added','duplicates_rejected','possible_matches'):
        counters[name] = store.db.execute(f'SELECT coalesce(sum({name}),0) FROM collection_items WHERE run_id=?',(run_id,)).fetchone()[0]
    counters['access_errors'] = store.db.execute("SELECT count(*) FROM collection_items WHERE run_id=? AND status='access_error'",(run_id,)).fetchone()[0]
    counters['other_errors'] = store.db.execute("SELECT count(*) FROM collection_items WHERE run_id=? AND status='parse_error'",(run_id,)).fetchone()[0]
    return counters

def finish_run(store, run_id, status='completed'):
    counters=run_counters(store,run_id)
    with store.db:
        store.db.execute('UPDATE collection_runs SET status=?,finished_at=?,counters_json=? WHERE id=?',(status,now(),json.dumps(counters),run_id))
    return counters
