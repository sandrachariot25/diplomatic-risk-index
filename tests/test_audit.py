"""Research audit invariants: inclusion, dated metadata, sample strata and non-destructive review."""
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from urllib.parse import parse_qs,urlsplit
from dri.paths import ROOT
from dri.storage import Store
from dri.models import Document
from dri.statements import Statement,Quote
from dri.research import institutional_metadata,stratified_sample
from dri.repository import register_sources,ingest
from dri.corpus_audit import pair_review,core_snapshot
from dri.connectors.kokkai import Kokkai
from dri.html import Tree

TEXT='The speaker discusses Korea and Japan in a specific parliamentary context without establishing party membership.'

class AuditTests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'data/test-tmp';folder.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=folder)
        self.store=Store(self.tmp.name,memory=True);register_sources(self.store)

    def tearDown(self):
        self.store.db.close();self.tmp.cleanup()

    def test_parliamentary_venue_not_confused_with_actor_institution(self):
        m=institutional_metadata({'speaker_office':'外務大臣'}, {'kokkai_jp'})
        self.assertEqual(m['institution_type'],'foreign_ministry')
        self.assertEqual(m['venue_institution_type'],'parliament')
        self.assertNotEqual(m['speaker_category'],'legislator')
        self.assertIsNone(m['government_opposition_status'])
        self.assertNotIn('weight',m)

    def test_ministerial_secretariat_not_mistaken_for_minister(self):
        m=institutional_metadata({'speaker_office':'外務省大臣官房参事官'}, {'kokkai_jp'})
        self.assertEqual(m['speaker_category'],'executive_official')
        self.assertEqual(m['institution_type'],'foreign_ministry')

    def test_individual_legislator_included_without_invented_party_status(self):
        m=institutional_metadata({'speaker_office':'参議院議員','speaker_name':'任意の議員'}, {'kokkai_jp'})
        self.assertEqual(m['institution_type'],'parliament')
        self.assertEqual(m['position_scope'],'individual_position')
        self.assertIsNone(m['political_affiliation'])
        self.assertIsNone(m['government_opposition_status'])

    def test_kokkai_default_query_not_minister_only(self):
        q=parse_qs(urlsplit(Kokkai().request_url(2020)).query)
        self.assertNotIn('speakerPosition',q)
        explicit=parse_qs(urlsplit(Kokkai().request_url(2020,speaker_position='大臣')).query)
        self.assertEqual(explicit['speakerPosition'],['大臣'])

    def test_kokkai_missing_role_and_group_not_excluded(self):
        item={'speechID':'fixture_001','speechURL':'https://kokkai.ndl.go.jp/txt/fixture/1','date':'2020-01-01',
              'speaker':'例示議員','speakerGroup':'例示会派','speech':'日韓関係について、韓国との対話に関する質問をいたします。'}
        pairs=Kokkai().parse(json.dumps({'speechRecord':[item]}))
        self.assertEqual(len(pairs),1)
        doc,st=pairs[0]
        self.assertIsNone(st.speaker_office)
        self.assertEqual(st.political_affiliation,'例示会派')
        self.assertIsNone(st.government_opposition_status)
        self.assertIsNone(st.published_date)

    def statement(self,event='fixture:one',speech='2020-01-01',published='2020-01-01'):
        return Statement(event,'JPN','ROK','House of Representatives','Fixture parliamentary reply',published,
                         spoken_date=speech,speaker_name='Example',speaker_office='Legislator',
                         attribution_evidence='Synthetic explicit source',quotes=(Quote(TEXT,'en'),))

    def test_party_status_requires_evidence_and_correct_as_of_date(self):
        with self.assertRaises(ValueError):replace(self.statement(),political_affiliation='Party').validate()
        with self.assertRaises(ValueError):replace(self.statement(),government_opposition_status='ruling',metadata_evidence='fixture').validate()
        with self.assertRaises(ValueError):replace(self.statement(),government_opposition_status='ruling',political_status_date='2025-01-01',metadata_evidence='fixture').validate()
        replace(self.statement(),government_opposition_status='opposition',political_status_date='2020-01-01',metadata_evidence='Explicit dated fixture').validate()

    def test_sample_reproducible_balanced_and_all_year_country_strata(self):
        rows=[]
        for year in range(2015,2027):
            for country in ('ROK','JPN'):
                for n in range(4):
                    role='MOFA Spokesperson' if country=='ROK' else '参議院議員'
                    src='mofa_kr' if country=='ROK' else 'kokkai_jp'
                    rows.append(dict(id=len(rows)+1,event_key=f'{year}:{country}:{n}',year=str(year),country=country,
                     spoken_date=f'{year}-01-01',published_date=None,theme=['security','historical_disputes','trade_economy','regional_cooperation'][n],
                     metadata=institutional_metadata({'speaker_office':role},{src}),sources=[{'source_type':'primary'}]))
        a=stratified_sample(rows);b=stratified_sample(list(reversed(rows)))
        self.assertEqual([r['id'] for r in a],[r['id'] for r in b])
        self.assertEqual(len(a),50)
        self.assertEqual(sum(r['country']=='ROK' for r in a),25)
        self.assertEqual(len({(r['year'],r['country']) for r in a}),24)

    def _pair(self,a,b):
        for i,st in enumerate((a,b)):
            d=Document('kokkai_jp',f'https://kokkai.ndl.go.jp/txt/fixture/{i}', 'Fixture',st.published_date,TEXT,'en','NDL',
                       content_policy='excerpt_only',event_date=st.spoken_date)
            ingest(self.store,d,statements=[st])
        candidate=self.store.db.execute("SELECT id,entity_type,left_id,right_id FROM duplicate_candidates WHERE entity_type='statement' LIMIT 1").fetchone()
        return candidate

    def test_known_different_speech_dates_never_auto_merge(self):
        p=self._pair(self.statement(),self.statement('fixture:two','2020-01-02','2020-01-02'))
        before=core_snapshot(self.store.db)
        classification,_=pair_review(self.store.db,p)
        self.assertEqual(classification,'different_known_speech_dates_keep_separate')
        self.assertEqual(core_snapshot(self.store.db),before)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM statements').fetchone()[0],2)

    def test_publication_dates_not_treated_as_speech_dates(self):
        p=self._pair(self.statement('official:one',None,'2020-01-01'),self.statement('official:two',None,'2021-01-01'))
        classification,_=pair_review(self.store.db,p)
        self.assertEqual(classification,'different_publications_speech_identity_unconfirmed')
        self.assertEqual(self.store.db.execute('SELECT status FROM duplicate_candidates WHERE id=?',(p[0],)).fetchone()[0],'possible_duplicate')

    def test_audit_view_keeps_unknown_dates_and_no_institution_weight(self):
        st=self.statement(speech=None)
        d=Document('kokkai_jp','https://kokkai.ndl.go.jp/txt/fixture/0','Fixture','2020-01-01',TEXT,'en','NDL',content_policy='excerpt_only')
        ingest(self.store,d,statements=[st])
        row=self.store.db.execute('SELECT statement_date,published_date,government_opposition_status FROM signal_timeline').fetchone()
        self.assertEqual(row,(None,'2020-01-01',None))
        names=[r[1] for r in self.store.db.execute('PRAGMA table_info(signal_timeline)')]
        self.assertFalse(any('weight' in n or 'prediction' in n for n in names))

    def test_current_audit_sample_and_all_original_pairs_persist(self):
        path=ROOT/'data/dri.sqlite3'
        if not path.exists():self.skipTest('Local corpus absent')
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        try:
            if db.execute('PRAGMA user_version').fetchone()[0]<3:self.skipTest('Audit not migrated yet')
            self.assertEqual(db.execute("SELECT count(*) FROM audit_samples WHERE sample_key='stratified-50-v1'").fetchone()[0],50)
            # This completed audit covered the original 164 pairs. Expansion pairs
            # must remain unreviewed until separately checked, not inherit reviews.
            self.assertEqual(db.execute('SELECT count(*) FROM duplicate_reviews WHERE candidate_id<=164').fetchone()[0],164)
            self.assertEqual(db.execute('SELECT count(*) FROM duplicate_candidates WHERE id<=164').fetchone()[0],164)
            self.assertEqual(db.execute("SELECT count(*) FROM duplicate_candidates WHERE status!='possible_duplicate'").fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM statement_assessments WHERE sentiment_verified=1').fetchone()[0],0)
        finally:db.close()

if __name__=='__main__':unittest.main()
