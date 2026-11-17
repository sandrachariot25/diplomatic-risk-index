"""Bounded, resumable collection; dry run is the default. No API keys required."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.storage import Store, now
from dri.http import Client, AccessBlocked
from dri.repository import register_sources, start_run, queue_item, ingest, finish_run
from dri.connectors.korea_government import parse

RECORDS = [
    dict(id='132038430', route='speechView', name='이재명', role='대통령',
         theme='diplomatic_contacts', addressee='Prime Minister Takaichi and Japanese public',
         evidence='Name in title; speaker role and speech date explicitly labelled.'),
    dict(id='132037781', route='speechView', name=None, role='대통령',
         theme='regional_cooperation', addressee='Korean community in Japan',
         evidence='Personal name not established from page; no historical office-holder inference.'),
    dict(id='148974237', route='presidentView', name='김성완', role='대변인',
         theme='trade_economy', addressee='Public; Japan business delegation is topic',
         evidence='Signed spokesperson written briefing in title; president reported indirectly.'),
    dict(id='148950259', route='presidentView', name='강유정', role='대변인',
         theme='diplomatic_contacts', addressee='Public; Japan summit is topic',
         evidence='Spokesperson briefing explicitly labelled in title; not president oral speech.'),
]
for r in RECORDS:
    r['institution']='Presidential administration, Republic of Korea'
    r['url']='https://www.korea.kr/briefing/'+r['route']+'.do?newsId='+r['id']

EARLIER_RECORDS=[dict(id='148870027',route='presidentView',name=None,role=None,
    institution='Presidential administration, Republic of Korea',
    theme='diplomatic_contacts',addressee='Domestic public and media; Japan entry restrictions are topic',
    evidence='Institution 청와대 in publication header; personal author not inferred.',
    url='https://www.korea.kr/briefing/presidentView.do?newsId=148870027')]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--restricted-research', action='store_true')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--batch', choices=('pilot','earlier'), default='pilot')
    args=ap.parse_args()
    records=RECORDS if args.batch=='pilot' else EARLIER_RECORDS
    print(json.dumps(dict(network_plan=[r['url'] for r in records], interval_seconds=5.5,
                         retention='text only, item licence checked; no photos/attachments',
                         restricted_research=args.restricted_research, execute=args.execute)), flush=True)
    if not args.execute:return
    store=Store(); register_sources(store)
    config={'records':records, 'restricted_research':args.restricted_research}
    run=start_run(store,'domestic-20261101'+('' if args.batch=='pilot' else '-earlier'),config,resume=args.resume)
    client=Client(store,'windows',hosts={'www.korea.kr'},retain_body=False)
    for r in records:
        key=queue_item(store,run,'korea_government_kr',r['url'])
        status=store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(run,key)).fetchone()[0]
        if status=='processed':continue
        if store.db.execute('SELECT 1 FROM document_aliases WHERE source=? AND normalized_url=?',('korea_government_kr',r['url'])).fetchone():
            raise ValueError('Existing document without this checkpoint; review before refetch')
        try:
            html,raw,url=client.get(r['url'])
            doc,statements=parse(html,url,r,restricted_research=args.restricted_research)
            # Retain only the licensed text; raw HTML includes unlicensed media/UI.
            ref=store.record_fetch(url,200,{'X-DRI-Retention':'licensed extracted text only'},doc.text.encode('utf-8'))
            result=ingest(store,doc,ref,statements,run,key)
            before=[store.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','statements','quotes')]
            replay=ingest(store,doc,statements=statements)
            after=[store.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','statements','quotes')]
            if before!=after:raise AssertionError('Repeat import added entities')
            with store.db:
                store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                    (doc.source,url,now(),200,json.dumps({'import':result,'replay':replay,'field_check':{'dated':True,'named':bool(doc.author)},'theme':doc.theme}),ref[1]))
            finish_run(store,run,'running')
            print(json.dumps(result),flush=True)
        except Exception as error:
            store.error('korea_government_kr',r['url'],'domestic_collection',error)
            with store.db:
                store.db.execute('UPDATE collection_items SET status=?,error=?,updated_at=? WHERE run_id=? AND item_key=?',
                    ('access_error' if isinstance(error,AccessBlocked) else 'parse_error',str(error),now(),run,key))
            print(type(error).__name__+': '+str(error),flush=True)
            if isinstance(error,AccessBlocked):break
    counters=finish_run(store,run,'completed' if not store.db.execute("SELECT 1 FROM collection_items WHERE run_id=? AND status!='processed'",(run,)).fetchone() else 'partial')
    print(json.dumps(counters),flush=True)
    store.db.close()

if __name__=='__main__':main()
