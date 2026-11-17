"""Expansion is bounded, checkpointed and does not turn reports into speeches."""
import json,tempfile,unittest
from unittest.mock import patch
from dri.storage import Store
from dri.paths import ROOT
from dri.expansion import run_batch,convert,counts
from dri.repository import register_sources
from scripts.expand_kokkai import complete_quote

def html(title='ROK-Japan Economic Dialogue Held',text=None,stamp='2025-03-05'):
    text=text or 'Representatives of the Republic of Korea and Japan met to discuss economic cooperation. The two sides discussed further trade exchanges and agreed to continue consultations.'
    return f'<div class="board_detail"><div class="bo_head"><h2>{title}</h2>{stamp}</div><div class="bo_con"><p>{text}</p></div></div>'

class ExpansionTests(unittest.TestCase):
    def test_kokkai_missing_bilateral_quote_anchor_is_skipped(self):
        from dri.connectors.kokkai import Kokkai
        body=json.dumps({'speechRecord':[{'speech':'竹島について説明します。','date':'2024-01-01','speechID':'fixture','speechURL':'https://kokkai.ndl.go.jp/fixture','speaker':'fixture'}]})
        self.assertEqual(Kokkai().parse(body),[])
    def test_study_period_includes_october_31_only(self):
        url='https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=777'
        self.assertIsNotNone(convert(html(stamp='2026-10-31'),url))
        self.assertIsNone(convert(html(stamp='2026-11-01'),url))
    def setUp(self):
        folder=ROOT/'data/test-tmp';folder.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=folder)
        self.store=Store(self.tmp.name,memory=True);register_sources(self.store)
    def tearDown(self):self.store.db.close();self.tmp.cleanup()
    def seed(self):
        self.store.db.execute("INSERT INTO discovery_results(source_id,normalized_url,title,discovered_via,discovered_at) VALUES('mofa_kr',?,'Japan dialogue','fixture','2026-10-30')",('https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=777',))
        self.store.db.commit()
    def test_full_own_prose_does_not_create_statement(self):
        d=convert(html(),'https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=777')
        self.assertEqual(d.text_completeness,'complete_published_body')
        self.assertEqual(d.observation_type,'official_activity_report')
        self.assertIsNone(d.event_date)
        self.assertEqual(d.verification_status,'needs_review')
    def test_complete_japanese_quote_never_cuts_or_invents_a_sentence(self):
        good='日韓の協力を進めることが重要だと考えております。'
        self.assertEqual(complete_quote('○山田太郎君　'+good),good)
        self.assertIsNone(complete_quote('日韓の関係に関する発言'+'長'*100+'。'))
        self.assertIsNone(complete_quote('北朝鮮について議論しています。'))
    def test_third_party_remains_restricted(self):
        d=convert(html(text='Reuters provided by an external publisher. Japan and Korea discussed economic and political relations during consultations and reviewed cooperation.'),'https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=777')
        self.assertEqual(d.content_policy,'excerpt_only')
        self.assertEqual(d.analysis_status,'insufficient_text_pending_rights')
    def test_dprk_only_and_outside_period_excluded(self):
        for content in (html(title='Japan and DPRK',text='North Korea and Japan discussed issues. '*6),html(stamp='2014-12-31')):
            # DPRK-only needs no Republic of Korea linkage; date independently excluded.
            self.assertIsNone(convert(content,'https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=777'))
    def test_plan_does_not_mutate_or_fetch(self):
        self.seed();before=counts(self.store.db)
        with patch('dri.expansion.Client') as client:
            run_batch(self.store,execute=False)
            client.assert_not_called()
        self.assertEqual(before,counts(self.store.db))
    def test_second_run_never_fetches_imported_document(self):
        self.seed()
        with patch('dri.expansion.Client') as client:
            client.return_value.get.return_value=(html(),('', 'test-hash','2026-10-30'), 'https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=777')
            first=run_batch(self.store,execute=True)
            before=counts(self.store.db)
            second=run_batch(self.store,execute=True)
            self.assertIsNone(second)
            self.assertEqual(client.return_value.get.call_count,1)
        self.assertEqual(before,counts(self.store.db))
        self.assertEqual(before['statements'],0)
        self.assertEqual(len(first['repeat_verified_document_ids']),1)

if __name__=='__main__':unittest.main()
