"""Freeze one expert set and author one blind XLSX; never overwrite human edits."""
import argparse,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT
from dri.expert_review import prepare_review,WORKBOOK,read_xlsx,EXPERT_COLUMNS,col_name,update_documentation

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-only',action='store_true');ap.add_argument('--rebuild-blank',action='store_true');args=ap.parse_args()
    registry,payload=prepare_review()
    if not args.data_only:
        build=not WORKBOOK.exists()
        if WORKBOOK.exists() and args.rebuild_blank:
            book=read_xlsx(WORKBOOK)
            if any(value is not None and str(value).strip() for key,value in book['Разметка'].items()
                   if int(''.join(c for c in key if c.isdigit()))>1 and ''.join(c for c in key if c.isalpha()) in {col_name(i+1) for i in EXPERT_COLUMNS}):
                raise ValueError('Expert entries exist; workbook must not be overwritten')
            build=True
        if build:
            node=Path(sys.base_prefix).parent/'node/bin/node.exe'
            if not node.exists():raise RuntimeError('Bundled Node runtime is unavailable; no dependency installation attempted')
            subprocess.run([str(node),str(ROOT/'scripts/build_expert_review.mjs')],cwd=ROOT,check=True)
    update_documentation(registry)
    print(json.dumps({'sample_id':registry['sample_id'],'size':len(registry['records']),
        'seed_ids_retained':len(registry['baseline_32_ids']),'annotations':len(registry['annotations']),
        'composition':registry['composition'],'workbook_exists':WORKBOOK.exists()},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
