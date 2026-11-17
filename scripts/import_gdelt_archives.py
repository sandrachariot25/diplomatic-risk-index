"""Reuse fetched official archives, without re-downloading or fetching news articles."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.repository import start_run,finish_run,queue_item
from dri.connectors.gdelt_archive import events,mentions,gkg,save_records
from dri.identity import fingerprint

def main():
    s=Store() # controlled migration with pre-schema backup, only if needed
    try:
        files=s.db.execute("SELECT url,raw_path,sha256 FROM fetches WHERE status=200 AND raw_path IS NOT NULL AND url LIKE 'https://data.gdeltproject.org/gdeltv2/%.zip' ORDER BY id").fetchall()
        files=[list(r) for r in dict.fromkeys(files)]
        tables=('gdelt_events','gdelt_mentions','gdelt_gkg')
        before={t:s.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
        batch_key='expansion-gdelt-archives-'+fingerprint(files)[:16]
        prior=s.db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(batch_key+'-validation',)).fetchone()
        original_before=json.loads(prior[0])['before'] if prior else before
        rid=start_run(s,batch_key,{'files':files,'filter':'CAMEO KOR/JPN; GKG FIPS KS+JA cooccurrence separate'},resume=True)
        for kind,parser,table in (('.export.',events,'gdelt_events'),('.mentions.',mentions,'gdelt_mentions'),('.gkg.',gkg,'gdelt_gkg')):
            for url,path,sha in files:
                if kind not in url:continue
                body=(s.root/path).read_bytes()
                if hashlib.sha256(body).hexdigest()!=sha:raise ValueError('Archive hash mismatch')
                rows=parser(body,{r[0] for r in s.db.execute('SELECT event_id FROM gdelt_events')}) if table=='gdelt_mentions' else parser(body)
                added=save_records(s,table,rows,url,sha)
                assert save_records(s,table,rows,url,sha)==0
                key=queue_item(s,rid,'gdelt',url)
                from dri.storage import now
                with s.db:s.db.execute("UPDATE collection_items SET status='query_completed',error=?,updated_at=? WHERE run_id=? AND item_key=?",(json.dumps({'table':table,'selected':len(rows),'added':added,'repeat_passed':True}),now(),rid,key))
                print(json.dumps({'archive':url,'table':table,'selected':len(rows),'added':added,'repeat_passed':True}),flush=True)
        after={t:s.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
        finish_run(s,rid)
        finish_run(s,start_run(s,batch_key+'-validation',{'before':original_before,'after':after,'no_speech_entities_created':True},resume=True))
        print(json.dumps({'before':before,'after':after,'foreign_key_errors':s.db.execute('PRAGMA foreign_key_check').fetchall()}))
    except Exception as e:
        s.error('gdelt',None,'gdelt_archive_import',e);raise
    finally:s.db.close()

if __name__=='__main__':main()
