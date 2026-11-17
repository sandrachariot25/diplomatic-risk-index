"""Finite inspection of official pages; retain only status, hashes and link/form metadata."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dri.http import Client
from dri.storage import Store
from dri.html import Tree, clean
from dri.repository import register_sources

def main():
    urls=sys.argv[1:]
    print(json.dumps({'network_plan':urls,'retention':'hash and metadata only, no page body'}),flush=True)
    store=Store();register_sources(store)
    client=Client(store,'windows',hosts={'www.mofa.go.kr','japan.kantei.go.jp','www.president.go.kr'},retain_body=False)
    try:
        for url in urls:
            try:
                html,raw,final=client.get(url)
                root=Tree(html).root
                value={'url':url,'final_url':final,'title':[clean(n.text()) for n in root.find('title')],
                       'inputs':[n.attrs for n in root.find('input')],
                       'selects':[{'attrs':n.attrs,'options':[{'value':o.attrs.get('value'),'label':clean(o.text())} for o in n.find('option')]} for n in root.find('select')],
                       'links':[{'attrs':a.attrs,'title':clean(a.text())} for a in root.find('a') if any(t in clean(a.text()).lower() for t in ('japan','copyright','저작권','정책','대한민국','korea'))][:100],
                       'forms':[n.attrs for n in root.find('form')],
                       'navigation_code':[n.text() for n in []]}
                print(json.dumps(value,ensure_ascii=True),flush=True)
                # Extracted site navigation metadata is the one canonical inspection file.
                path=ROOT/'data'/'remote_inspection.json'
                previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                previous[url]=value
                path.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
            except Exception as e:
                store.error(None,url,'inspection',e);print(json.dumps({'url':url,'error':str(e)}),flush=True)
    finally:store.db.close()

if __name__=='__main__':main()
