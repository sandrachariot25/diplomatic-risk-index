"""Read selected Parquet row groups over validated HTTP ranges; retain candidates locally."""
import io
import json
import re
import urllib.request
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]


class RangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url = url
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60) as response:
            self.url = response.url
            self.size = int(response.headers['Content-Length'])
        self.pos = 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos
    def read(self, size=-1):
        size = min(self.size-self.pos, size if size >= 0 else self.size-self.pos)
        if not size: return b''
        start = self.pos
        request = urllib.request.Request(self.url, headers={'Range': f'bytes={start}-{start+size-1}'})
        with urllib.request.urlopen(request, timeout=120) as response:
            if response.status != 206 or not response.headers.get('Content-Range','').startswith(f'bytes {start}-'):
                raise ValueError('Server did not honor byte range; refusing full download')
            payload = response.read()
        if len(payload) != size: raise ValueError('Truncated range')
        self.pos += size
        return payload


if __name__ == '__main__':
    import sys
    term = int(sys.argv[1])
    p = ROOT/'data'/f'kr_hearings_turns_t{term}_v10.3.parquet'
    source = str(p) if p.exists() else RangeFile(f'https://github.com/kyusik-yang/kr-hearings-data/releases/download/v10.3/turns_t{term}_v10.3.parquet')
    f = pq.ParquetFile(source)
    years = set()
    out = ROOT/'data'/f'kr_hearings_candidates_t{term}.jsonl'
    done = {json.loads(line)['row_group'] for line in out.read_text(encoding='utf-8').splitlines()} if out.exists() else set()
    pattern = re.compile('일본|한일|대일외교|강제징용|강제동원|위안부|독도|수출규제|지소미아|GSOMIA')
    for i in range(f.num_row_groups):
        rg = f.metadata.row_group(i)
        col = next(rg.column(j) for j in range(rg.num_columns) if rg.column(j).path_in_schema=='speech_date')
        low, high = col.statistics.min, col.statistics.max
        if high < '2015-01-01': continue
        year = high[:4]
        if year in years and '--all-groups' not in sys.argv: continue
        years.add(year)
        if i in done: continue
        columns = ['conf_num','turn_seq','speech_date','speaker_name','speaker_pos','role_group','text','party','party_uncertain','source','after_end_marker']
        rows = f.read_row_group(i, columns=columns).to_pylist()
        candidates = [r for r in rows if '2015-01-01' <= r['speech_date'] <= '2026-10-31'
                      and 150 <= len(r['text'] or '') <= 1200 and pattern.search(r['text'] or '')
                      and not r['after_end_marker'] and r['speaker_name']]
        with out.open('a',encoding='utf-8') as stream:
            for r in candidates:
                stream.write(json.dumps({**r,'row_group':i,'term':term},ensure_ascii=False)+'\n')
        print(term,i,low,high,'candidates',len(candidates),flush=True)
