"""Filter documented GDELT 1.0 daily exports in memory, one ZIP at a time."""
from datetime import datetime
from hashlib import sha256
import io
from urllib.request import Request, urlopen
from zipfile import ZipFile


def fetch_day(day):
    stamp = day.strftime('%Y%m%d')
    url = f'https://data.gdeltproject.org/events/{stamp}.export.CSV.zip'
    request = Request(url, headers={'User-Agent': 'DiplomaticRiskIndex/1.0 research archive reader'})
    with urlopen(request, timeout=25) as response:
        body = response.read(32_000_001)
    if len(body) > 32_000_000:
        raise ValueError('Compressed archive exceeds 32 MB')
    records = []
    with ZipFile(io.BytesIO(body)) as archive:
        files = archive.infolist()
        if len(files) != 1 or files[0].file_size > 256_000_000:
            raise ValueError('Expected one bounded TSV member')
        with archive.open(files[0]) as stream:
            for raw in stream:
                row = raw.rstrip(b'\r\n').split(b'\t')
                if len(row) != 58:
                    raise ValueError(f'Unexpected GDELT 1.0 width: {len(row)}')
                if {row[7], row[17]} != {b'KOR', b'JPN'}:
                    continue
                fields = [value.decode('utf-8', errors='replace') for value in row]
                if not fields[0].isdigit() or not fields[26].isdigit():
                    raise ValueError('Invalid GDELT ID or CAMEO code')
                records.append(dict(candidate_id=f'gdelt1:{fields[0]}',
                                    event_date=datetime.strptime(fields[1], '%Y%m%d').date().isoformat(),
                                    actor1='ROK' if fields[7]=='KOR' else 'JPN',
                                    actor2='ROK' if fields[17]=='KOR' else 'JPN',
                                    cameo=fields[26], observed_at=fields[56], url=fields[57],
                                    archive_url=url, record_sha256=sha256(raw).hexdigest(),
                                    raw_fields=fields))
    return dict(day=day.isoformat(), url=url, sha256=sha256(body).hexdigest(), records=records)
