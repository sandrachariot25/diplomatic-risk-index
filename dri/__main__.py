import argparse
import json
from pathlib import Path
from .connectors import CONNECTORS
from .http import Client
from .storage import Store
from .paths import ROOT, DATA, inside
from .repository import register_sources
from .collection import collect_manifest, retained, discover_korea

def main():
    parser = argparse.ArgumentParser(description='DRI official-document collection (default: offline plan)')
    parser.add_argument('--data-dir', default=str(DATA))
    sub = parser.add_subparsers(dest='command', required=True)
    collect = sub.add_parser('collect')
    collect.add_argument('--manifest', default='config/seeds.json')
    collect.add_argument('--execute', action='store_true', help='Explicitly execute the printed network plan')
    collect.add_argument('--transport', choices=['urllib', 'windows'], default='urllib')
    collect.add_argument('--limit', type=int, default=4)
    collect.add_argument('--run-key', default=None)
    collect.add_argument('--resume', action='store_true')
    collect.add_argument('--retry-errors', action='store_true')
    imp = sub.add_parser('import-html')
    imp.add_argument('--source', choices=CONNECTORS, required=True)
    imp.add_argument('--url', required=True)
    imp.add_argument('--file', required=True)
    sub.add_parser('export')
    sub.add_parser('stats')
    sub.add_parser('migrate')
    sub.add_parser('report')
    media=sub.add_parser('media-rss',help='Verified publisher RSS; discovery metadata only')
    media.add_argument('--source',choices=('kbs','korea_herald'),required=True)
    media.add_argument('--execute',action='store_true')
    discovery = sub.add_parser('discover')
    discovery.add_argument('--pages', type=int, default=12)
    discovery.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.command=='media-rss':
        from .media_collection import fetch_feed
        sources=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
        source=next(s for s in sources if s['id']==args.source)
        if not args.execute:
            fetch_feed(None,source)
            return 0
    if args.command == 'collect':
        if not 1 <= args.limit <= 200:
            parser.error('--limit must be 1..200 for the pilot')
        seeds = json.loads(inside(args.manifest).read_text(encoding='utf-8'))[:args.limit]
        for seed in seeds:
            if seed['source'] in CONNECTORS:
                CONNECTORS[seed['source']].canonical(seed['url'])
        print(json.dumps({'plan': 'GET robots.txt per host, then HTML; >=5.5s; TLS verification; stop on 403/429; policy-limited excerpts; no full bodies', 'seeds': seeds}, ensure_ascii=False, indent=2), flush=True)
        if not args.execute:
            return 0
    if args.command == 'discover' and not args.execute:
        discover_korea(None, pages=args.pages)
        return 0
    store = Store(args.data_dir)
    failures = 0
    try:
        register_sources(store)
        if args.command == 'collect':
            from .storage import now
            result=collect_manifest(store,seeds,args.run_key or 'collect-'+now(),transport=args.transport,
                                    resume=args.resume,retry_errors=args.retry_errors)
            failures=result['access_errors']+result['other_errors']
        elif args.command == 'import-html':
            connector = CONNECTORS[args.source]
            url = connector.canonical(args.url)
            body = inside(args.file).read_bytes()
            # Imported bytes are preserved but are never represented as a live HTTP response.
            raw = store.record_fetch(url, None, {'provenance': 'user/local HTML import; not HTTP verified'}, body,retain_body=False)
            try:
                from .repository import ingest
                from .statements import extract_korean_institutional
                doc = retained(connector.parse(body.decode('utf-8-sig'), url))
                print(json.dumps(ingest(store,doc,raw,extract_korean_institutional(doc))))
            except Exception as error:
                store.error(args.source, url, 'import', error)
                raise
            store.export()
        elif args.command == 'export':
            store.export()
        elif args.command == 'report':
            from .quality import report
            print(json.dumps(report(store),ensure_ascii=True))
        elif args.command == 'discover':
            discover_korea(store,pages=args.pages,execute=True)
        elif args.command=='media-rss':
            from .media_collection import fetch_feed
            from .storage import now
            rows=fetch_feed(store,source,execute=True)
            # RSS discovery cannot create documents, statements or quotes.
            relevant=[r for r in rows if 'japan' in r['title'].casefold()]
            with store.db:
                for row in relevant:
                    store.db.execute('''INSERT OR IGNORE INTO discovery_results(source_id,normalized_url,title,discovered_via,discovered_at)
                      VALUES(?,?,?,?,?)''',(source['id'],row['url'],row['title'],source['verified_feed'],now()))
            print(json.dumps({'feed_items':len(rows),'japan_title_candidates':len(relevant),'articles_fetched':0,'documents_imported':0},ensure_ascii=False))
        elif args.command == 'migrate':
            print(json.dumps({'schema_version':store.db.execute('PRAGMA user_version').fetchone()[0]}))
        else:
            print(json.dumps({'documents': store.db.execute('SELECT source,count(*) FROM documents GROUP BY source').fetchall(),
                              'statements':store.db.execute('SELECT country,count(*) FROM statements GROUP BY country').fetchall(),
                              'quotes':store.db.execute('SELECT count(*) FROM quotes').fetchone()[0],
                              'discovery_results':store.db.execute('SELECT count(*) FROM discovery_results').fetchone()[0],
                              'gdelt_events':store.db.execute('SELECT count(*) FROM gdelt_events').fetchone()[0],
                              'gdelt_mentions':store.db.execute('SELECT count(*) FROM gdelt_mentions').fetchone()[0],
                              'gdelt_gkg':store.db.execute('SELECT count(*) FROM gdelt_gkg').fetchone()[0],
                              'errors': store.db.execute('SELECT count(*) FROM errors').fetchone()[0]}))
    finally:
        store.db.close()
    return 1 if failures else 0

if __name__ == '__main__':
    raise SystemExit(main())
