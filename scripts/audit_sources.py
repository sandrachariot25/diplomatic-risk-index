"""Small live robots/root checks; copyright-protected page bodies are not persisted."""
import argparse
import hashlib
import json
import sys
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.storage import Store, now
from dri.repository import register_sources
from dri.http import windows_get, USER_AGENT

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--execute',action='store_true')
    args=ap.parse_args()
    rows=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
    print('PLAN: sequential robots and allowed root checks; >=5.5s; stop on denial; page bodies not retained',flush=True)
    if not args.execute:
        print(json.dumps([r['base_url'] for r in rows])); return
    store=Store(); register_sources(store)
    try:
        for row in rows:
            if row['id'] in {'mofa_jp','gdelt'}:
                continue  # Previously denied hosts are not retried.
            existing=store.db.execute('SELECT 1 FROM source_checks WHERE source_id=?',(row['id'],)).fetchone()
            if existing:
                continue
            url=row['base_url']+'/robots.txt'
            status=None
            try:
                status,headers,body=windows_get(url)
                digest=hashlib.sha256(body).hexdigest()
                store.record_fetch(url,status,headers,body,retain_body=False)
                parser=RobotFileParser()
                if status==200 and b'<html' not in body.lower():
                    parser.parse(body.decode('utf-8-sig').splitlines())
                    allowed=parser.can_fetch(USER_AGENT,row['base_url']+'/')
                    result='root_allowed_by_robots' if allowed else 'root_disallowed_by_robots'
                elif status in {404,410}:
                    allowed=True; result='robots_absent'
                else:
                    allowed=False; result=f'robots_unavailable_{status}'
                with store.db:
                    store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                                     (row['id'],url,now(),status,result,digest))
                if allowed:
                    delay=max(5.5,parser.crawl_delay(USER_AGENT) or 0)
                    time.sleep(delay)
                    url=row['base_url']+'/'
                    status,headers,body=windows_get(url)
                    store.record_fetch(url,status,headers,body,retain_body=False)
                    result=f'root_http_{status}; document access and licence not established'
                    with store.db:
                        store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                                         (row['id'],url,now(),status,result,hashlib.sha256(body).hexdigest()))
            except Exception as error:
                result=f'{type(error).__name__}: {error}'
                with store.db:
                    store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result) VALUES(?,?,?,?,?)',
                                     (row['id'],url,now(),status,result[:2000]))
            print(json.dumps({'source':row['id'],'status':status,'result':result},ensure_ascii=True),flush=True)
            time.sleep(5.5)
    finally:
        store.db.close()

if __name__=='__main__': main()
