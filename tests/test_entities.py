"""Behavioural tests: repeated imports, event boundaries, provenance, rollback and resume."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from dri.storage import Store
from dri.models import Document
from dri.statements import Statement,Quote,extract_korean_institutional
from dri.repository import register_sources,ingest,link_language_versions,start_run,queue_item,finish_run
from dri.collection import collect_manifest,retained
from dri.identity import normalize_url
from dri.connectors.gdelt import GDELTDiscovery
from dri.paths import ROOT

TEXT='The government urges Japan to engage constructively in dialogue and resolve outstanding bilateral issues.'

class EntityTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'data/test-tmp';folder.mkdir(exist_ok=True,parents=True)
        self.tmp=tempfile.TemporaryDirectory(dir=folder)
        self.store=Store(self.tmp.name,memory=True);register_sources(self.store)

    def tearDown(self):
        self.store.db.close();self.tmp.cleanup()

    def doc(self,url='https://example.org/a',source='mofa_kr',text=TEXT,date='2020-01-01',language='en'):
        return Document(source,url,'MOFA Spokesperson statement on Japan',date,text,language,source,
                        source_type='secondary' if source in {'yonhap','nhk','reuters'} else 'primary',content_policy='excerpt_only')

    def st(self,event='reviewed:meeting1:opening',date='2020-01-01',text=TEXT,lang='en'):
        return Statement(event,'ROK','JPN','Foreign Ministry','Opening statement at a specified meeting','2020-01-01',
                         spoken_date=date,speaker_name='Example Speaker',speaker_office='Foreign Minister',
                         attribution_evidence='Synthetic fixture, explicit event identity',quotes=(Quote(text,lang),))

    def counts(self):
        return tuple(self.store.db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ('documents','statements','quotes','statement_sources'))

    def test_same_ingestion_twice_is_idempotent(self):
        first=ingest(self.store,self.doc(),statements=[self.st()])
        before=self.counts()
        second=ingest(self.store,self.doc(),statements=[self.st()])
        self.assertEqual(before,self.counts())
        self.assertEqual((first['documents_added'],first['statements_added'],first['quotes_added']),(1,1,1))
        self.assertEqual((second['documents_added'],second['statements_added'],second['quotes_added']),(0,0,0))

    def test_newspaper_reports_add_sources_not_statements(self):
        for source in ('reuters','yonhap','nhk'):
            # Synthetic allowed excerpts, not downloaded or real news content.
            ingest(self.store,self.doc('https://example.org/'+source,source),statements=[self.st()])
        self.assertEqual(self.counts(),(3,1,1,3))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM quote_sources').fetchone()[0],3)

    def test_same_text_different_day_does_not_merge(self):
        ingest(self.store,self.doc(),statements=[self.st()])
        ingest(self.store,self.doc('https://example.org/b',date='2020-01-02'),statements=[self.st('reviewed:meeting2',date='2020-01-02')])
        self.assertEqual(self.counts()[:3],(2,2,2))
        self.assertGreater(self.store.db.execute("SELECT count(*) FROM duplicate_candidates WHERE status='possible_duplicate'").fetchone()[0],0)

    def test_different_speech_same_day_not_merged(self):
        ingest(self.store,self.doc(),statements=[self.st()])
        ingest(self.store,self.doc('https://example.org/b',text=TEXT+' Further remarks.'),statements=[self.st('reviewed:meeting1:closing')])
        self.assertEqual(self.counts()[1],2)

    def test_partial_quote_remains_distinct_and_reviewable(self):
        ingest(self.store,self.doc(),statements=[self.st()])
        shorter=TEXT.replace('constructively ','')
        ingest(self.store,self.doc('https://example.org/b',text=shorter),statements=[self.st(text=shorter)])
        self.assertEqual(self.counts()[1:3],(1,2))
        self.assertTrue(self.store.db.execute("SELECT 1 FROM duplicate_candidates WHERE entity_type='quote'").fetchone())

    def test_languages_linked_only_with_explicit_evidence(self):
        ingest(self.store,self.doc(),statements=[self.st()])
        ko='정부는 일본과의 건설적인 대화를 촉구한다.'
        ingest(self.store,self.doc('https://example.org/ko',text=ko,language='ko'),statements=[self.st(text=ko,lang='ko')])
        self.assertEqual(self.counts()[1:3],(1,2))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM language_links').fetchone()[0],0)
        a,b=[r[0] for r in self.store.db.execute('SELECT id FROM quotes')]
        with self.assertRaises(ValueError):link_language_versions(self.store,a,b,'','reviewer')
        link_language_versions(self.store,a,b,'https://example.org/official-translation','human_fixture')
        link_language_versions(self.store,a,b,'https://example.org/official-translation','human_fixture')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM language_links').fetchone()[0],1)

    def test_quote_outside_evidence_rejected_without_partial_rows(self):
        with self.assertRaises(ValueError):ingest(self.store,self.doc(),statements=[self.st(text='Invented quotation')])
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_exception_after_document_insert_rolls_back(self):
        with patch('dri.repository._statement',side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):ingest(self.store,self.doc(),statements=[self.st()])
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_resume_preserves_committed_item_and_counters(self):
        rid=start_run(self.store,'test-run',{'x':1})
        key=queue_item(self.store,rid,'mofa_kr',self.doc().url)
        ingest(self.store,self.doc(),statements=[self.st()],run_id=rid,item_key=key)
        self.assertEqual(finish_run(self.store,rid,'interrupted')['statements_added'],1)
        self.assertEqual(start_run(self.store,'test-run',{'x':1},resume=True),rid)
        self.assertEqual(queue_item(self.store,rid,'mofa_kr',self.doc().url),key)
        with self.assertRaises(ValueError):start_run(self.store,'test-run',{'x':2},resume=True)
        self.assertEqual(finish_run(self.store,rid)['documents_discovered'],1)
        self.assertEqual(self.counts(),(1,1,1,1))

    def test_url_tracking_does_not_duplicate_document(self):
        ingest(self.store,self.doc())
        ingest(self.store,self.doc('https://example.org/a?utm_source=search#fragment'))
        self.assertEqual(self.counts()[0],1)
        self.assertEqual(normalize_url('https://EXAMPLE.org:443/a?utm_source=x&b=2&a=1#fragment'),'https://example.org/a?a=1&b=2')

    def test_independent_dates_keep_documents_with_identical_text(self):
        ingest(self.store,self.doc())
        ingest(self.store,self.doc(date='2021-01-01'))
        self.assertEqual(self.counts()[0],2)
    def test_ndl_distinct_speech_ids_keep_identical_same_day_documents(self):
        one=replace(self.doc('https://kokkai.ndl.go.jp/one',source='kokkai_jp'),official_identifier='speech-one')
        two=replace(one,url='https://kokkai.ndl.go.jp/two',official_identifier='speech-two')
        ingest(self.store,one);ingest(self.store,two)
        self.assertEqual(self.counts()[0],2)
        self.assertEqual(ingest(self.store,two)['documents_added'],0)

    def test_retention_and_no_imputed_speech_date(self):
        d=retained(self.doc(text=TEXT+' '+TEXT+' '+TEXT))
        self.assertLessEqual(len(d.text.split()),25)
        self.assertEqual(d.content_sha256,self.doc(text=TEXT+' '+TEXT+' '+TEXT).text_sha256)
        st=extract_korean_institutional(d)[0]
        self.assertIsNone(st.spoken_date)
        self.assertIsNone(st.speaker_name)
        self.assertIsNone(st.original_language)
        self.assertEqual(retained(self.doc(source='reuters')).text,'')

    def test_meeting_article_does_not_become_statement(self):
        d=replace(self.doc(),title='Korea-Japan Foreign Ministers Meeting')
        self.assertEqual(extract_korean_institutional(d),[])

    def test_abe_title_uses_actual_document_relevance(self):
        d=retained(replace(self.doc(),title='MOFA Spokesperson Commentary on Abe Statement'))
        self.assertEqual(len(extract_korean_institutional(d)),1)

    def test_metadata_only_response_is_not_written_as_raw(self):
        raw=self.store.record_fetch('https://example.org/a',200,{},b'protected full content',retain_body=False)
        self.assertEqual(raw[0],'')
        self.assertFalse((Path(self.tmp.name)/'raw').exists())

    def test_gdelt_seen_date_not_publication_date(self):
        g=GDELTDiscovery()
        rows=g.parse(json.dumps({'articles':[{'url':'https://example.org/a','seendate':'20261028000000'}]}),'application/json')
        self.assertIsNone(rows[0]['publication_date'])
        with self.assertRaises(ValueError):g.parse('Please limit requests','text/plain')
        with self.assertRaises(ValueError):g.request_url('Japan Korea',timespan='2015')

    def test_foreign_keys_enforced(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.db:self.store.db.execute('INSERT INTO statement_sources VALUES(999,999,?,?)',('primary','needs_review'))

    def test_unknown_publication_date_is_not_meeting_date(self):
        d=replace(self.doc(),published_date=None,event_date='2020-01-01')
        s=replace(self.st(),published_date=None)
        ingest(self.store,d,statements=[s]);ingest(self.store,d,statements=[s])
        self.assertEqual(self.counts()[:3],(1,1,1))
        self.assertEqual(self.store.db.execute('SELECT spoken_date,published_date FROM statements').fetchone(),('2020-01-01',None))

    def test_kokkai_official_schema_preserves_name_role_and_original(self):
        from dri.connectors.kokkai import Kokkai
        speech='○テスト大臣　日韓関係を改善し、韓国政府との対話を続けます。安全保障についても協力します。'
        body=json.dumps({'speechRecord':[{'speechID':'test_001','speechURL':'https://kokkai.ndl.go.jp/txt/test/1',
          'date':'2020-01-01','speaker':'テスト','speakerPosition':'外務大臣','speech':speech,'issueID':'meeting1',
          'nameOfHouse':'参議院','nameOfMeeting':'外交防衛委員会'}]})
        [(doc,st)]=Kokkai().parse(body)
        self.assertIsNone(doc.published_date)
        self.assertIsNone(st.published_date)
        self.assertEqual(st.spoken_date,'2020-01-01')
        self.assertEqual(st.speaker_name,'テスト')
        self.assertEqual(st.speaker_office,'外務大臣')
        self.assertIn(doc.text,speech)
        self.assertEqual(st.original_language,'ja')
        self.assertLessEqual(len(doc.text),90)

    def test_kokkai_theme_requires_actual_target_phrase(self):
        from dri.connectors.kokkai import Kokkai
        base={'speechID':'test_001','speechURL':'https://kokkai.ndl.go.jp/txt/test/1','date':'2020-01-01',
              'speaker':'テスト','speakerPosition':'外務大臣','issueID':'meeting1'}
        api=Kokkai()
        generic=json.dumps({'speechRecord':[{**base,'speech':'韓国政府との対話について説明します。'}]})
        self.assertEqual(api.parse(generic,'normalization_deescalation'),[])
        regional=json.dumps({'speechRecord':[{**base,'speech':'日中韓の協力を推進して、韓国政府との地域協力を続けます。'}]})
        pairs=api.parse(regional,'regional_cooperation')
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0][1].theme,'regional_cooperation')
        self.assertIn('日中韓',pairs[0][0].text)

    def test_in_memory_schema_migration_preserves_legacy_ids(self):
        import sqlite3
        from dri.migrations import upgrade
        db=sqlite3.connect(':memory:')
        db.executescript('''CREATE TABLE documents(id INTEGER PRIMARY KEY,source TEXT NOT NULL,url TEXT NOT NULL,
          text_sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL,text TEXT NOT NULL,created_at TEXT NOT NULL,
          UNIQUE(source,text_sha256));''')
        metadata=json.dumps({'published_date':'2015-01-01','language':'en'})
        db.execute('INSERT INTO documents VALUES(7,?,?,?,?,?,?)',('mofa_kr','https://example.org/a','hash',metadata,TEXT,'then'))
        db.commit()
        upgrade(db,Path(self.tmp.name))
        self.assertEqual(db.execute('SELECT id,text FROM documents').fetchone(),(7,TEXT))
        from dri.migrations import VERSION
        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],VERSION)
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        db.close()

    def test_verified_fingerprint_normalization_preserves_document_identity(self):
        import hashlib
        from dri.identity import fingerprint,normalized
        from dri.repository import normalize_legacy_fingerprint
        legacy=fingerprint(TEXT)
        old=replace(self.doc(source='kokkai_jp'),official_identifier='speech1',content_sha256=legacy)
        ingest(self.store,old)
        corrected=replace(old,content_sha256=hashlib.sha256(normalized(TEXT).encode()).hexdigest(),legacy_content_fingerprint=legacy)
        self.assertTrue(normalize_legacy_fingerprint(self.store,corrected))
        self.assertEqual(ingest(self.store,corrected)['documents_added'],0)
        self.assertFalse(normalize_legacy_fingerprint(self.store,corrected))
        self.assertEqual(self.counts()[0],1)

    def test_changed_source_cannot_overwrite_existing_fingerprint(self):
        from dri.repository import normalize_legacy_fingerprint
        old=replace(self.doc(source='kokkai_jp'),official_identifier='speech1')
        ingest(self.store,old)
        changed=replace(old,content_sha256='a'*64,legacy_content_fingerprint='b'*64)
        with self.assertRaises(ValueError):normalize_legacy_fingerprint(self.store,changed)
        self.assertEqual(self.store.db.execute('SELECT text_sha256 FROM documents').fetchone()[0],old.text_sha256)

if __name__=='__main__':unittest.main()
