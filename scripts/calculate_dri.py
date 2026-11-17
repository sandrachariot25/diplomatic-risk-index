"""One reproducible, offline DRI v0.1 calculation against the existing read-only DB."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT
from dri.analytics import calculate
from dri.analytical_sample import digest,load_sample
from dri.analytics_outputs import write_outputs
from dri.tokenization import Segmenter,prepare
from dri.rhetoric import Matcher

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--verify-reproducibility',action='store_true')
    ap.add_argument('--explain',type=int,help='Internal terminal-only source/token inspection; no artifacts written')
    args=ap.parse_args()
    config=json.loads((ROOT/'config/dri_v01.json').read_text(encoding='utf-8'))
    lexicon=json.loads((ROOT/config['lexicon']).read_text(encoding='utf-8'))
    db=ROOT/'data/dri.sqlite3'
    if args.explain is not None:
        units,_=load_sample(db);unit=next((u for u in units if args.explain in u['statement_ids']),None)
        if unit is None:raise ValueError('Statement not present in saved database')
        segmenter=Segmenter();matcher=Matcher(lexicon,segmenter)
        print(json.dumps({'internal_only':True,'unit_id':unit['unit_id'],'exclusion':unit['exclusion_reason']},ensure_ascii=False))
        for f in unit['fragments']:
            ts,ms=matcher.match(f['text'],unit['language'],unit['target_country'])
            print(json.dumps({'source_ref':f['ref'],'analysis_text':prepare(f['text']),
                'tokens':[asdict(t) for t in ts],'matches':ms},ensure_ascii=False))
        return
    result=calculate(db,config,lexicon);reproduced=False
    if args.verify_reproducibility:
        again=calculate(db,config,lexicon)
        if digest(result)!=digest(again):raise AssertionError('Calculation differs on the same snapshot')
        reproduced=True
    write_outputs(result,config,lexicon,reproduced)
    print(json.dumps({k:v for k,v in result['summary'].items() if k not in {'lengths','coverage_by_year'}},ensure_ascii=False))

if __name__=='__main__':main()
