"""Small, sequential audit probes. Saves exact responses, including failures."""
import hashlib
import json
import time
import urllib.error
import urllib.request
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def probe(urls, windows=False):
    out = ROOT / 'data' / 'audit'
    out.mkdir(parents=True, exist_ok=True)
    for url in urls:
        record = {'url': url, 'checked_at': datetime.now(timezone.utc).isoformat()}
        try:
            if windows:
                from dri.http import windows_get
                status, headers, body = windows_get(url)
                record.update(status=status, headers=headers, transport='windows-system-trust')
                if status >= 400:
                    record['error'] = f'HTTP {status}'
            else:
                body, record = python_request(url, record)
        except urllib.error.HTTPError as error:
            body = error.read(100000)
            record.update(status=error.code, error=str(error), headers=dict(error.headers))
        except Exception as error:
            body = b''
            record.update(error=f'{type(error).__name__}: {error}')
        # One stable metadata record per URL; no new protected response bodies retained.
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        record['body_file'] = None
        record['retention'] = 'metadata_only; response body hashed in memory, not saved'
        record['sha256'] = hashlib.sha256(body).hexdigest()
        # Never overwrite old evidence. Current probes live in the primary SQLite source checks
        # for bulk audits; this compatibility tool appends a single canonical metadata log.
        with (out / 'probe_metadata.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(record,ensure_ascii=False)+'\n')
        print(json.dumps(record, ensure_ascii=True), flush=True)
        time.sleep(5.5)

def python_request(url, record):
            req = urllib.request.Request(url, headers={'User-Agent': 'DRI-Research-Audit/0.1 (small public-source feasibility audit)'})
            with urllib.request.urlopen(req, timeout=35) as response:
                body = response.read(4_000_001)
                if len(body) > 4_000_000:
                    raise ValueError('Response exceeds audit size cap')
                record.update(status=response.status, final_url=response.url, headers=dict(response.headers))
            return body, record

if __name__ == '__main__':
    windows = '--windows' in sys.argv
    probe([arg for arg in sys.argv[1:] if arg != '--windows'], windows)
