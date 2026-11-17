"""Bounded public archive fetching; repeat runs reuse verified cached responses."""
import argparse,json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dri.storage import Store,now
from dri.http import Client,windows_get,AccessBlocked,CAP
from dri.identity import fingerprint
from dri.repository import start_run,finish_run,queue_item
from dri.connectors.gdelt_archive import rows_from_zip

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--timestamps',default='20151228120000,20190802000000,20200615120000,20250823120000')
    p.add_argument('--kinds',default='events,mentions')
    p.add_argument('--gkg-max-bytes',type=int,default=CAP)
    p.add_argument('--execute',action='store_true')
    a=p.parse_args();timestamps=a.timestamps.split(',');kinds=a.kinds.split(',')
    mapping={'events':('export.CSV.zip',61),'mentions':('mentions.CSV.zip',16),'gkg':('gkg.csv.zip',27)}
    if not 1<=len(timestamps)*len(kinds)<=12 or any(k not in mapping for k in kinds):p.error('1..12 archives; kinds events,mentions,gkg')
    if not CAP<=a.gkg_max_bytes<=16_000_000:p.error('GKG cap 4000000..16000000')
    for t in timestamps:
        dt=datetime.strptime(t,'%Y%m%d%H%M%S')
        if not '20150219000000'<=t<='20261030235959' or dt.minute not in (0,15,30,45) or dt.second!=0:p.error('Valid 15-minute interval within verified 2015-02-19..2026-10-30')
    files=[('https://data.gdeltproject.org/gdeltv2/'+t+'.'+mapping[k][0],k) for t in timestamps for k in kinds]
    config={'timestamps':timestamps,'kinds':kinds,'gkg_max_bytes':a.gkg_max_bytes}
    print(json.dumps({'plan':files,'robots':True,'interval_seconds':5.5,'skip_cached':True,'stop_on_denial_or_error':True,'article_requests':0,'gkg_cap':a.gkg_max_bytes}),flush=True)
    if not a.execute:return
    s=Store();client=Client(s,'windows',hosts={'data.gdeltproject.org'},retain_body=True)
    rid=start_run(s,'expansion-gdelt-fetch-'+fingerprint(config)[:16],config,resume=True)
    state='completed'
    try:
        for url,kind in files:
            item=queue_item(s,rid,'gdelt',url)
            cached=s.db.execute('SELECT raw_path,sha256 FROM fetches WHERE url=? AND status=200 AND raw_path IS NOT NULL ORDER BY id DESC LIMIT 1',(url,)).fetchone()
            try:
                if cached:
                    data=(s.root/cached[0]).read_bytes()
                    if hashlib.sha256(data).hexdigest()!=cached[1]:raise ValueError('Cache hash mismatch; no automatic re-fetch')
                    print(json.dumps({'url':url,'cached':True}),flush=True)
                else:
                    client.transport=lambda u:windows_get(u,max_bytes=a.gkg_max_bytes if kind=='gkg' else CAP)
                    client.check_robots(url);status,headers,data,raw=client.request(url)
                    if status in (401,403,429):raise AccessBlocked(f'HTTP {status}; source stopped')
                    if status!=200:raise OSError(f'HTTP {status}')
                parsed=rows_from_zip(data,mapping[kind][1])
                with s.db:s.db.execute("UPDATE collection_items SET status='query_completed',updated_at=? WHERE run_id=? AND item_key=?",(now(),rid,item))
                print(json.dumps({'url':url,'rows':len(parsed),'schema_validated':True}),flush=True)
            except Exception as e:
                s.error('gdelt',url,'gdelt_archive_fetch',e)
                with s.db:s.db.execute("UPDATE collection_items SET status='access_error',error=?,updated_at=? WHERE run_id=? AND item_key=?",(str(e),now(),rid,item))
                state='completed_with_errors';break
    finally:finish_run(s,rid,state);s.db.close()
    return int(state!='completed')

if __name__=='__main__':raise SystemExit(main() or 0)
