"""One official speech query per year, sequential, bounded excerpts only."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.connectors.kokkai import Kokkai
from dri.http import Client,AccessBlocked
from dri.storage import Store,now
from dri.repository import register_sources,start_run,queue_item,ingest,finish_run,normalize_legacy_fingerprint

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--execute',action='store_true')
    ap.add_argument('--year',type=int)
    ap.add_argument('--start-year',type=int,default=2015)
    ap.add_argument('--per-year',type=int,default=6)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--run-key')
    ap.add_argument('--retry-errors',action='store_true')
    ap.add_argument('--query',default='韓国')
    ap.add_argument('--focus-theme',choices=['normalization_deescalation','regional_cooperation'])
    ap.add_argument('--speaker-position',default=None,help='Optional explicit filter; default includes all roles, including MPs and opposition')
    args=ap.parse_args()
    api=Kokkai();years=[args.year] if args.year else list(range(args.start_year,2027))
    if not years or not 2015<=args.start_year<=2026:ap.error('start-year must be 2015..2026')
    urls=[api.request_url(y,query=args.query,speaker_position=args.speaker_position) for y in years]
    print(json.dumps({'network_plan':urls,'retention':'at most 90 original Japanese characters per selected speech, no response body','per_year':args.per_year}),flush=True)
    if not args.execute:return
    if not 1<=args.per_year<=10:ap.error('per-year 1..10')
    store=Store();register_sources(store)
    with store.db:
        store.db.execute('''INSERT INTO sources(id,name,country,source_type,base_url,terms_url,access_status,content_policy,audit_json)
          VALUES('kokkai_jp','National Diet Library speech transcripts','JPN','primary','https://kokkai.ndl.go.jp',
          'https://kokkai.ndl.go.jp/api.html','documented_api','excerpt_only',?) ON CONFLICT(id) DO NOTHING''',
          (json.dumps({'reliability':'official_parliamentary_record','publication_date':'not supplied by speech API'}),))
    key=args.run_key or ('kokkai-inclusive-pilot-' if args.speaker_position is None else 'kokkai-pilot-')+str(args.year or f'{args.start_year}-2026')
    config={'years':years,'per_year':args.per_year}
    if args.speaker_position!='大臣':config['speaker_position']=args.speaker_position
    if args.query!='韓国' or args.focus_theme:config.update(query=args.query,focus_theme=args.focus_theme)
    rid=start_run(store,key,config,args.resume)
    client=Client(store,'windows',hosts={api.host},retain_body=False)
    state='completed'
    try:
        for year,url in zip(years,urls):
            qkey=queue_item(store,rid,api.source,url)
            qstate=store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,qkey)).fetchone()[0]
            if qstate=='query_completed' or (qstate.endswith('_error') and not args.retry_errors):continue
            try:
                # Same policy as HTML transport, JSON content validation is specific to this API.
                try:
                    client.check_robots(url)
                except AccessBlocked:
                    # robots redirects to the site's home, not an access denial. The official
                    # API spec expressly authorises sequential automated API use without signup.
                    # Permit ONLY the documented speech endpoint on this exact condition;
                    # 401/403/429 and actual robots Disallow never receive this exception.
                    last=store.db.execute("SELECT status,headers_json FROM fetches WHERE url='https://kokkai.ndl.go.jp/robots.txt' ORDER BY id DESC LIMIT 1").fetchone()
                    h={k.lower():v for k,v in json.loads(last[1]).items()} if last else {}
                    if not last or last[0] not in (301,302,303,307,308) or h.get('location')!='https://kokkai.ndl.go.jp/' or not url.startswith(api.endpoint+'?'):
                        raise
                    with store.db:
                        store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result) VALUES(?,?,?,?,?)',
                          (api.source,'https://kokkai.ndl.go.jp/api.html',now(),None,'Explicit official API automation permission; robots redirects to homepage, no Disallow read; exact /api/speech only, sequential >=5.5s'))
                status,headers,body,raw=client.request(url)
                if status in {401,403,429}:raise AccessBlocked(f'HTTP {status}; source stopped without retry')
                if status!=200 or 'json' not in headers.get('content-type','').lower():raise ValueError(f'Expected API JSON, HTTP {status}')
                pairs=api.parse(body,args.focus_theme)
                if args.focus_theme:
                    pairs=[(d,s) for d,s in pairs if not store.db.execute('SELECT 1 FROM documents WHERE source=? AND official_id=?',(api.source,d.official_identifier)).fetchone()]
                pairs=pairs[:args.per_year]
                for doc,st in pairs:
                    normalize_legacy_fingerprint(store,doc)
                    ikey=queue_item(store,rid,api.source,doc.url)
                    if store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,ikey)).fetchone()[0]=='processed':continue
                    print(json.dumps({'year':year,'speech':doc.official_identifier,**ingest(store,doc,raw,[st],rid,ikey)}),flush=True)
                with store.db:
                    store.db.execute("UPDATE collection_items SET status='query_completed',updated_at=? WHERE run_id=? AND item_key=?",(now(),rid,qkey))
                    store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                       (api.source,url,now(),status,f'validated speech JSON; {len(pairs)} selected for year {year}',raw[1]))
            except Exception as e:
                with store.db:store.db.execute("UPDATE collection_items SET status='access_error',error=?,updated_at=? WHERE run_id=? AND item_key=?",(str(e)[:2000],now(),rid,qkey))
                store.error(api.source,url,'kokkai',e);print(json.dumps({'year':year,'error':str(e)[:300]}),flush=True)
                state='completed_with_errors';break
    except BaseException:
        state='interrupted';raise
    finally:
        print(json.dumps({'run_id':rid,'counters':finish_run(store,rid,state)}),flush=True)
        store.export();store.db.close()

if __name__=='__main__':main()
