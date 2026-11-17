import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dri.connectors import CONNECTORS
from dri.http import Client, AccessBlocked
from dri.models import Document
from dri.storage import Store

KR = CONNECTORS['mofa_kr']
JP = CONNECTORS['mofa_jp']
URL = 'https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=315568'
BODY = 'A diplomatic statement with substantive original content. ' * 5
HTML = f'''<html><script>ignore me</script><div class="board_detail"><div class="bo_head">
<h2>Japan statement</h2><dl><dt>Date</dt><dd>2015-08-15</dd></dl></div>
<div class="bo_con"><p>{BODY}</p><p>* unofficial translation</p></div></div>
<footer>FOOTER MUST NOT APPEAR</footer></html>'''

class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / 'data' / 'test-tmp'
        temp_root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=temp_root)
        self.store = Store(self.tmp.name, memory=True)

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def test_korean_body_and_missing_author(self):
        doc = KR.parse(HTML, URL)
        self.assertEqual(doc.published_date, '2015-08-15')
        self.assertIsNone(doc.author)
        self.assertNotIn('FOOTER', doc.text)
        self.assertNotIn('ignore me', doc.text)
        self.assertEqual(doc.translation_note, 'unofficial translation')
    @patch('dri.http.time.sleep')
    @patch('dri.http.time.monotonic',return_value=100.0)
    @patch.dict('dri.http.HOST_LAST_REQUEST',{},clear=True)
    def test_rate_limit_survives_new_client_instances(self,clock,sleep):
        for _ in range(2):
            client=Client(self.store)
            client.transport=lambda u:(200,{'Content-Type':'text/html'},b'fixture')
            client.request(URL)
        self.assertEqual(sleep.call_args_list[-1].args[0],5.5)

    def test_structure_drift_and_invalid_date_are_rejected(self):
        with self.assertRaises(ValueError):
            KR.parse('<html>Access denied</html>', URL)
        with self.assertRaises(ValueError):
            KR.parse(HTML.replace('2015-08-15', '2015-99-99'), URL)

    def test_url_normalization_and_host_restriction(self):
        self.assertEqual(KR.canonical(URL + '&page=10#x'), URL)
        with self.assertRaises(ValueError):
            KR.canonical(URL.replace('www.mofa.go.kr', 'evil.example'))

    def test_discovery_uses_real_links(self):
        html = '<a href="./view.do?seq=315568&amp;page=2">Japan statement</a><a href="./view.do?seq=123">Other event</a>'
        self.assertEqual(KR.discover(html), [URL])

    def test_dedup_retains_urls_and_revisions(self):
        doc = KR.parse(HTML, URL)
        raw = self.store.record_fetch(URL, 200, {}, HTML.encode())
        self.assertTrue(self.store.save(doc, raw))
        self.assertFalse(self.store.save(doc, raw))
        alias = Document(**{**doc.__dict__, 'url': URL.replace('315568', '315569')})
        self.assertFalse(self.store.save(alias, raw))
        revision = Document(**{**doc.__dict__, 'text': doc.text + '\nA later revision.'})
        self.assertTrue(self.store.save(revision, raw))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM documents').fetchone()[0], 2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM observations').fetchone()[0], 3)
        self.store.export()
        rows = [json.loads(line) for line in (Path(self.tmp.name) / 'corpus.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows[0]['observations']), 2)
        self.assertEqual((Path(self.tmp.name) / raw[0]).read_bytes(), HTML.encode())

    def client(self, responses):
        client = Client(self.store)
        client.transport = lambda url: responses.pop(0)
        return client

    @patch('dri.http.time.sleep')
    def test_robots_denial_prevents_document_request(self, sleep):
        responses = [(200, {}, b'User-agent: *\nDisallow: /eng/')]
        client = self.client(responses)
        with self.assertRaises(AccessBlocked):
            client.get(URL)
        self.assertEqual(len(responses), 0)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM fetches').fetchone()[0], 1)

    @patch('dri.http.time.sleep')
    def test_403_robots_blocks_subsequent_requests(self, sleep):
        client = self.client([(403, {}, b'Forbidden')])
        for _ in range(2):
            with self.assertRaises(AccessBlocked):
                client.get(URL)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM fetches').fetchone()[0], 1)

    @patch('dri.http.time.sleep')
    def test_429_stops_host_and_preserves_failure(self, sleep):
        client = self.client([(200, {}, b'User-agent: *\nAllow: /'), (429, {'Retry-After': '60'}, b'wait')])
        with self.assertRaises(AccessBlocked):
            client.get(URL)
        with self.assertRaises(AccessBlocked):
            client.get(URL)
        self.assertEqual(self.store.db.execute('SELECT status FROM fetches ORDER BY id DESC LIMIT 1').fetchone()[0], 429)

    @patch('dri.http.time.sleep')
    def test_redirect_to_other_host_rejected(self, sleep):
        client = self.client([(200, {}, b'User-agent: *\nAllow: /'), (302, {'Location': 'https://evil.example/a'}, b'')])
        with self.assertRaises(AccessBlocked):
            client.get(URL)

    def test_failure_logging(self):
        self.store.error('mofa_jp', 'https://www.mofa.go.jp/a.html', 'collect', AccessBlocked('HTTP 403'))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM errors').fetchone()[0], 1)
        self.assertIn('HTTP 403', (Path(self.tmp.name) / 'errors.jsonl').read_text(encoding='utf-8'))

    def test_japan_provisional_parser_only_synthetic_fixture(self):
        html = f'<div id="main"><h2>Japan-ROK meeting</h2><p>July 29, 2025</p><div class="contents"><p>{BODY}</p></div></div>'
        doc = JP.parse(html, 'https://www.mofa.go.jp/press/release/pressite_000001_01500.html')
        self.assertEqual(doc.published_date, '2025-07-29')
        self.assertIsNone(doc.author)

    def test_real_korean_snapshot(self):
        path = Path(__file__).resolve().parents[1] / 'data/manual/korea-315568.html'
        if not path.exists():
            self.skipTest('Saved live snapshot not present')
        doc = KR.parse(path.read_text(encoding='utf-8'), URL)
        self.assertIn('Abe Statement', doc.title)
        self.assertIn('Government of the Republic of Korea', doc.text)
        self.assertEqual(doc.published_date, '2015-08-15')

if __name__ == '__main__':
    unittest.main()
