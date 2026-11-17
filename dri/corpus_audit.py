"""Offline corpus audit. Evidence-limited labels, stable sampling, no automatic merges."""
import json
import re
from collections import Counter
from .identity import fingerprint,normalized
from .paths import ROOT,write_generated
from .research import records,stratified_sample,insert_metadata
from .storage import now

RULESET='offline-audit-50-v1'
SAMPLE='stratified-50-v1'
CORE_TABLES=('documents','statements','quotes','statement_sources','quote_sources','duplicate_candidates','language_links','speakers','document_aliases','observations')

def core_snapshot(db):
    return {t:fingerprint(db.execute(f'SELECT * FROM {t} ORDER BY rowid').fetchall()) for t in CORE_TABLES}

def evidence_hash(record):
    return fingerprint([(q['id'],q['text']) for q in record['quotes']],record['event_key'],
                       record['spoken_date'],record['published_date'],record['context'])

def provisional_relevance(record):
    text=' '.join(q['text'] for q in record['quotes'])
    lower=text.casefold()
    src={s['source_id'] for s in record['sources']}
    if 'mofa_kr' in src or 'mofa_jp' in src:
        if re.search(r'\b(urges?|demands?|protests?)\b',lower) and re.search(r'japan|japanese|rok|korea',lower):
            return 'direct_address','В сохранённом фрагменте официального источника есть обращённое требование/протест и названная сторона; полный контекст ещё не проверен.'
        return 'official_bilateral','Официальный заголовок задаёт двусторонний контекст; непосредственный адресат и содержание позиции не полностью установлены коротким фрагментом.'
    if re.search(r'日中韓',text):
        return 'regional_cooperation','Явно назван трёхсторонний формат; это не обязательно региональная безопасность.'
    if re.search(r'日韓|日米韓',text) and re.search(r'北朝鮮|ミサイル|安全保障|安定',text) and re.search(r'連携|協力',text):
        return 'regional_security','В одном фрагменте прямо связаны корейско-японская координация и региональная безопасность.'
    if re.search(r'日韓|韓国との|韓国政府|韓国側',text):
        return 'domestic_bilateral','В парламентской реплике явно упомянуты двусторонние отношения/другая сторона; принадлежность к официальной позиции определяется ролью, а не площадкой.'
    if '北朝鮮' in text and not re.search(r'日韓|日米韓',text):
        return 'third_country_only','Сохранённый фрагмент обсуждает Северную Корею без явной связи с двусторонней позицией; это предварительная оценка фрагмента, не исключение всей речи.'
    return 'indeterminate','Сохранённого фрагмента недостаточно для уверенной оценки двусторонней релевантности; источник и парламентская речь сохранены.'

def pair_review(db,candidate):
    cid,kind,left,right=candidate
    if kind=='quote':
        rows=db.execute('SELECT id,statement_id,text,published_language FROM quotes WHERE id IN (?,?) ORDER BY id',(left,right)).fetchall()
        if len(rows)!=2:raise ValueError('Dangling quote duplicate candidate')
        sids=[r[1] for r in rows]
        equal=normalized(rows[0][2])==normalized(rows[1][2])
        langs=[r[3] for r in rows]
    else:
        sids=[left,right]
        qs=[db.execute('SELECT text,published_language FROM quotes WHERE statement_id=? ORDER BY id LIMIT 1',(sid,)).fetchone() for sid in sids]
        equal=bool(qs[0] and qs[1] and normalized(qs[0][0])==normalized(qs[1][0]))
        langs=[q[1] if q else None for q in qs]
    st=[]
    for sid in sids:
        row=db.execute('SELECT event_key,spoken_date,published_date,speaker_name,institution,context FROM statements WHERE id=?',(sid,)).fetchone()
        if not row:raise ValueError('Dangling statement duplicate candidate')
        st.append(dict(zip(('event_key','spoken_date','published_date','speaker_name','institution','context'),row)))
    if sids[0]==sids[1]:
        if langs[0]!=langs[1]:classification='same_statement_language_versions_require_translation_evidence'
        else:classification='same_statement_repeated_or_partial_quote'
    elif st[0]['spoken_date'] and st[1]['spoken_date'] and st[0]['spoken_date']!=st[1]['spoken_date']:
        classification='different_known_speech_dates_keep_separate'
    elif all(s['event_key'].startswith('kokkai:') for s in st) and st[0]['event_key']!=st[1]['event_key']:
        classification='different_parliamentary_speech_ids_keep_separate'
    elif not st[0]['spoken_date'] or not st[1]['spoken_date']:
        classification='different_publications_speech_identity_unconfirmed'
    else:classification='different_context_needs_review'
    evidence=dict(statement_ids=sids,statements=st,normalized_excerpt_equal=equal,languages=langs,
                  linked_documents=[db.execute('SELECT document_id FROM statement_sources WHERE statement_id=?',(sid,)).fetchall() for sid in sids],
                  note='No merge/delete; publication date is not speech date. Similar short excerpts do not establish identity.')
    return classification,evidence

def audit(store):
    db=store.db
    before=core_snapshot(db)
    previous_audit=db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(RULESET,)).fetchone()
    if previous_audit and json.loads(previous_audit[0]).get('core_snapshot_before')!=before:
        raise ValueError('Corpus differs from this audit baseline; do not overwrite an old audit silently')
    rows=records(db)
    sample=stratified_sample(rows,50)
    annotations_path=ROOT/'data/audit_annotations.json'
    annotations=json.loads(annotations_path.read_text(encoding='utf-8')) if annotations_path.exists() else {'records':{}}
    selected={r['id'] for r in sample}
    if set(map(int,annotations['records']))!=selected:
        raise ValueError('Curated excerpt annotations must cover exactly the selected 50 statements')
    prior={r[0] for r in db.execute('SELECT statement_id FROM audit_samples WHERE sample_key=?',(SAMPLE,))}
    if prior and prior!=selected:raise ValueError('Stored sample differs; refusing silent replacement')
    with db:
        for r in rows:
            insert_metadata(db,r['id'],r['metadata'],now())
            category,reason=provisional_relevance(r)
            by='deterministic_excerpt_rules'
            quality='needs_context';suggestion=None
            annotation=annotations['records'].get(str(r['id']))
            if annotation:
                if annotation['evidence_sha256']!=evidence_hash(r):raise ValueError('Curated evidence changed: '+str(r['id']))
                category=annotation['category'];reason=annotation['reason']
                quality=annotation.get('excerpt_quality','needs_context');suggestion=annotation.get('theme_suggestion')
                by='agent_review_of_retained_excerpt_not_human_verification'
            values=(r['id'],category,reason,evidence_hash(r),RULESET,'excerpt_assessed_needs_review',quality,suggestion,by,now())
            db.execute('''INSERT INTO statement_assessments(statement_id,relevance_category,reason,evidence_sha256,ruleset_version,
                assessment_status,excerpt_quality,theme_suggestion,assessed_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(statement_id) DO UPDATE SET relevance_category=excluded.relevance_category,reason=excluded.reason,
                evidence_sha256=excluded.evidence_sha256,ruleset_version=excluded.ruleset_version,
                assessment_status=excluded.assessment_status,excerpt_quality=excluded.excerpt_quality,
                theme_suggestion=excluded.theme_suggestion,assessed_by=excluded.assessed_by,updated_at=excluded.updated_at
                WHERE statement_assessments.evidence_sha256!=excluded.evidence_sha256
                 OR statement_assessments.ruleset_version!=excluded.ruleset_version OR statement_assessments.reason!=excluded.reason
                 OR statement_assessments.relevance_category!=excluded.relevance_category
                 OR statement_assessments.excerpt_quality!=excluded.excerpt_quality
                 OR coalesce(statement_assessments.theme_suggestion,'')!=coalesce(excluded.theme_suggestion,'')''',values)
        for rank,r in enumerate(sample,1):
            strata=dict(country=r['country'],year=r['year'],year_basis='speech_date' if r['spoken_date'] else 'publication_date_not_imputed_as_speech',
                        theme=r['theme'],institution_type=r['metadata']['institution_type'],venue=r['metadata']['venue_institution_type'],
                        source_types=sorted({d['source_type'] for d in r['sources']}))
            db.execute('INSERT INTO audit_samples VALUES(?,?,?,?) ON CONFLICT(sample_key,statement_id) DO NOTHING',
                       (SAMPLE,r['id'],rank,json.dumps(strata,ensure_ascii=False,sort_keys=True)))
        for candidate in db.execute('SELECT id,entity_type,left_id,right_id FROM duplicate_candidates ORDER BY id').fetchall():
            classification,evidence=pair_review(db,candidate)
            db.execute('''INSERT INTO duplicate_reviews(candidate_id,classification,disposition,evidence_json,reviewed_by,ruleset_version,updated_at)
              VALUES(?,?,?,?,?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET classification=excluded.classification,
              evidence_json=excluded.evidence_json,ruleset_version=excluded.ruleset_version,updated_at=excluded.updated_at
              WHERE duplicate_reviews.evidence_json!=excluded.evidence_json OR duplicate_reviews.classification!=excluded.classification''',
              (candidate[0],classification,'possible_duplicate',json.dumps(evidence,ensure_ascii=False,sort_keys=True),'structural_offline_check_not_human_resolution',RULESET,now()))
        after=core_snapshot(db)
        if before!=after:raise RuntimeError('Audit changed original domain records')
        db.execute('''INSERT INTO collection_runs(run_key,started_at,finished_at,status,config_json,counters_json)
          VALUES(?,?,?,?,?,?) ON CONFLICT(run_key) DO NOTHING''',
          (RULESET,now(),now(),'completed',json.dumps({'scope':'offline only, no network, no weights or inference of missing facts',
           'core_snapshot_before':before,'sample_ids':[r['id'] for r in sample]},sort_keys=True),json.dumps({'audited_statements':len(rows),'sample_size':50})))
    return summary(db,before==after)

def summary(db,preserved=None):
    if preserved is None:
        proof=db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(RULESET,)).fetchone()
        preserved=(json.loads(proof[0]).get('core_snapshot_before')==core_snapshot(db)) if proof else None
        expansion=db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',('media-bibliography-2026-10-30-preservation',)).fetchone()
        if proof and expansion:
            baseline=json.loads(expansion[0])
            preserved=(json.loads(proof[0]).get('core_snapshot_before')==baseline.get('original_core_snapshot') and
                       all(fingerprint(db.execute(f'SELECT rowid,* FROM {table} WHERE rowid<=? ORDER BY rowid',(saved['last_rowid'],)).fetchall())==saved['hash']
                           for table,saved in baseline['tables'].items()))
    total=db.execute('SELECT count(*) FROM statements').fetchone()[0]
    return dict(sample_size=db.execute('SELECT count(*) FROM audit_samples WHERE sample_key=?',(SAMPLE,)).fetchone()[0],
                sample_country=dict(db.execute('SELECT s.country,count(*) FROM audit_samples a JOIN statements s ON s.id=a.statement_id WHERE a.sample_key=? GROUP BY s.country',(SAMPLE,))),
                sample_relevance=dict(db.execute('SELECT relevance_category,count(*) FROM statement_assessments a JOIN audit_samples s ON s.statement_id=a.statement_id WHERE s.sample_key=? GROUP BY relevance_category',(SAMPLE,))),
                corpus_relevance=dict(db.execute('SELECT relevance_category,count(*) FROM statement_assessments GROUP BY relevance_category')),
                institution_counts=dict(db.execute('SELECT institution_type,count(*) FROM statement_metadata GROUP BY institution_type')),
                venue_counts=dict(db.execute("SELECT coalesce(venue_institution_type,'unknown'),count(*) FROM statement_metadata GROUP BY venue_institution_type")),
                speaker_categories=dict(db.execute('SELECT speaker_category,count(*) FROM statement_metadata GROUP BY speaker_category')),
                duplicate_review_counts=dict(db.execute('SELECT classification,count(*) FROM duplicate_reviews GROUP BY classification')),
                core_records_preserved=preserved,
                requires_human_verification=db.execute("SELECT count(*) FROM statements WHERE verification_status!='verified'").fetchone()[0],
                established_speech_dates=total-db.execute('SELECT count(*) FROM statements WHERE spoken_date IS NULL').fetchone()[0],
                established_names=total-db.execute('SELECT count(*) FROM statements WHERE speaker_name IS NULL').fetchone()[0],
                established_party_status=db.execute('SELECT count(*) FROM statement_metadata WHERE government_opposition_status IS NOT NULL').fetchone()[0],
                verified_sentiment=dict(db.execute('SELECT sentiment,count(*) FROM statement_assessments WHERE sentiment_verified=1 GROUP BY sentiment')))
