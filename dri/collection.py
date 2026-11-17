"""Checkpointed collectors with rights-aware retention and deterministic extraction."""
import json
import re
from dataclasses import replace
from urllib.parse import urljoin, urlencode
from .connectors import CONNECTORS
from .html import Tree, clean
from .http import Client, AccessBlocked
from .identity import fingerprint, normalize_url
from .models import Document
from .paths import ROOT, inside
from .repository import register_sources, ingest, start_run, queue_item, finish_run
from .statements import extract_korean_institutional
from .storage import now

def retained(doc, policy='excerpt_only', quote_words=25):
    """Hash the transient full text, retain only policy-approved text.

    25 words is a conservative engineering cap, NOT a universal legal permission.
    Secondary sources default to zero text; supplied licences must be audited separately.
    """
    if doc.source=='mofa_kr' and re.search(r'Japan|Japanese|Dokdo|Takeshima',doc.title+' '+doc.text,re.I):
        doc=replace(doc,related_countries=('ROK','JPN'))
    if doc.source_type == 'secondary' or policy == 'metadata_only':
        return replace(doc,text='',content_policy='metadata_only',content_sha256=doc.text_sha256)
    if policy == 'full_text_permitted':
        return replace(doc,content_policy=policy)
    paragraphs=[p for p in doc.text.splitlines() if p.strip() and 'unofficial translation' not in p.lower()]
    preferred=next((p for p in paragraphs if re.search(r'(?:Government of the Republic of Korea|ROK government|Korean government)',p,re.I)),doc.text)
    excerpt=' '.join(preferred.split()[:quote_words])
    return replace(doc,text=excerpt,content_policy='excerpt_only',content_sha256=doc.text_sha256)

def collect_manifest(store, manifest, run_key, *, transport='urllib', resume=False, retry_errors=False):
    register_sources(store)
    config={'manifest_sha256':fingerprint(manifest),'transport':transport}
    run_id=start_run(store,run_key,config,resume)
    client=Client(store,transport,retain_body=False)
    run_status='completed'
    try:
        for seed in manifest:
            url=seed['url']; source=seed['source']
            key=queue_item(store,run_id,source,url)
            status=store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(run_id,key)).fetchone()[0]
            if status=='processed' or status=='excluded' or (status.endswith('_error') and not retry_errors):
                continue
            try:
                if source not in CONNECTORS:
                    # Explicit metadata imports are useful even if publisher access is forbidden.
                    if not seed.get('metadata'):
                        raise ValueError('Only metadata import supported for unlicensed/unverified publishers')
                    m=seed['metadata']
                    doc=Document(source,normalize_url(url),m['title'],m['published_date'],'',m.get('language','und'),
                                 m.get('publisher',source),author=m.get('author'),source_type=m.get('source_type','secondary'),content_policy='metadata_only',
                                 content_sha256=fingerprint(source,normalize_url(url),m['title'],m['published_date']),
                                 country_scope=m.get('country_scope'),fingerprint_kind='metadata_identity')
                    raw=None; statements=[]
                else:
                    html,raw,final=client.get(url)
                    full=CONNECTORS[source].parse(html,final)
                    if not '2015-01-01' <= full.published_date <= '2026-10-28':
                        with store.db:
                            store.db.execute("UPDATE collection_items SET status='excluded',error='Outside research interval',updated_at=? WHERE run_id=? AND item_key=?",(now(),run_id,key))
                        continue
                    policy=store.db.execute('SELECT content_policy FROM sources WHERE id=?',(source,)).fetchone()[0]
                    doc=retained(full,policy)
                    statements=extract_korean_institutional(doc)
                current=store.db.execute('SELECT count(*) FROM statements').fetchone()[0]
                new_statements=[st for st in statements if not store.db.execute('SELECT 1 FROM statements WHERE identity_key=?',(st.key,)).fetchone()]
                if current+len(new_statements)>200:
                    with store.db:store.db.execute("UPDATE collection_items SET status='excluded',error='Pilot cap: 200 unique statement records',updated_at=? WHERE run_id=? AND item_key=?",(now(),run_id,key))
                    continue
                result=ingest(store,doc,raw,statements,run_id,key)
                print(json.dumps({'url':url,**result}),flush=True)
            except Exception as e:
                state='access_error' if isinstance(e,(AccessBlocked,OSError)) else 'parse_error'
                with store.db:
                    store.db.execute('UPDATE collection_items SET status=?,error=?,updated_at=? WHERE run_id=? AND item_key=?',
                                     (state,str(e)[:2000],now(),run_id,key))
                store.error(source,url,'collect',e)
                print(json.dumps({'url':url,'status':state,'error':str(e)[:300]}),flush=True)
        errors=store.db.execute("SELECT count(*) FROM collection_items WHERE run_id=? AND status LIKE '%_error'",(run_id,)).fetchone()[0]
        if errors:run_status='completed_with_errors'
    except BaseException:
        run_status='interrupted'
        raise
    finally:
        counters=finish_run(store,run_id,run_status)
        store.export()
        print(json.dumps({'run_id':run_id,'status':run_status,'counters':counters}),flush=True)
    return counters

def discover_korea(store, *, pages=12, transport='windows', execute=False):
    """Read only form-confirmed HTML search parameters and actual document links.

    No guessed date filters/API. Year coverage depends on what the server returns.
    """
    urls=['https://www.mofa.go.kr/eng/brd/m_5676/list.do?'+urlencode({'srchWord':'Japan','srchTp':'0','page':p}) for p in range(1,pages+1)]
    print(json.dumps({'plan':'bounded official HTML search; no full-body retention','page_count':pages,'first_url':urls[0],'last_url':urls[-1]}),flush=True)
    if not execute:return []
    register_sources(store)
    rid=start_run(store,'korea-html-search-'+str(pages),{'pages':pages,'term':'Japan','srchTp':'0'},resume=True)
    client=Client(store,transport,retain_body=False)
    found=[]; seen=set()
    for url in urls:
        qkey=queue_item(store,rid,'mofa_kr',url)
        if store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,qkey)).fetchone()[0]=='query_completed':continue
        try:
            html,raw,final=client.get(url)
            root=Tree(html).root
            for a in root.find('a'):
                title=clean(a.text())
                if not re.search(r'Japan|Japanese|Dokdo|Takeshima',title,re.I):continue
                href=urljoin(final,a.attrs.get('href',''))
                if href.endswith('#') or a.attrs.get('href')=='#':
                    # Only actual onclick navigation carrying an explicit seq is accepted.
                    handler=a.attrs.get('onclick','')
                    match=re.search(r'(?:seq\s*[=:]\s*[\'\"]?|(?:f_view|fnView|goView|fn_view|go_view)\s*\(\s*[\'\"]?)(\d{5,})',handler)
                    if not match:continue
                    href='https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq='+match[1]
                try:canonical=CONNECTORS['mofa_kr'].canonical(href)
                except ValueError:continue
                if canonical in seen:continue
                seen.add(canonical)
                if any(t in title.casefold() for t in ('commentary','statement')):
                    found.append({'source':'mofa_kr','url':canonical,'title':title})
                with store.db:
                    store.db.execute('''INSERT INTO discovery_results(source_id,normalized_url,title,discovered_via,discovered_at)
                      VALUES(?,?,?,?,?) ON CONFLICT(normalized_url) DO NOTHING''',('mofa_kr',canonical,title,url,now()))
            with store.db:store.db.execute("UPDATE collection_items SET status='query_completed',updated_at=? WHERE run_id=? AND item_key=?",(now(),rid,qkey))
            print(json.dumps({'index':url,'statement_documents_found':len(found)}),flush=True)
        except Exception as e:
            with store.db:store.db.execute("UPDATE collection_items SET status='access_error',error=?,updated_at=? WHERE run_id=? AND item_key=?",(str(e)[:2000],now(),rid,qkey))
            store.error('mofa_kr',url,'discovery',e)
            print(json.dumps({'index':url,'error':str(e)[:300]}),flush=True)
            break
    # One canonical manifest, deterministic URL order, no repeated export versions.
    path=ROOT/'data/pilot_manifest.json'
    prior=[{'source':'mofa_kr','url':url,'title':title} for url,title in store.db.execute("SELECT normalized_url,title FROM discovery_results WHERE source_id='mofa_kr' ORDER BY id") if any(t in title.casefold() for t in ('commentary','statement'))]
    combined={x['url']:x for x in prior}
    combined.update({x['url']:x for x in found})
    path.write_text(json.dumps(list(combined.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    has_errors=store.db.execute("SELECT 1 FROM collection_items WHERE run_id=? AND status='access_error'",(rid,)).fetchone()
    finish_run(store,rid,'completed_with_errors' if has_errors else 'completed')
    return found
