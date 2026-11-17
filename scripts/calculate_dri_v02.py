"""Offline v0.2; refuse mismatch with the preserved v0.1 input snapshot."""
import argparse
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT
from dri.analytical_sample import digest
from dri.contextual_index import calculate_v02,compare_v01
from dri.contextual_outputs import write_v02
from dri.analytics_outputs import file_sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify-reproducibility',action='store_true');args=ap.parse_args()
    config=json.loads((ROOT/'config/dri_v02.json').read_text(encoding='utf-8'))
    rules=json.loads((ROOT/config['rules']).read_text(encoding='utf-8'))
    db=ROOT/'data/dri.sqlite3';db_sha=file_sha(db)
    preserved={str(p.relative_to(ROOT)):file_sha(p) for p in (ROOT/'data').glob('dri_v01_*')}
    preserved.update({str(p.relative_to(ROOT)):file_sha(p) for p in (ROOT/'docs').glob('DRI_v01*.png')})
    result,private=calculate_v02(db,config,rules);reproduced=False
    v01=json.loads((ROOT/'data/dri_v01_manifest.json').read_text(encoding='utf-8'))
    if result['summary']['core_input_sha256']!=v01['summary']['core_input_sha256']:raise ValueError('Existing v0.1 snapshot differs; refresh it explicitly before comparison')
    if args.verify_reproducibility:
        again,again_private=calculate_v02(db,config,rules)
        if digest(result)!=digest(again) or digest(private)!=digest(again_private):raise AssertionError('Non-reproducible calculation')
        reproduced=True
    v01_units=[json.loads(line) for line in (ROOT/'data/dri_v01_units.jsonl').read_text(encoding='utf-8').splitlines()]
    with (ROOT/'data/dri_v01_monthly.csv').open(encoding='utf-8',newline='') as f:old=list(csv.DictReader(f))
    for r in old:r['raw_rate_per_1000']=float(r['raw_rate_per_1000']) if r['raw_rate_per_1000'] else None
    comparison=compare_v01(result,v01_units,old,config)
    write_v02(result,private,comparison,config,rules,reproduced)
    if db_sha!=file_sha(db) or any(file_sha(ROOT/p)!=sha for p,sha in preserved.items()):raise AssertionError('DB or v0.1 changed')
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
