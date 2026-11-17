from datetime import datetime, timezone
import json
import sqlite3
import unittest
from unittest.mock import patch

from dri.models import Document
from dri.repository import ingest, register_sources
from dri.storage import Store
from scripts.collect_live_dri import attributed
from scripts.live_dri import digest, import_batch, issue, verify_journal


class LiveDRITests(unittest.TestCase):
    def setUp(self):
        self.store = Store(memory=True)
        self.addCleanup(self.store.db.close)
        self.db = self.store.db
        register_sources(self.store)
        self.capture = datetime(2026, 11, 8, 18, tzinfo=timezone.utc)
        self.issued = datetime(2026, 11, 8, 19, tzinfo=timezone.utc)
        self.labels = []
        for i in range(5):
            country = 'ROK' if i < 3 else 'JPN'
            source = 'mofa_kr' if country == 'ROK' else 'kantei_jp'
            identity = f'live-test-{i}'
            url = f'https://example.org/{identity}'
            text = f'Test institutional speech {i}: cooperation and open dialogue between the two sides.'
            doc = Document(source, url, identity, None, text, 'en', 'Official office',
                           event_date='2026-11-07', country_scope=country,
                           content_policy='excerpt_only', official_identifier=identity)

            def saved(doc_id, statement_id, added):
                self.assertTrue(added)
                evidence = dict(content_sha256=digest(text), source=source, url=url, country=country,
                                speaker='Speaker', title=identity, institution='government',
                                fetch_sha256=digest(text), spoken_date='2026-11-07', published_date=None)
                self.db.execute('INSERT INTO live_review_queue VALUES (?,?,?,?,?)',
                                (identity, doc_id, statement_id, self.capture.isoformat(), json.dumps(evidence)))

            ingest(self.store, doc, statements=[attributed(doc, 'government')], on_statement=saved)
            self.labels.append(dict(id=identity, content_sha256=digest(text), direction='cooperative',
                                    cooperation_present=True, target_country='JPN' if country == 'ROK' else 'ROK',
                                    confrontation_intensity=0, position_ownership='own', confidence='medium',
                                    summary_ru='Поддержка диалога.', reason_ru='Двустороннее сотрудничество.'))

    def test_batch_is_hash_bound_and_repeat_safe(self):
        wrong = dict(self.labels[-1], content_sha256='invalid')
        with self.assertRaises(ValueError):
            import_batch(self.db, [*self.labels[:-1], wrong], self.issued)
        self.assertEqual(self.db.execute('SELECT count(*) FROM live_annotations').fetchone()[0], 0)
        self.assertEqual(import_batch(self.db, self.labels, self.issued), 5)
        self.assertEqual(import_batch(self.db, self.labels, self.issued), 0)

    def test_seal_and_database_append_only(self):
        import_batch(self.db, self.labels, self.issued)
        with patch('scripts.live_dri.load_corpora', return_value=([], [])):
            result, added = issue(self.db, self.issued)
            self.assertTrue(added)
            self.assertEqual(result['calculation']['expanded']['score'], 0)
            self.assertIsNone(result['calculation']['balanced']['score'])
            self.assertEqual(result['horizon_start'], '2026-11-09')
            self.assertEqual(result['horizon_end'], '2026-12-08')
            self.assertEqual(issue(self.db, self.issued), (result, False))
        for command in ('UPDATE live_forecasts SET payload=payload',
                        'DELETE FROM live_forecasts',
                        'INSERT OR REPLACE INTO live_forecasts SELECT * FROM live_forecasts'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(command)
            self.db.rollback()
        self.assertEqual(verify_journal(self.db), [result])

    def test_cutoff_excludes_later_capture_and_future_context(self):
        import_batch(self.db, self.labels, self.issued)
        context=dict(collection_cutoff='2026-11-08T17:00:00+00:00',known_events=[])
        with patch('scripts.live_dri.load_corpora', return_value=([], [])):
            with self.assertRaises(ValueError):
                issue(self.db,self.issued,context)
        context['collection_cutoff']='2026-11-08T20:00:00+00:00'
        with self.assertRaises(ValueError):
            issue(self.db,self.issued,context)
        context['collection_cutoff']=self.capture.isoformat()
        context['known_events']=[dict(known_since='2026-11-09')]
        with self.assertRaises(ValueError):
            issue(self.db,self.issued,context)

    def test_context_is_sealed_and_repeat_cannot_replace_it(self):
        import_batch(self.db,self.labels,self.issued)
        context=dict(collection_cutoff=self.capture.isoformat(),known_events=[],note='Original')
        with patch('scripts.live_dri.load_corpora',return_value=([],[])):
            result,added=issue(self.db,self.issued,context)
            self.assertTrue(added)
            repeated,added=issue(self.db,self.issued,dict(context,note='Changed'))
            self.assertFalse(added)
            self.assertEqual(repeated['research_context']['note'],'Original')
        self.assertEqual(verify_journal(self.db),[result])
