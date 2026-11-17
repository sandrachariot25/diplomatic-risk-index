"""Audit existing records only. No network, LLM or new source collection."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.research import records,stratified_sample
from dri.corpus_audit import audit

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan',action='store_true')
    args=p.parse_args()
    if args.plan:
        db=sqlite3.connect((ROOT/'data/dri.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            rows=records(db)
            sample=stratified_sample(rows)
            print(json.dumps({'network_requests':0,'documents':db.execute('SELECT count(*) FROM documents').fetchone()[0],
                  'statements':len(rows),'sample_ids':[r['id'] for r in sample],'sample_size':len(sample),
                  'migration':'2->3, one pre-schema-003 backup; additive audit metadata, no deletion/merge'}))
        finally:db.close()
        return
    store=Store()
    try:print(json.dumps(audit(store),ensure_ascii=True))
    finally:store.db.close()

if __name__=='__main__':main()
