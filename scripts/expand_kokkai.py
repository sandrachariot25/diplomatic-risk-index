"""New NDL speeches only; complete short source quotations, all political roles."""
import argparse,json,re,sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dri.storage import Store,now
from dri.http import Client,AccessBlocked
from dri.connectors.kokkai import Kokkai
from dri.statements import Quote
from dri.repository import start_run,finish_run,queue_item,ingest
from dri.expansion import baseline,counts

def complete_quote(speech):
    # Retain one complete sentence, never a 90-character cut in the middle.
    for sentence in re.findall(r'[^。！？!?]+[。！？!?]',speech):
        sentence=sentence.strip()
        sentence=re.sub(r'^[○◯][^\s　]+[\s　]+','',sentence)
        if '日韓' in sentence and 15<=len(sentence)<=90:return sentence
    return None

def collect(store,year,execute=False,start_record=1,retry_errors=False):
    api=Kokkai();url=api.request_url(year,20,query='日韓')+'&startRecord='+str(start_record)
    print(json.dumps({'plan':url,'max_new_speeches':20,'roles':'all; no ministry priority','retention':'one complete original sentence <=90 characters; no full API body','interval_seconds':5.5}),flush=True)
    if not execute:return
    baseline(store)
    run_key=f'expansion-kokkai-{year}-start-{start_record}'
    rid=start_run(store,run_key,{'url':url,'selection':'20 API records; unseen IDs with complete <=90-character 日韓 sentence; not representative'},resume=True)
    qkey=queue_item(store,rid,api.source,url)
    done=store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,qkey)).fetchone()[0]
    if done=='query_completed':
        checkpoint=store.db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(run_key+'-checkpoint',)).fetchone()
        finish_run(store,rid)
        return json.loads(checkpoint[0]).get('next_record') if checkpoint else None
    if done.endswith('_error'):
        previous=store.db.execute('SELECT error FROM collection_items WHERE run_id=? AND item_key=?',(rid,qkey)).fetchone()[0] or ''
        corrected_anchor_error='NoneType' in previous and 'start' in previous
        allowed=retry_errors and ('timed out' in previous.lower() or 'TimeoutExpired' in previous or corrected_anchor_error) and not re.search(r'HTTP\s*(401|403|429)',previous)
        if not allowed:
            finish_run(store,rid,'completed_with_errors')
            raise AccessBlocked('Prior query failed; only explicit --retry-errors after a transport timeout is permitted; server/robots denials are never overridden')
    client=Client(store,'windows',hosts={api.host},retain_body=False)
    try:
        try:client.check_robots(url)
        except AccessBlocked:
            last=store.db.execute("SELECT status,headers_json FROM fetches WHERE url='https://kokkai.ndl.go.jp/robots.txt' ORDER BY id DESC LIMIT 1").fetchone()
            h={k.lower():v for k,v in json.loads(last[1]).items()} if last else {}
            if not last or last[0] not in (301,302,303,307,308) or h.get('location')!='https://kokkai.ndl.go.jp/':raise
        status,headers,body,raw=client.request(url)
        if status in (401,403,429):raise AccessBlocked(f'HTTP {status}; no retry')
        if status!=200 or 'json' not in headers.get('content-type',''):raise ValueError('Expected documented API JSON')
        original=json.loads(body);byid={r['speechID']:r for r in original.get('speechRecord',[])}
        added=0;repeated=0
        for doc,st in api.parse(body):
            if store.db.execute('SELECT 1 FROM documents WHERE source=? AND official_id=?',(api.source,doc.official_identifier)).fetchone():continue
            if byid[doc.official_identifier].get('speakerRole') in ('参考人','公述人','証人'):continue
            sentence=complete_quote(byid[doc.official_identifier]['speech'])
            if not sentence:continue
            doc=replace(doc,text=sentence,observation_type='parliamentary_speech_excerpt',text_completeness='complete_sentence_partial_speech',
                analysis_status='source_quote_verified_context_needs_review',verification_status='needs_review',country_scope='JPN',
                institution=st.institution,observation_addressee='ROK: topic, direct recipient not established',theme=st.theme,
                rights_evidence='https://kokkai.ndl.go.jp/api.html section 4; quotation restriction; speakers retain rights')
            st=replace(st,quotes=(Quote(sentence,'ja','ja','original_excerpt','speechID='+doc.official_identifier+'; complete sentence'),))
            item=queue_item(store,rid,api.source,doc.url)
            outcome=ingest(store,doc,raw,[st],rid,item)
            before=counts(store.db)
            again=ingest(store,doc,raw,[st])
            assert again['documents_added']==again['statements_added']==again['quotes_added']==0
            # Literal provenance confirmed; political relevance remains needs_review.
            with store.db:
                store.db.execute("UPDATE quotes SET verification_status='source_text_verified' WHERE id IN (SELECT quote_id FROM quote_sources WHERE document_id=?)",(outcome['document_id'],))
            added+=outcome['documents_added'];repeated+=1
            if added>=20:break
        with store.db:
            store.db.execute("UPDATE collection_items SET status='query_completed',error=?,updated_at=? WHERE run_id=? AND item_key=?",(json.dumps({'next_record':original.get('nextRecordPosition'),'query_total':original.get('numberOfRecords')}),now(),rid,qkey))
            store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
              (api.source,url,now(),status,json.dumps({'new_documents':added,'complete_short_quotes':repeated,'speaker_filter':None,'full_speech_retained':False}),raw[1]))
        finish_run(store,rid)
        checkpoint={'new_documents':added,'repeat_passed':repeated,'query_total':original.get('numberOfRecords'),'next_record':original.get('nextRecordPosition'),'full_speech_retained':False,
          'mandatory_missing':store.db.execute("SELECT count(*) FROM collection_items i JOIN documents d ON d.id=i.document_id WHERE i.run_id=? AND (coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')) IS NULL OR d.language IS NULL OR d.url='' OR d.text='')",(rid,)).fetchone()[0],
          'theme_distribution':store.db.execute("SELECT s.theme,count(*) FROM collection_items i JOIN statement_sources ss ON ss.document_id=i.document_id JOIN statements s ON s.id=ss.statement_id WHERE i.run_id=? GROUP BY 1",(rid,)).fetchall(),
          'year_country_distribution':store.db.execute("SELECT substr(s.spoken_date,1,4),s.country,s.target_country,count(*) FROM collection_items i JOIN statement_sources ss ON ss.document_id=i.document_id JOIN statements s ON s.id=ss.statement_id WHERE i.run_id=? GROUP BY 1,2,3",(rid,)).fetchall()}
        finish_run(store,start_run(store,run_key+'-checkpoint',checkpoint,resume=True))
        store.export();print(json.dumps({'year':year,'new_documents':added,'repeat_passed':repeated}),flush=True)
        return original.get('nextRecordPosition')
    except Exception as error:
        store.error(api.source,url,'expansion_kokkai',error)
        with store.db:store.db.execute("UPDATE collection_items SET status='access_error',error=?,updated_at=? WHERE run_id=? AND item_key=?",(str(error),now(),rid,qkey))
        finish_run(store,rid,'completed_with_errors');raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--year',type=int)
    p.add_argument('--pages',type=int,default=1);p.add_argument('--start-record',type=int)
    p.add_argument('--start-year',type=int);p.add_argument('--retry-errors',action='store_true')
    a=p.parse_args();years=[a.year] if a.year else range(a.start_year or 2015,2027)
    if any(not 2015<=y<=2026 for y in years):p.error('year 2015..2026')
    if not 1<=a.pages<=5 or (a.start_record is not None and a.start_record<1):p.error('pages 1..5; start-record >=1')
    s=Store()
    try:
        if a.year is None and a.start_year is None:
            failed=s.db.execute("SELECT run_key FROM collection_runs WHERE run_key LIKE 'expansion-kokkai-%-start-%' AND status='completed_with_errors' ORDER BY id DESC LIMIT 1").fetchone()
            if failed:years=range(int(failed[0].split('-')[2]),2027)
        for year in years:
            start=a.start_record
            if start is None:
                saved=s.db.execute('SELECT config_json FROM collection_runs WHERE run_key LIKE ? ORDER BY id DESC LIMIT 1',(f'expansion-kokkai-{year}-start-%-checkpoint',)).fetchone()
                start=json.loads(saved[0]).get('next_record') if saved else 1
                if not start:continue
            for _ in range(a.pages):
                start=collect(s,year,a.execute,int(start),a.retry_errors)
                if not start:break
    finally:s.db.close()
if __name__=='__main__':main()
