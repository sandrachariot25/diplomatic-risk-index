"""Bounded official pilot discovery and collection. One manifest and primary DB."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.collection import discover_korea, collect_manifest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pages',type=int,default=90)
    ap.add_argument('--target',type=int,default=150)
    ap.add_argument('--execute',action='store_true')
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--discovery-only',action='store_true')
    ap.add_argument('--collect-only',action='store_true')
    ap.add_argument('--run-key',default='official-pilot-2015-2026')
    args=ap.parse_args()
    if not 1<=args.pages<=120 or not 1<=args.target<=200:ap.error('Bounded pilot: pages 1..120, target 1..200')
    print(json.dumps({'network_plan':{'max_index_pages':args.pages,'max_documents':args.target,'source':'mofa_kr',
                      'retention':'metadata + max 25 words; no new full texts'},'execute':args.execute}),flush=True)
    if not args.execute:return
    store=Store()
    try:
        if not args.collect_only:discover_korea(store,pages=args.pages,execute=True)
        if not args.discovery_only:
            path=ROOT/'data/pilot_manifest.json'
            manifest=json.loads(path.read_text(encoding='utf-8'))[:args.target] if path.exists() else []
            if not manifest:
                print('No confirmed statement document links discovered; no synthetic records created',flush=True)
                return
            collect_manifest(store,manifest,args.run_key,transport='windows',resume=args.resume)
    finally:store.db.close()

if __name__=='__main__':main()
