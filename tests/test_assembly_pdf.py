import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dri.connectors.assembly_pdf import segment,parse_label,JAPAN,floor_episodes,literal_quote_blocks,eligible
from dri.models import Document
from dri.statements import Statement,Quote
from dri.storage import Store
from dri.paths import ROOT
from dri.repository import register_sources,ingest
from dri.publication import internal_statement,WITHHELD

class AssemblyPDFTests(unittest.TestCase):
    def test_name_order_and_administrative_marker(self):
        self.assertEqual(parse_label('박주선 위원 일본과 협력합니다.'),('박주선','위원','일본과 협력합니다.'))
        self.assertEqual(parse_label('외교부장관 강경화 답변드립니다.'),('강경화','외교부장관','답변드립니다.'))
        self.assertEqual(parse_label('의안 제출 목록입니다.'),(None,None,''))
        self.assertEqual(parse_label('정무위원장대리 최승재 보고합니다.'),('최승재','정무위원장대리','보고합니다.'))

    def test_appendix_after_adjournment_is_not_a_speech(self):
        ts=segment([(1,'L',10,20,'◯박주선 위원 발언합니다.'),
            (1,'L',30,40,'(12시15분 산회)'),(2,'L',10,20,'◯의안 제출 부록')])
        self.assertEqual(len(ts),1);self.assertTrue(ts[0].closed)

    def test_cross_column_and_page_turn_is_not_truncated(self):
        lines=[(1,'L',100,110,'◯박주선 위원 시작'),(1,'R',80,90,'일본과 협력'),
               (2,'L',80,90,'계속합니다.'),(2,'L',100,110,'◯외교부장관 강경화 다음 답변')]
        ts=segment(lines)
        self.assertEqual(len(ts),2);self.assertEqual(ts[0].speaker_name,'박주선')
        self.assertEqual(ts[0].text,'시작\n일본과 협력\n계속합니다.')
        self.assertTrue(ts[0].closed);self.assertFalse(ts[1].closed)
        self.assertEqual(ts[0].spans[-1][:2],[2,'L'])

    def test_interruptions_share_episode_later_appearance_is_new(self):
        ts=[dict(ordinal=i,speaker_name=n,role=r) for i,n,r in
            [(1,'박주선','위원'),(2,'강경화','외교부장관'),(3,'윤상현','위원장'),
             (4,'박주선','위원'),(5,'이수혁','위원'),(6,'박주선','위원')]]
        episodes=floor_episodes(ts)
        self.assertEqual(episodes[1],episodes[4]);self.assertEqual(episodes[2],episodes[1])
        self.assertNotEqual(episodes[1],episodes[6])

    def test_stage_directions_never_become_attributed_quotes(self):
        a='일본과 협력에 관한 첫 발언입니다. '*10;b='대화를 통해 문제를 해결하겠습니다. '*10
        blocks=literal_quote_blocks(a+'\n(장내 소란)\n'+b+'\n(｢반대합니다｣ 하는 의원 있음)')
        self.assertEqual(len(blocks),2)
        self.assertNotIn('반대합니다',''.join(blocks))

    def test_korean_north_only_and_ordinary_il_han_are_not_japan(self):
        self.assertIsNone(JAPAN.search('북한의 핵실험에 관한 논의'))
        self.assertIsNone(JAPAN.search('통일한 나라의 미래'))
        self.assertIsNotNone(JAPAN.search('한·일 경제 협력과 일본'))

    def test_unclosed_and_mapping_errors_rejected(self):
        ts=segment([(1,'L',10,20,'◯박주선 위원 일본에 대한 '+('협력 '*60)),(1,'L',30,40,'\ufffd')])
        self.assertFalse(eligible(ts[0].metadata()))

    def test_import_requires_matching_sealed_source_review(self):
        from scripts.collect_assembly_pdf import reviewed_statements
        from dri.connectors.assembly import MeetingReference
        text='일본과 협력하여 양국의 경제 및 안보를 논의합니다. '*8
        ref=MeetingReference('000001','1','2019-07-30','Committee','Synthetic meeting',
            'https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=1',())
        t=dict(ordinal=1,speaker_name='박주선',role='위원',text=text,spans=[[1,'L',100,200]],closed=True,rejection=None)
        q=dict(pdf_url=ref.pdf_url,pdf_sha256='original',ordinal=1,speaker_name='박주선',role='위원',
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),spans=t['spans'],status='pass',checks={k:True for k in ['author','date','boundaries','korean_text','bilateral_relevance']})
        statements,selected=reviewed_statements(ref,{'turns':[t]},[q],'original')
        self.assertEqual(len(statements),1);self.assertEqual(len(selected),1)
        with self.assertRaises(ValueError):reviewed_statements(ref,{'turns':[{**t,'text':text+'changed'}]},[q],'original')
        with self.assertRaises(ValueError):reviewed_statements(ref,{'turns':[t]},[q],'new-pdf-revision')
        with self.assertRaises(ValueError):reviewed_statements(ref,{'turns':[t]},[{**q,'checks':{}}],'original')

    def test_internal_export_and_review_never_publish_source_text(self):
        folder=ROOT/'data/test-tmp';folder.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as td:
            s=Store(td,memory=True);register_sources(s)
            secret='INTERNAL_SOURCE_SENTINEL Japan cooperation. '*8
            doc=Document('assembly_kr','https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=1',
                'Synthetic minutes',None,secret,'ko','Assembly',event_date='2019-07-30',content_policy='internal_research_only')
            st=Statement('assembly:1:floor:1','ROK','JPN','Assembly','Synthetic floor episode',None,
                spoken_date='2019-07-30',speaker_name='Fixture',attribution_evidence='Synthetic test',quotes=(Quote(secret,'ko'),))
            first=ingest(s,doc,statements=[st]);again=ingest(s,doc,statements=[st])
            self.assertEqual(again['statements_added'],0);self.assertEqual(first['documents_added'],1)
            self.assertTrue(internal_statement(s.db,1))
            s.export();export=(Path(td)/'corpus.jsonl').read_text(encoding='utf-8')
            self.assertNotIn('INTERNAL_SOURCE_SENTINEL',export)
            self.assertEqual(json.loads(export)['text'],'')
            (Path(td)/'docs').mkdir()
            from dri.quality import _review
            with patch('dri.quality.ROOT',Path(td)):_review(s)
            html=(Path(td)/'docs/REVIEW_TABLE.html').read_text(encoding='utf-8')
            self.assertNotIn('INTERNAL_SOURCE_SENTINEL',html);self.assertIn(WITHHELD,html)
            self.assertEqual(s.db.execute('SELECT text FROM documents').fetchone()[0],secret)
            s.db.close()

if __name__=='__main__':unittest.main()
