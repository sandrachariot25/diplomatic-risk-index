"""Offline integrity, provenance and idempotent-ingestion check."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dri.connectors import CONNECTORS
from dri.storage import Store
from dri.models import Document
from dri.statements import Statement, Quote
from dri.repository import ingest, start_run, queue_item, finish_run
from dri.quality import report

def main():
    store = Store(ROOT / 'data')
    try:
        assert store.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not store.db.execute('PRAGMA foreign_key_check').fetchall()
        import sqlite3
        pre_audit_preserved=None
        audit_baseline=ROOT/'data/backups/pre-schema-003.sqlite3'
        if audit_baseline.exists():
            from dri.corpus_audit import core_snapshot
            original=sqlite3.connect(audit_baseline.as_uri()+'?mode=ro',uri=True)
            try:
                # Authorized appends do not invalidate preservation of original rows.
                from dri.corpus_audit import CORE_TABLES
                pre_audit_preserved=True
                for table in CORE_TABLES:
                    cutoff=original.execute(f'SELECT coalesce(max(rowid),0) FROM {table}').fetchone()[0]
                    pre_audit_preserved &= (original.execute(f'SELECT rowid,* FROM {table} ORDER BY rowid').fetchall()==
                        store.db.execute(f'SELECT rowid,* FROM {table} WHERE rowid<=? ORDER BY rowid',(cutoff,)).fetchall())
                assert pre_audit_preserved,'Pre-audit domain records changed'
            finally:original.close()
        baseline=ROOT/'data/backups/pre-schema-001.sqlite3'
        legacy_preserved=None
        if baseline.exists():
            original=sqlite3.connect(baseline.as_uri()+'?mode=ro',uri=True)
            try:
                cols='id,source,url,text_sha256,metadata_json,text,created_at'
                legacy=original.execute('SELECT '+cols+' FROM documents ORDER BY id').fetchall()
                legacy_preserved=all(store.db.execute('SELECT '+cols+' FROM documents WHERE id=?',(row[0],)).fetchone()==row for row in legacy)
                assert legacy_preserved, 'A pre-migration document was modified'
            finally:original.close()
        rows = store.db.execute("SELECT d.source,d.url,o.raw_path,o.raw_sha256,o.fetched_at FROM documents d JOIN observations o ON d.id=o.document_id WHERE o.raw_path != ''").fetchall()
        for source, url, path, digest, stamp in rows:
            raw = (store.root / path).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == digest, path
        tables=('documents','statements','quotes','statement_sources','quote_sources','language_links','duplicate_candidates')
        def counts():return {t:store.db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in tables}
        before=counts()
        rid=start_run(store,'offline-idempotence-verification',{'purpose':'re-ingest committed original entities; no network'},resume=True)
        for doc_id,metadata in store.db.execute('SELECT id,metadata_json FROM documents ORDER BY id').fetchall():
            doc=Document(**json.loads(metadata))
            statements=[]
            columns=('event_key','country','target_country','institution','context','published_date','spoken_date','speaker_name','speaker_office',
                     'addressee','theme','original_language','verification_status','attribution_confidence','attribution_evidence','third_country_context')
            for row in store.db.execute('SELECT s.id,'+','.join('s.'+c for c in columns)+' FROM statements s JOIN statement_sources ss ON ss.statement_id=s.id WHERE ss.document_id=?',(doc_id,)).fetchall():
                fields=dict(zip(columns,row[1:]))
                qrows=store.db.execute('''SELECT q.text,q.published_language,q.original_language,q.version_kind,qs.evidence_locator
                  FROM quotes q JOIN quote_sources qs ON qs.quote_id=q.id WHERE q.statement_id=? AND qs.document_id=?''',(row[0],doc_id)).fetchall()
                statements.append(Statement(**fields,quotes=tuple(Quote(*q) for q in qrows)))
            key=queue_item(store,rid,doc.source,doc.url)
            result=ingest(store,doc,None,statements,rid,key)
            assert result['documents_added']==result['statements_added']==result['quotes_added']==0, result
        finish_run(store,rid)
        after=counts()
        assert before==after, (before,after)
        store.export()
        result=report(store)
        result['idempotence']={'before':before,'after':after,'passed':before==after,'network_requests':0}
        result['raw_hashes_verified']=len(rows)
        result['legacy_documents_preserved']=legacy_preserved
        result['pre_audit_core_preserved']=pre_audit_preserved
        (store.root / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        with (ROOT/'docs/QUALITY_REPORT.md').open('a',encoding='utf-8') as f:
            f.write('\n## Повторный импорт реального корпуса\n\nДо: `'+json.dumps(before)+'`.\n\nПосле: `'+json.dumps(after)+'`.\n\nЧисло доменных записей и связей не изменилось. Проверка офлайн, сетевых запросов: 0.\n')
        print(json.dumps({'counts':result['counts'],'integrity':result['sqlite_integrity'],'idempotence':result['idempotence'],'raw_hashes_verified':len(rows)}))
    finally:
        store.db.close()

if __name__ == '__main__':
    main()
