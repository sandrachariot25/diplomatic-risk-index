"""Bounded, auditable bibliographic import into the existing repository."""
import json
from collections import Counter
from .paths import ROOT, inside
from .identity import fingerprint
from .storage import now
from .repository import register_sources, ingest, start_run, queue_item, finish_run
from .connectors.media import metadata_document, parse_rss

TABLES=('documents','statements','quotes','sources','statement_sources','quote_sources','duplicate_candidates')
def counts(db):
    return {t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in TABLES}

def validate_batch(rows, sources):
    if len(rows)>100:raise ValueError('Media pilot cap is 100 publications')
    if any(n>10 for n in Counter(r['source'] for r in rows).values()):
        raise ValueError('Maximum ten publications per outlet')
    if len({(r['source'],r['url']) for r in rows})!=len(rows):
        raise ValueError('Repeated URL in batch')
    return [metadata_document(row,sources[row['source']]) for row in rows]

def import_batch(store, rows, run_key):
    sources={s['id']:s for s in json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))}
    docs=validate_batch(rows,sources) # Entire batch validated before writing anything.
    before=counts(store.db)
    rid=start_run(store,run_key,{'manifest_sha256':fingerprint(rows),'channel':'media_bibliography'},resume=True)
    register_sources(store)
    results=[]
    for row,doc in zip(rows,docs):
        key=queue_item(store,rid,doc.source,doc.url)
        try:
            # Existing repository controls canonical URL, document versions and deduplication.
            result=ingest(store,doc,run_id=rid,item_key=key)
            results.append(result)
        except Exception as error:
            store.error(doc.source,doc.url,'media_metadata_import',error)
            with store.db:
                store.db.execute("UPDATE collection_items SET status='parse_error',error=?,updated_at=? WHERE run_id=? AND item_key=?",
                                 (str(error),now(),rid,key))
            raise
    finish_run(store,rid)
    return {'before':before,'after':counts(store.db),'results':results}

def fetch_feed(store, source, *, execute=False):
    """Only publisher-advertised RSS; no article fetching or description retention."""
    url=source.get('verified_feed')
    if not url or source.get('feed_mode')!='metadata_discovery':
        raise ValueError('Source has no verified, enabled discovery feed')
    plan={'url':url,'requests':'robots + one RSS; redirects checked; >=5.5 s; stop on denial',
          'retention':'headers/hash and bibliographic fields only; no descriptions or article requests'}
    print(json.dumps(plan,ensure_ascii=False),flush=True)
    if not execute:return []
    from .http import Client
    from urllib.parse import urlsplit
    client=Client(store,transport='windows',hosts={urlsplit(url).hostname},retain_body=False)
    try:
        xml,_,final=client.get(url,content_types=('xml','rss','html'))
        return parse_rss(xml,source,final)
    except Exception as error:
        store.error(source['id'],url,'media_rss',error)
        raise
