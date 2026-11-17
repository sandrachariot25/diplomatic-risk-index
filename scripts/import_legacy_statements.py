"""Backfill statement entities from preserved legacy evidence without fetching or replacing it."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.models import Document
from dri.collection import retained
from dri.repository import register_sources, start_run, queue_item, ingest, finish_run
from dri.statements import extract_korean_institutional

def main():
    store=Store();register_sources(store)
    try:
        rid=start_run(store,'legacy-statement-backfill',{'purpose':'preserve legacy documents; add short-evidence statement entities'},resume=True)
        rows=store.db.execute("SELECT metadata_json FROM documents WHERE content_policy='legacy_unreviewed'").fetchall()
        for (metadata,) in rows:
            full=Document(**json.loads(metadata))
            doc=retained(full)
            key=queue_item(store,rid,doc.source,doc.url)
            existing=store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,key)).fetchone()[0]
            linked=store.db.execute('SELECT 1 FROM statement_sources ss JOIN documents d ON d.id=ss.document_id WHERE d.url=?',(doc.url,)).fetchone()
            if existing=='processed' and linked:continue
            print(json.dumps(ingest(store,doc,None,extract_korean_institutional(doc),rid,key)))
        print(json.dumps(finish_run(store,rid)))
        store.export()
    finally:store.db.close()

if __name__=='__main__':main()
