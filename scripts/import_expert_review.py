"""Validate a human-filled workbook; --execute atomically saves expert labels only."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.expert_review import import_review

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--file',required=True);ap.add_argument('--reviewer',required=True);ap.add_argument('--execute',action='store_true');args=ap.parse_args()
    print(json.dumps(import_review(args.file,args.reviewer,args.execute),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
