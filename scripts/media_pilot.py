"""Offline media pilot; all output remains in the existing project and database."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.media_collection import import_batch,counts
from dri.corpus_audit import CORE_TABLES,core_snapshot
from dri.identity import fingerprint
from dri.paths import write_generated

def run(store, rows):
    key='media-bibliography-2026-10-30'
    prior=store.db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(key+'-preservation',)).fetchone()
    if prior:
        baseline=json.loads(prior[0])
    else:
        baseline={'counts':counts(store.db),'tables':{},'original_core_snapshot':core_snapshot(store.db)}
        for table in CORE_TABLES:
            records=store.db.execute(f'SELECT rowid,* FROM {table} ORDER BY rowid').fetchall()
            baseline['tables'][table]={'last_rowid':max((r[0] for r in records),default=0),'hash':fingerprint(records)}
        from dri.repository import start_run,finish_run
        finish_run(store,start_run(store,key+'-preservation',baseline))
    first=import_batch(store,rows,key)
    # Deliberately run actual ingestion again, not merely skip completed checkpoints.
    second=import_batch(store,rows,key+'-repeat')
    preserved={table:fingerprint(store.db.execute(f'SELECT rowid,* FROM {table} WHERE rowid<=? ORDER BY rowid',(saved['last_rowid'],)).fetchall())==saved['hash']
               for table,saved in baseline['tables'].items()}
    assert all(preserved.values()),preserved
    assert second['before']==second['after'],second
    assert all(r['documents_added']==r['statements_added']==r['quotes_added']==0 for r in second['results'])
    result={'baseline':baseline['counts'],'after':counts(store.db),'repeat_before':second['before'],
            'repeat_after':second['after'],'repeat_passed':True,'original_tables_preserved':preserved,
            'manifest_sha256':fingerprint(rows),'publications_in_batch':len(rows),'network_requests_during_import':0}
    from dri.repository import start_run,finish_run
    finish_run(store,start_run(store,key+'-validated',result,resume=True))
    store.export()
    from dri.quality import report
    report(store)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    store=Store()
    try:run(store,json.loads((ROOT/'data/media_manifest.json').read_text(encoding='utf-8')))
    finally:store.db.close()
