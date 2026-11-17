"""Media import safeguards, real repeat ingestion and RSS provenance."""
import json
import tempfile
import unittest
from dataclasses import replace
from dri.paths import ROOT
from dri.storage import Store
from dri.media_collection import validate_batch,import_batch,counts,fetch_feed
from dri.connectors.media import metadata_document,parse_rss
from dri.repository import register_sources,ingest
from dri.statements import Statement,Quote

class MediaTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'data/test-tmp';folder.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=folder)
        self.store=Store(self.tmp.name,memory=True);register_sources(self.store)
        self.sources={s['id']:s for s in json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))}
        self.rows=json.loads((ROOT/'data/media_manifest.json').read_text(encoding='utf-8'))
    def tearDown(self):self.store.db.close();self.tmp.cleanup()
    def test_entire_real_manifest_repeat_import(self):
        first=import_batch(self.store,self.rows,'test-media')
        second=import_batch(self.store,self.rows,'test-media-repeat')
        self.assertEqual(first['after'],second['after'])
        self.assertEqual(second['before'],second['after'])
        self.assertEqual(first['after']['documents'],len(self.rows))
        self.assertEqual(first['after']['statements'],0)
        self.assertTrue(all(r['documents_added']==0 for r in second['results']))
    def test_prose_quotes_and_statements_rejected(self):
        for field in ('text','quotes','statements'):
            with self.assertRaises(ValueError):metadata_document(dict(self.rows[0],**{field:'not permitted'}),self.sources[self.rows[0]['source']])
    def test_external_host_and_missing_date_evidence_rejected(self):
        for change in ({'url':'https://example.org/article'},{'date_evidence':''},{'published_date':'2027-01-01'}):
            with self.assertRaises(ValueError):metadata_document(dict(self.rows[0],**change),self.sources[self.rows[0]['source']])
    def test_caps_before_mutation(self):
        before=counts(self.store.db)
        for size in (11,101):
            with self.assertRaises(ValueError):import_batch(self.store,[self.rows[0]]*size,'invalid')
        self.assertEqual(before,counts(self.store.db))
    def test_rss_ignores_body_and_publisher_author(self):
        xml='''<rss><channel><item><title>Japan talks</title><link>https://world.kbs.co.kr/service/news_view.htm?Seq_Code=1</link><pubDate>Tue, 01 Jul 2025 00:30:00 +0900</pubDate><author>KBS WORLD Radio</author><description>Do not retain this copyrighted body.</description></item></channel></rss>'''
        row=parse_rss(xml,self.sources['kbs'],'https://world.kbs.co.kr/rss/rss_news.htm?id=Po&amp;lang=e')[0]
        self.assertEqual(row['published_date'],'2025-07-01')
        self.assertIsNone(row['author']);self.assertNotIn('description',row)
        self.assertEqual(metadata_document(row,self.sources['kbs']).text,'')
    def test_xml_entities_and_html_rejected(self):
        for xml in ('<!DOCTYPE rss><rss/>','<html>Access denied</html>'):
            with self.assertRaises(ValueError):parse_rss(xml,self.sources['kbs'],'https://world.kbs.co.kr')
    def test_unverified_feed_disabled(self):
        for source in ('korea_times','kbs'):
            with self.assertRaises(ValueError):fetch_feed(self.store,self.sources[source])

if __name__=='__main__':unittest.main()
