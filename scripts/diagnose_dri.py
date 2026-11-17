"""Reproduce existing DRI and replace its completeness section, entirely offline."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT
from dri.analytics import calculate
from dri.analytical_sample import digest
from dri.analytical_diagnostics import diagnose

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify-reproducibility',action='store_true');args=ap.parse_args()
    config=json.loads((ROOT/'config/dri_v01.json').read_text(encoding='utf-8'))
    lexicon=json.loads((ROOT/config['lexicon']).read_text(encoding='utf-8'))
    result=calculate(ROOT/'data/dri.sqlite3',config,lexicon)
    manifest=json.loads((ROOT/'data/dri_v01_manifest.json').read_text(encoding='utf-8'))
    if digest(result)!=manifest['result_sha256']:raise RuntimeError('Recalculate existing artifacts first; diagnostics must describe the same snapshot')
    reproduced=False
    if args.verify_reproducibility:
        if digest(result)!=digest(calculate(ROOT/'data/dri.sqlite3',config,lexicon)):raise AssertionError('Non-reproducible result')
        reproduced=True
    report=diagnose(result,config,reproduced)
    print(json.dumps({k:report[k] for k in ('documents','checks','components')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
