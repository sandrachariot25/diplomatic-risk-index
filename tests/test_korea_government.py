import unittest
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from dataclasses import replace
from dri.connectors.korea_government import parse
from dri.storage import Store
from dri.repository import register_sources, ingest

URL='https://www.korea.kr/briefing/speechView.do?newsId=132038430'
RECORD=dict(name='이재명',role='대통령',institution='Presidential administration, Republic of Korea',
            addressee='Japanese public',theme='diplomatic_contacts',evidence='Title and labelled date')

def fixture(licence='제4유형',date='2026.01.13'):
    return ('<div class="view_title">이재명 대통령 한일 공동언론발표문</div>'
            '<div class="info">연설자 : 대통령<br>연설일 : '+date+'</div>'
            '<div class="view_cont"><p>일본 국민 여러분께 감사드립니다.</p><p>'+('양국 협력을 논의합니다. '*20)+'</p></div>'
            '<div class="kogl">공공누리 '+licence+'</div>')

class GovernmentTests(unittest.TestCase):
    def test_restricted_requires_authorization(self):
        with self.assertRaises(ValueError):parse(fixture(),URL,RECORD)

    def test_unknown_licence_rejected(self):
        with self.assertRaises(ValueError):parse(fixture('없음'),URL,RECORD,restricted_research=True)

    def test_speech_date_is_not_publication(self):
        doc,st=parse(fixture(),URL,RECORD,restricted_research=True)
        self.assertIsNone(doc.published_date)
        self.assertEqual(st[0].spoken_date,'2026-01-13')
        self.assertEqual(doc.text_completeness,'complete_published_body')
        self.assertIn('NONCOMMERCIAL',doc.rights)

    def test_no_inferred_speaker(self):
        with self.assertRaises(ValueError):parse(fixture(),URL,{**RECORD,'name':'다른 사람'},restricted_research=True)

    def test_outside_period(self):
        with self.assertRaises(ValueError):parse(fixture(date='2026.11.01'),URL,RECORD,restricted_research=True)

    def test_multiple_bodies_and_media_fail_closed(self):
        for h in (fixture()+'<div class="view_cont">extra</div>',fixture().replace('<p>일본','<img src="x"><p>일본')):
            with self.assertRaises(ValueError):parse(h,URL,RECORD,restricted_research=True)

    def test_idempotent_and_different_speeches_preserved(self):
        store=Store(memory=True);register_sources(store)
        try:
            doc,sts=parse(fixture(),URL,RECORD,restricted_research=True)
            first=ingest(store,doc,statements=sts)
            second=ingest(store,doc,statements=sts)
            self.assertEqual((first['documents_added'],first['statements_added'],first['quotes_added']),(1,1,1))
            self.assertEqual((second['documents_added'],second['statements_added'],second['quotes_added']),(0,0,0))
            other=replace(doc,url=URL.replace('132038430','132038431'),event_date='2026-01-14',official_identifier='korea.kr:132038431')
            st=replace(sts[0],event_key='official:korea.kr:132038431',spoken_date='2026-01-14')
            result=ingest(store,other,statements=(st,))
            self.assertEqual(result['statements_added'],1)
            self.assertGreater(result['possible_matches'],0)
        finally:store.db.close()

    def test_type1_needs_no_restricted_permission(self):
        doc,_=parse(fixture('제1유형'),URL,RECORD)
        self.assertEqual(doc.content_policy,'full_text')

    def test_institutional_briefing_never_invents_oral_speaker(self):
        html=fixture().replace('연설자 : 대통령<br>연설일 : 2026.01.13','2020.03.08 청와대')
        doc,statements=parse(html,URL.replace('speechView','presidentView'),
                             {**RECORD,'name':None,'role':None},restricted_research=True)
        self.assertEqual(doc.published_date,'2020-03-08')
        self.assertIsNone(statements[0].spoken_date)
        self.assertIsNone(statements[0].speaker_name)
        self.assertEqual(doc.observation_type,'official_written_briefing')

    def test_collector_live_schema_checkpoint_and_replay(self):
        from scripts import collect_domestic
        store=Store(memory=True)
        record={**RECORD,'url':URL,'id':'132038430','route':'speechView'}
        output=io.StringIO()
        with patch.object(collect_domestic,'Store',return_value=store), \
             patch.object(store,'record_fetch',return_value=('', 'fixture-only', 'test-time')), \
             patch.object(collect_domestic,'RECORDS',[record]), \
             patch.object(collect_domestic,'Client') as client, \
             patch.object(collect_domestic,'ingest',wraps=ingest) as importer, \
             patch('sys.argv',['collect_domestic','--execute','--restricted-research']), redirect_stdout(output):
            client.return_value.get.return_value=(fixture(),('', 'test', 'date'),URL)
            collect_domestic.main()
            self.assertEqual(client.return_value.get.call_count,1)
            self.assertEqual(importer.call_count,2)
        self.assertIn('"documents_processed": 1',output.getvalue())
        self.assertIn('"other_errors": 0',output.getvalue())

if __name__=='__main__':unittest.main()
