"""Small checkpointed batches. Plan by default; execute requires explicit flag."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.expansion import run_batch

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--execute',action='store_true')
    p.add_argument('--batch-size',type=int,default=20)
    p.add_argument('--batches',type=int,default=1)
    p.add_argument('--retry-errors',action='store_true',help='Explicit retry only after transport timeout, never denial')
    a=p.parse_args()
    if not 1<=a.batches<=25:p.error('batches 1..25')
    s=Store()
    try:
        for _ in range(a.batches):
            result=run_batch(s,a.batch_size,a.execute,a.retry_errors)
            if result is None:break
            print(json.dumps({'checkpoint':result},ensure_ascii=True),flush=True)
            errors=s.db.execute('SELECT status FROM collection_runs WHERE id=?',(result['batch_run_id'],)).fetchone()[0]
            if errors!='completed':break
    finally:s.db.close()

if __name__=='__main__':main()
