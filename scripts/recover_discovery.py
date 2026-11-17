"""Recover the actual interrupted discovery from committed logs; no networking."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.storage import Store,now
from dri.repository import start_run,queue_item,finish_run

def main():
    store=Store()
    try:
        rows=store.db.execute("SELECT normalized_url,title,discovered_at FROM discovery_results WHERE source_id='mofa_kr' ORDER BY id").fetchall()
        manifest=[{'source':'mofa_kr','url':url,'title':title} for url,title,stamp in rows if any(t in title.casefold() for t in ('commentary','statement'))]
        path=ROOT/'data/pilot_manifest.json'
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8'))
            if old!=manifest:raise RuntimeError('Existing manifest differs; inspect before replacing')
        else:path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        rid=start_run(store,'korea-discovery-recovered-from-logs',{'recovery':'Actual search interrupted intentionally before document collection; links recovered from committed discovery_results'},resume=True)
        for url,title,stamp in rows:
            key=queue_item(store,rid,'mofa_kr',url)
            with store.db:store.db.execute("UPDATE collection_items SET status='discovered',updated_at=? WHERE run_id=? AND item_key=?",(stamp,rid,key))
        finish_run(store,rid,'interrupted_recovered')
        print(json.dumps({'discovered_urls':len(rows),'statement_document_candidates':len(manifest),'manifest':str(path)}))
    finally:store.db.close()

if __name__=='__main__':main()
