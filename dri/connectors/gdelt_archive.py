"""Documented GDELT 2 exports; never converted into speech entities."""
import io,json,zipfile,re
from datetime import datetime
from ..identity import fingerprint

def rows_from_zip(body,width):
    z=zipfile.ZipFile(io.BytesIO(body));items=z.infolist()
    if len(items)!=1 or items[0].file_size>64_000_000:raise ValueError('ZIP must contain one bounded TSV')
    rows=[r.split('\t') for r in z.read(items[0]).decode('utf-8-sig').splitlines()]
    if any(len(row)!=width for row in rows):raise ValueError('GDELT schema width changed')
    return rows

def events(body):
    selected=[]
    for r in rows_from_zip(body,61):
        if {r[7],r[17]}!={'KOR','JPN'}:continue
        day=datetime.strptime(r[1],'%Y%m%d').date().isoformat()
        if not '2015-01-01'<=day<='2026-10-30':continue
        datetime.strptime(r[59],'%Y%m%d%H%M%S')
        if not r[0].isdigit() or not r[26] or not r[60]:raise ValueError('Missing GDELT event identity/code/source')
        selected.append(dict(event_id=r[0],event_date=day,observed_at=r[59],actor1_name=r[6],actor1_country='ROK' if r[7]=='KOR' else 'JPN',
          actor1_role=r[12],actor2_name=r[16],actor2_country='ROK' if r[17]=='KOR' else 'JPN',actor2_role=r[22],event_code=r[26],
          source_url=r[60],record_sha256=fingerprint(r),raw_json=json.dumps(r,ensure_ascii=False)))
    return selected

def mentions(body,event_ids):
    selected=[]
    for r in rows_from_zip(body,16):
        if r[0] not in event_ids:continue
        datetime.strptime(r[1],'%Y%m%d%H%M%S');datetime.strptime(r[2],'%Y%m%d%H%M%S')
        if not r[5]:raise ValueError('Missing mention document identifier')
        lang=re.search(r'(?:^|;)\s*srclc:([^;]+)',r[14],re.I)
        selected.append(dict(identity_key=fingerprint(r),event_id=r[0],event_observed_at=r[1],mention_observed_at=r[2],
            source_name=r[4],document_identifier=r[5],source_type=r[3],source_language=lang[1].strip() if lang else None,raw_json=json.dumps(r,ensure_ascii=False)))
    return selected

def gkg(body):
    selected=[]
    for r in rows_from_zip(body,27):
        # GKG locations use FIPS country codes, not CAMEO actor codes.
        countries={location.split('#')[2] for location in r[9].split(';') if len(location.split('#'))>=3}
        if not {'KS','JA'}.issubset(countries):continue
        stamp=r[1]
        datetime.strptime(stamp,'%Y%m%d%H%M%S')
        if not '20150101000000'<=stamp<='20261030235959':continue
        selected.append(dict(record_id=r[0],observed_at=stamp,document_identifier=r[4],source_name=r[3],raw_json=json.dumps(r,ensure_ascii=False)))
    return selected

def save_records(store,table,records,archive_url,sha):
    if table not in {'gdelt_events','gdelt_mentions','gdelt_gkg'}:raise ValueError('Unknown typed GDELT table')
    added=0
    with store.db:
        for record in records:
            pk={'gdelt_events':'event_id','gdelt_mentions':'identity_key','gdelt_gkg':'record_id'}[table]
            existing=store.db.execute(f'SELECT raw_json FROM {table} WHERE {pk}=?',(record[pk],)).fetchone()
            if existing and existing[0]!=record['raw_json']:
                raise ValueError('Same GDELT identity has changed content; retain archive and review, no overwrite')
            row=dict(record,archive_url=archive_url,raw_sha256=sha)
            fields=','.join(row);marks=','.join('?' for _ in row)
            added+=store.db.execute(f'INSERT OR IGNORE INTO {table}({fields}) VALUES({marks})',tuple(row.values())).rowcount
    return added
