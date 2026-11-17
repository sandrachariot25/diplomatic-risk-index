"""Verify ONLY this expansion; no rerun of the historical content audits."""
import json,sqlite3,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.expansion import PREFIX,counts
from dri.models import Document
from dri.statements import Statement,Quote
from dri.repository import ingest,start_run,finish_run
from dri.paths import write_generated

def main():
    s=Store();db=s.db
    try:
        base=json.loads(db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(PREFIX+'-baseline',)).fetchone()[0])
        if db.execute("SELECT 1 FROM collection_runs WHERE status='running' AND run_key LIKE 'expansion-%'").fetchone():
            raise RuntimeError('Finish active expansion writers before the final snapshot check')
        # Flag only new, explicitly nonpolitical roles; retain text, IDs and dates.
        from dri.storage import now
        witnesses=[]
        for sid,role,group,evidence in db.execute('SELECT s.id,s.speaker_office,m.political_affiliation,m.evidence_json FROM statements s JOIN statement_metadata m ON m.statement_id=s.id WHERE s.id>?',(base['last_statement_id'],)).fetchall():
            ev=json.loads(evidence);ev.pop('selection_bias',None)
            ev['current_selection']='NDL any=日韓; no office priority; complete original sentence <=90 characters; source quotation confirmed, interpretation pending'
            with db:
                db.execute('UPDATE statement_metadata SET evidence_json=? WHERE statement_id=?',(json.dumps(ev,ensure_ascii=False),sid))
                if group and not role:
                    db.execute("UPDATE statement_metadata SET institution_type='parliament',speaker_category='parliamentary_group_member_role_unspecified' WHERE statement_id=?",(sid,))
        for sid,role in db.execute('SELECT id,speaker_office FROM statements WHERE id>?',(base['last_statement_id'],)).fetchall():
            if role and any(word in role for word in ('教授','研究員')):
                witnesses.append(sid)
                with db:
                    db.execute("UPDATE statement_metadata SET institution_type='other',speaker_category='nonpolitical_witness',position_scope='unclear' WHERE statement_id=?",(sid,))
                    db.execute("UPDATE statements SET verification_status='needs_review_nonpolitical_witness' WHERE id=?",(sid,))
                    for did,metadata in db.execute('SELECT d.id,d.metadata_json FROM documents d JOIN statement_sources ss ON ss.document_id=d.id WHERE ss.statement_id=?',(sid,)).fetchall():
                        m=json.loads(metadata);m.update(observation_type='parliamentary_witness_excerpt',analysis_status='nonpolitical_witness_excluded_from_political_frequencies')
                        db.execute('UPDATE documents SET metadata_json=? WHERE id=?',(json.dumps(m,ensure_ascii=False),did))
        # Technical checkpoint correction: known event OR publication date, and
        # distributions of this batch rather than unrelated concurrent writers.
        for rid,key in db.execute("SELECT id,run_key FROM collection_runs WHERE run_key LIKE 'expansion-2015-2026-queue-%' AND run_key NOT LIKE '%checkpoint'").fetchall():
            record=db.execute('SELECT id,config_json FROM collection_runs WHERE run_key=?',(key+'-checkpoint',)).fetchone()
            if not record:continue
            check=json.loads(record[1])
            check['mandatory_date_rule']='documented event OR publication date; no imputation'
            check['mandatory_missing']=db.execute("SELECT count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? AND (coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')) IS NULL OR d.language IS NULL OR d.url='' OR d.text='')",(rid,)).fetchone()[0]
            check['theme_distribution']=db.execute("SELECT json_extract(d.metadata_json,'$.theme'),count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? GROUP BY 1",(rid,)).fetchall()
            check['year_country_distribution']=db.execute("SELECT substr(coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')),1,4),json_extract(d.metadata_json,'$.country_scope'),d.source,count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? GROUP BY 1,2,3",(rid,)).fetchall()
            with db:db.execute('UPDATE collection_runs SET config_json=? WHERE id=?',(json.dumps(check,ensure_ascii=False),record[0]))
        for rid,key in db.execute("SELECT id,run_key FROM collection_runs WHERE run_key LIKE 'expansion-kokkai-%-start-%' AND run_key NOT LIKE '%checkpoint'").fetchall():
            saved=db.execute('SELECT id,config_json FROM collection_runs WHERE run_key=?',(key+'-checkpoint',)).fetchone()
            if not saved:continue
            check=json.loads(saved[1]);check['mandatory_date_rule']='known speech date; publication date not imputed'
            check['mandatory_missing']=db.execute("SELECT count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? AND (coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')) IS NULL OR d.language IS NULL OR d.url='' OR d.text='')",(rid,)).fetchone()[0]
            check['theme_distribution']=db.execute("SELECT s.theme,count(*) FROM collection_items i JOIN statement_sources ss ON ss.document_id=i.document_id JOIN statements s ON s.id=ss.statement_id WHERE i.run_id=? GROUP BY 1",(rid,)).fetchall()
            check['year_country_distribution']=db.execute("SELECT substr(s.spoken_date,1,4),s.country,s.target_country,count(*) FROM collection_items i JOIN statement_sources ss ON ss.document_id=i.document_id JOIN statements s ON s.id=ss.statement_id WHERE i.run_id=? GROUP BY 1,2,3",(rid,)).fetchall()
            with db:db.execute('UPDATE collection_runs SET config_json=? WHERE id=?',(json.dumps(check,ensure_ascii=False),saved[0]))
        # Existing discovered documents remain referenced, not fetched again.
        with db:
            db.execute("UPDATE discovery_results SET status='already_documented_before_expansion' WHERE status='unreviewed' AND EXISTS(SELECT 1 FROM document_aliases a WHERE a.source=discovery_results.source_id AND a.normalized_url=discovery_results.normalized_url)")
            db.execute("UPDATE discovery_results SET status='pending_media_rights_review' WHERE source_id='korea_herald' AND status='unreviewed'")
        protected={}
        original=sqlite3.connect((ROOT/'data/backups/pre-schema-004.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            for table,cutoff in [('documents',base['last_document_id']),('statements',base['last_statement_id']),('quotes',base['last_quote_id'])]:
                protected[table]=original.execute(f'SELECT * FROM {table} WHERE id<=? ORDER BY id',(cutoff,)).fetchall()==db.execute(f'SELECT * FROM {table} WHERE id<=? ORDER BY id',(cutoff,)).fetchall()
        finally:original.close()
        assert all(protected.values()),protected
        tables=('documents','statements','quotes','statement_sources','quote_sources','duplicate_candidates','document_aliases','observations','gdelt_events','gdelt_mentions','gdelt_gkg')
        def domain_counts():return {t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
        before=domain_counts()
        cols=('event_key','country','target_country','institution','context','published_date','spoken_date','speaker_name','speaker_office','addressee','theme','original_language','verification_status','attribution_confidence','attribution_evidence','third_country_context')
        repeated=0
        for did,metadata in db.execute('SELECT id,metadata_json FROM documents WHERE id>? ORDER BY id',(base['last_document_id'],)).fetchall():
            doc=Document(**json.loads(metadata));statements=[]
            for row in db.execute('SELECT s.id,'+','.join('s.'+c for c in cols)+' FROM statements s JOIN statement_sources ss ON ss.statement_id=s.id WHERE ss.document_id=?',(did,)).fetchall():
                quotes=db.execute('SELECT q.text,q.published_language,q.original_language,q.version_kind,qs.evidence_locator FROM quotes q JOIN quote_sources qs ON qs.quote_id=q.id WHERE q.statement_id=? AND qs.document_id=?',(row[0],did)).fetchall()
                statements.append(Statement(**dict(zip(cols,row[1:])),quotes=tuple(Quote(*q) for q in quotes)))
            result=ingest(s,doc,statements=statements)
            assert result['documents_added']==result['statements_added']==result['quotes_added']==0,result
            repeated+=1
        after=domain_counts();assert before==after,(before,after)
        archive_hashes=0
        for path,sha in db.execute("SELECT DISTINCT raw_path,sha256 FROM fetches WHERE status=200 AND url LIKE 'https://data.gdeltproject.org/gdeltv2/%.zip' AND raw_path IS NOT NULL"):
            assert hashlib.sha256((s.root/path).read_bytes()).hexdigest()==sha
            archive_hashes+=1
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        result={'documents_reingested':repeated,'before':before,'after':after,'passed':True,'network_requests':0,
                'baseline_entities_preserved':protected,'gdelt_archive_hashes_verified':archive_hashes,
                'nonpolitical_witness_ids':witnesses,'original_audits_repeated':False,
                'checkpoint_date_rule_corrected':'known event OR publication, per batch distributions'}
        prior=db.execute('SELECT id FROM collection_runs WHERE run_key=?',('expansion-final-offline-validation',)).fetchone()
        if prior:
            with db:db.execute('UPDATE collection_runs SET config_json=?,finished_at=? WHERE id=?',(json.dumps(result,ensure_ascii=False),now(),prior[0]))
        else:finish_run(s,start_run(s,'expansion-final-offline-validation',result))
        s.export()
        from dri.quality import report
        report(s)
        path=ROOT/'data/verification.json';v=json.loads(path.read_text(encoding='utf-8'));v['expansion_idempotence']=result
        write_generated(path,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=True))
    finally:db.close()
if __name__=='__main__':main()
