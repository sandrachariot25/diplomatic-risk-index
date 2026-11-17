"""Bounded, incremental collection of official documents for the DRI live queue."""
import argparse
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import urlencode, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.collection import retained
from dri.connectors.assembly import meeting_references, parse_response, sample_url
from dri.connectors.assembly_pdf import eligible, extract
from dri.connectors.kokkai import Kokkai
from dri.connectors.korea import KoreaMOFA
from dri.html import Tree, clean
from dri.http import AccessBlocked, Client
from dri.identity import normalize_url
from dri.models import Document
from dri.repository import finish_run, ingest, queue_item, start_run
from dri.statements import Quote, Statement
from dri.storage import Store, now

MOSCOW = timezone(timedelta(hours=3))
KANTEI = 'https://www.kantei.go.jp'
KOREA_PATTERN = re.compile(r'\b(?:Japan(?:ese)?|ROK.Japan|Dokdo|Takeshima)\b|일본|한[·ㆍ․-]?(?:미[·ㆍ․-]?)?일|독도|사도광산', re.I)
JAPAN_PATTERN = re.compile(r'(?<!北朝鮮)日韓|韓国|大韓民国|竹島')
KOREAN_TOPIC = re.compile(r'일본|한[·ㆍ․-]?일|독도|강제동원')
HOSTS = {'www.mofa.go.kr', 'kokkai.ndl.go.jp', 'open.assembly.go.kr', 'record.assembly.go.kr', 'www.kantei.go.jp'}


def pilot_day():
    return datetime.now(MOSCOW).date()


def plan(day):
    start = day - timedelta(days=89)
    mofa = [KoreaMOFA.index_url + '?' + urlencode({'srchWord': 'Japan', 'srchTp': '0', 'page': 1}),
            'https://www.mofa.go.kr/www/brd/4080/list.do']
    diet = [Kokkai.endpoint + '?' + urlencode({'any': query, 'from': start, 'until': day,
                                                'maximumRecords': 24, 'recordPacking': 'json'})
            for query in ('韓国', '竹島', '日米韓', '大韓民国')]
    periods = []
    cursor = day.replace(day=1)
    while cursor >= start.replace(day=1):
        periods.append(cursor.strftime('%Y-%m'))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    assembly = [[kind, sample_url(kind, term=22, period=period, committee=committee, through=day)]
                for period in periods for kind, committee in (('committee', '외교통일위원회'), ('plenary', None))]
    # Current statement index verified from the cabinet's published navigation.
    kantei = KANTEI + f'/jp/105/statement/{day.year}/index.html'
    return mofa, diet, assembly, kantei


def diet_response(client, url):
    try:
        client.check_robots(url)
    except AccessBlocked:
        row = client.store.db.execute(
            "SELECT status,headers_json FROM fetches WHERE url='https://kokkai.ndl.go.jp/robots.txt' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        headers = {k.lower(): v for k, v in json.loads(row[1]).items()} if row else {}
        if (not row or row[0] not in (301, 302, 303, 307, 308)
                or headers.get('location') != 'https://kokkai.ndl.go.jp/'
                or not url.startswith(Kokkai.endpoint + '?')):
            raise
    status, headers, body, raw = client.request(url)
    if status in (401, 403, 429):
        raise AccessBlocked(f'HTTP {status}')
    if status != 200 or 'json' not in headers.get('content-type', '').lower():
        raise ValueError(f'Expected NDL JSON, HTTP {status}')
    return body, raw


def mofa_links(html, index):
    api = KoreaMOFA()
    for anchor in Tree(html).root.find('a'):
        title = clean(anchor.text())
        if not KOREA_PATTERN.search(title):
            continue
        href = urljoin(index, anchor.attrs.get('href', ''))
        if anchor.attrs.get('href') == '#':
            handler = anchor.attrs.get('onclick', '')
            match = re.search(r'(?:seq\s*[=:]\s*[\'"]?|(?:f_view|fnView|goView|fn_view|go_view)\s*\(\s*[\'"]?)(\d{5,})', handler)
            if not match:
                continue
            href = index.split('/list.do')[0] + '/view.do?seq=' + match[1]
        try:
            yield api.canonical(href)
        except ValueError:
            continue


def attributed(doc, kind, *, ownership='individual_position'):
    country = doc.country_scope
    return Statement(
        f'live:{doc.source}:{doc.official_identifier}', country, 'ROK' if country == 'JPN' else 'JPN',
        doc.publisher, doc.title, doc.published_date, spoken_date=doc.event_date,
        speaker_name=doc.author, speaker_office=doc.author_role,
        attribution_confidence='medium', attribution_evidence='Official dated source and retained excerpt.',
        original_language=doc.language, institution_type=kind, position_scope=ownership,
        quotes=(Quote(doc.text, doc.language, locator=doc.url),),
    )


class Collector:
    def __init__(self, store, day, run_id):
        self.store, self.day, self.run_id = store, day, run_id
        self.start = day - timedelta(days=89)
        self.client = Client(store, 'windows', hosts=HOSTS, retain_body=False)
        self.counts = Counter()

    def known(self, source, url, official_id=None):
        return self.store.db.execute(
            'SELECT 1 FROM documents WHERE source=? AND (canonical_url=? OR official_id=?)',
            (source, normalize_url(url), official_id),
        ).fetchone() is not None

    def retain(self, doc, statement, raw, institution, source_url=None):
        if (doc.source == 'assembly_kr' and self.store.db.execute(
                'SELECT 1 FROM documents WHERE source=? AND official_id=?', (doc.source, doc.official_identifier)
        ).fetchone()) or (doc.source != 'assembly_kr' and self.known(doc.source, doc.url, doc.official_identifier)):
            return
        identity = f'{doc.source}:{doc.official_identifier}'
        key = queue_item(self.store, self.run_id, doc.source, source_url or doc.url, item_key=identity)
        evidence = dict(country=statement.country, speaker=statement.speaker_name, institution=institution,
                        source=doc.source, url=source_url or doc.url, title=doc.title, language=doc.language,
                        published_date=doc.published_date, spoken_date=doc.event_date or doc.published_date,
                        content_sha256=hashlib.sha256(doc.text.encode()).hexdigest(), fetch_sha256=raw[1],
                        context=statement.context)
        queued = False

        def checkpoint(doc_id, sid, added):
            nonlocal queued
            if added:
                self.store.db.execute('INSERT INTO live_review_queue VALUES (?,?,?,?,?)',
                                      (identity, doc_id, sid, raw[2], json.dumps(evidence, ensure_ascii=False)))
                queued = True

        # Raw responses stay transient unless permitted by the existing PDF retention policy.
        ingest(self.store, doc, raw if raw[0] else None, [statement], self.run_id, key, on_statement=checkpoint)
        if queued:
            self.counts[f'queued_{statement.country}'] += 1
            print(json.dumps(dict(id=identity, **evidence), ensure_ascii=False), flush=True)

    def mofa(self, indexes):
        links = []
        for index in indexes:
            if '/view.do?' in index:
                links.append(KoreaMOFA().canonical(index))
                continue
            html, _, final = self.client.get(index)
            links.extend(mofa_links(html, final))
        links = [url for url in dict.fromkeys(links) if not self.known('mofa_kr', url)][:22]
        print('MOFA candidate links', len(links), flush=True)
        for url in links:
            if self.known('mofa_kr', url):
                continue
            html, raw, final = self.client.get(url)
            full = KoreaMOFA().parse(html, final)
            self.counts['fetched_ROK'] += 1
            if not self.start.isoformat() <= full.published_date <= self.day.isoformat():
                continue
            lines = [line for line in full.text.splitlines() if KOREA_PATTERN.search(line)]
            if not lines:
                continue
            excerpt = next((line for line in lines if len(line.split()) >= 12), lines[0])
            match = KOREA_PATTERN.search(excerpt)
            words = excerpt.split()
            before = max(0, len(excerpt[:match.start()].split()) - 7)
            doc = replace(retained(full), text=' '.join(words[before:before+25]),
                          country_scope='ROK', official_identifier=final.split('seq=')[-1])
            if len(doc.text) < 35:
                continue
            self.retain(doc, attributed(doc, 'government', ownership='institutional_position'), raw, 'government')

    def diet(self, urls):
        for url in urls:
            body, raw = diet_response(self.client, url)
            pairs = Kokkai().parse(body, start=self.start.isoformat(), end=self.day.isoformat())
            for doc, statement in pairs:
                if self.known(doc.source, doc.url, doc.official_identifier):
                    continue
                self.counts['fetched_JPN'] += 1
                group = 'government' if statement.speaker_office and re.search('大臣|副大臣|政務官', statement.speaker_office) else 'parliament'
                self.retain(doc, replace(statement, institution_type=group), raw, group)

    def assembly(self, urls):
        seen = set()
        for kind, url in urls:
            body, _, _ = self.client.get(url, content_types=('json','html','text/plain'))
            rows, _ = parse_response(json.loads(body), kind)
            for ref in meeting_references(rows, through=self.day)[:2]:
                if (ref.record_number in seen or ref.meeting_date < self.start.isoformat()
                        or self.known('assembly_kr', ref.pdf_url)
                        or self.store.db.execute("SELECT 1 FROM documents WHERE source='assembly_kr' AND url LIKE ? LIMIT 1",
                                                 (f'%id={ref.record_number}&%',)).fetchone()):
                    continue
                seen.add(ref.record_number)
                recent_error = self.store.db.execute(
                    "SELECT 1 FROM fetches WHERE url=? AND substr(fetched_at,1,10)=? "
                    "AND error LIKE '%Response exceeds size cap%' LIMIT 1",
                    (ref.pdf_url, datetime.now(timezone.utc).date().isoformat()),
                ).fetchone()
                if recent_error:
                    continue
                self.client.check_robots(ref.pdf_url)
                try:
                    status, _, content, raw = self.client.request(ref.pdf_url)
                except (OSError, ValueError) as error:
                    self.store.error('assembly_kr', ref.pdf_url, 'live:assembly_pdf', error)
                    if 'Response exceeds size cap' in str(error):
                        print('Assembly PDF exceeds response cap:', ref.record_number, flush=True)
                        continue
                    raise
                if status in (401, 403, 429):
                    raise AccessBlocked(f'PDF HTTP {status}')
                if status != 200 or not content.startswith(b'%PDF'):
                    raise ValueError(f'Expected Assembly PDF, HTTP {status}')
                self.counts['fetched_ROK'] += 1
                # The public text-layer protocol follows the existing internal research policy.
                ref_raw = self.store.record_fetch(ref.pdf_url, 200, {'X-DRI-Retention': 'internal research PDF'}, content)
                try:
                    protocol = extract(self.store.root/ref_raw[0])
                except ValueError as error:
                    self.store.error('assembly_kr', ref.pdf_url, 'live:assembly_pdf', error)
                    continue
                speakers = set()
                for turn in protocol['turns']:
                    text = turn['text']
                    topic = text.replace('재일본조선인총연합회', '')
                    if (not eligible(turn) or not KOREAN_TOPIC.search(topic)
                            or re.search(r'제\d+회-제\d+차\s*\(\d{4}년', text)
                            or turn['speaker_name'] in speakers):
                        continue
                    identity = f'{ref.conf_id}:{turn["ordinal"]}'
                    doc = Document('assembly_kr', ref.pdf_url, ref.title, None, turn['text'], 'ko',
                                   ref.organ, author=turn['speaker_name'], author_role=turn['role'],
                                   event_date=ref.meeting_date, country_scope='ROK', official_identifier=identity,
                                   content_policy='internal_research_only', rights='Public protocol, internal research only',
                                   research_metadata={'confer_num': ref.record_number, 'ordinal': turn['ordinal'],
                                                      'spans': turn['spans']})
                    group = 'parliament' if turn['role'] in ('위원', '의원', '위원장', '의장') else 'government'
                    self.retain(doc, attributed(doc, group), ref_raw, group)
                    speakers.add(turn['speaker_name'])
                    if len(speakers) == 6:
                        break

    def kantei(self, index):
        html, _, final = self.client.get(index)
        links = {}
        for anchor in Tree(html).root.find('a'):
            title = unicodedata.normalize('NFKC', clean(anchor.text()))
            url = urljoin(final, anchor.attrs.get('href', ''))
            path = urlsplit(url).path
            match = re.search(r'令和\s*(\d+)年\s*(\d+)月\s*(\d+)日', title)
            if not match or urlsplit(url).netloc != 'www.kantei.go.jp' or not re.fullmatch(r'/jp/\d+/statement/\d{4}/[^/]+\.html', path) or url == index:
                continue
            dated = date(int(match[1])+2018, int(match[2]), int(match[3]))
            if self.start <= dated <= self.day:
                links[url] = (title.split('令和')[0].strip(), dated, path)
        unseen = [(url, metadata) for url, metadata in links.items()
                  if not self.known('kantei_jp', url, metadata[2])
                  and not self.store.db.execute(
                      'SELECT 1 FROM fetches WHERE url=? AND status=200 AND fetched_at>=? LIMIT 1',
                      (url, (datetime.now(timezone.utc)-timedelta(days=1)).isoformat())).fetchone()]
        chosen = sorted(unseen, key=lambda item: (bool(JAPAN_PATTERN.search(item[1][0])),
                       any(term in item[1][0] for term in ('所信表明', '国連総会', '就任１年', '就任1年')), item[1][1]), reverse=True)[:9]
        print('Kantei candidate links', len(chosen), flush=True)
        for url, (title, dated, path) in chosen:
            if self.known('kantei_jp', url, path):
                continue
            html, raw, final = self.client.get(url)
            self.counts['fetched_JPN'] += 1
            root = Tree(html).root
            sections = root.find('main') or root.find(id='main')
            if not sections:
                continue
            paragraphs = [clean(node.text()) for node in sections[0].find('p')]
            paragraphs = [p for p in paragraphs if len(p) >= 35 and JAPAN_PATTERN.search(p)]
            if not paragraphs:
                continue
            # Prefer the actual statement over navigation or a date/heading.
            paragraph = paragraphs[0]
            match = JAPAN_PATTERN.search(paragraph)
            offset = max(0, match.start()-20)
            text = paragraph[offset:offset+90]
            doc = Document('kantei_jp', final, title, None, text, 'ja', "Prime Minister's Office of Japan",
                           event_date=dated.isoformat(), country_scope='JPN', official_identifier=path,
                           content_policy='excerpt_only', rights='Official site terms, short attributed excerpt',
                           rights_evidence=KANTEI+'/jp/terms.html')
            self.retain(doc, attributed(doc, 'government', ownership='institutional_position'), raw, 'government')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--source', choices=('mofa', 'diet', 'assembly', 'kantei'), action='append')
    parser.add_argument('--mofa-url', action='append', help='Use verified MOFA document links instead of index discovery')
    parser.add_argument('--mofa-pages', type=int, default=1, choices=range(1,11),
                        help='Bounded Korean archive pagination, at most ten pages')
    args = parser.parse_args()
    day = pilot_day()
    mofa, diet, assembly, kantei = plan(day)
    if args.mofa_pages > 1:
        mofa = ['https://www.mofa.go.kr/www/brd/4080/list.do?page='+str(page)
                for page in range(1,args.mofa_pages+1)]
    sources = dict(mofa=[KoreaMOFA().canonical(url) for url in args.mofa_url] if args.mofa_url else mofa,
                   diet=diet, assembly=assembly, kantei=kantei)
    selected = args.source or list(sources)
    config = {source: sources[source] for source in selected}
    print(json.dumps(config, ensure_ascii=False), flush=True)
    if not args.execute:
        return
    store = Store()
    plan_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    run = start_run(store, 'live:' + day.isoformat() + ':' + '+'.join(selected) + ':' + plan_hash, config, resume=True)
    collector = Collector(store, day, run)
    try:
        for source in selected:
            status = 'ok'
            before = collector.counts.copy()
            try:
                getattr(collector, source)(sources[source])
            except (ValueError, OSError, AccessBlocked, sqlite3.IntegrityError) as error:
                status = str(error)
                collector.counts['errors'] += 1
                store.error(None, None, 'live:' + source, error)
                print(f'{source}: {type(error).__name__}: {error}', flush=True)
            source_id, country = {'mofa': ('mofa_kr', 'ROK'), 'diet': ('kokkai_jp', 'JPN'),
                                  'assembly': ('assembly_kr', 'ROK'), 'kantei': ('kantei_jp', 'JPN')}[source]
            evidence_url = sources[source][0] if isinstance(sources[source], list) else sources[source]
            if source == 'assembly':
                evidence_url = evidence_url[1]
            with store.db:
                store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result) VALUES(?,?,?,?,?)',
                                 (source_id, evidence_url, now(), None, json.dumps(
                                     dict(pilot='live', run_id=run, status=status, country=country,
                                          fetched=collector.counts[f'fetched_{country}']-before[f'fetched_{country}'],
                                          queued=collector.counts[f'queued_{country}']-before[f'queued_{country}']),
                                     ensure_ascii=False)))
        finish_run(store, run, 'completed_with_errors' if collector.counts['errors'] else 'completed')
        print(json.dumps(collector.counts), flush=True)
    except BaseException:
        finish_run(store, run, 'interrupted')
        raise
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
