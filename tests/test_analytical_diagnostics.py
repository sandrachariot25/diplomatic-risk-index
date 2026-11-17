"""Provenance and coverage regression tests; no political accuracy claims."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from dri.analytical_sample import verified_completeness
from dri.analytical_diagnostics import component_diagnostics, document_inventory
from dri.paths import ROOT

class CompletenessTests(unittest.TestCase):
    def fixture(self, root):
        text='The Republic of Korea government comments on Japan. '*5
        title='MOFA Spokesperson Commentary on Japan'
        html=f'<div class="board_detail"><div class="bo_head"><h2>{title}</h2>2015-08-15</div><div class="bo_con">{text.strip()}</div></div>'
        raw=html.encode();path=root/'data/raw/example.bin';path.parent.mkdir(parents=True);path.write_bytes(raw)
        d=dict(id=1,source='mofa_kr',url='https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=1',language='en',published_date='2015-08-15',
               content_policy='legacy_unreviewed',text=text.strip(),metadata={'title':title})
        r=dict(document_id=1,url=d['url'],language='en',published_date=d['published_date'],
               text_completeness='complete_published_body',observation_type='official_institutional_statement',
               usage='internal_research_only_no_publication_permission_inferred',raw_path='raw/example.bin',
               raw_sha256=hashlib.sha256(raw).hexdigest(),body_sha256=hashlib.sha256(d['text'].encode()).hexdigest())
        return d,r

    def test_exact_source_proves_completeness_without_mutating_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            d,r=self.fixture(Path(tmp));old=copy.deepcopy(d)
            selected=verified_completeness(d,r,Path(tmp))
            self.assertEqual(d,old);self.assertEqual(selected['content_policy'],'legacy_unreviewed')
            self.assertEqual(selected['metadata']['text_completeness'],'complete_published_body')

    def test_tampered_raw_or_retained_body_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);d,r=self.fixture(root)
            for bad in ({**r,'raw_sha256':'0'*64},{**r,'body_sha256':'0'*64}):
                with self.assertRaises(ValueError):verified_completeness(d,bad,root)

    def test_matching_hashes_do_not_prove_body_extraction(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);d,r=self.fixture(root);d['text']+=' extra words'
            r['body_sha256']=hashlib.sha256(d['text'].encode()).hexdigest()
            with self.assertRaises(ValueError):verified_completeness(d,r,root)

    def test_identity_policy_and_path_guards(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp);d,r=self.fixture(root)
            for bad in ({**r,'document_id':2},{**r,'usage':'public'},{**r,'raw_path':'../outside.bin'}):
                with self.assertRaises(ValueError):verified_completeness(d,bad,root)

    def test_long_body_does_not_imply_full_speech(self):
        docs=[dict(id=1,text='x'*10000,metadata={}),dict(id=2,text='A report',metadata={
            'text_completeness':'complete_published_body','observation_type':'official_activity_report'})]
        _,summary=document_inventory(docs,[],[])
        bykind={r['kind']:r for r in summary}
        self.assertEqual(bykind['retained_fragment_or_unconfirmed']['documents'],1)
        self.assertEqual(bykind['full_activity_report']['unused'],1)
        self.assertNotIn('full_standalone_statement',bykind)

    def test_one_protocol_with_two_speeches_is_one_full_document(self):
        docs=[dict(id=1,text='protocol',metadata={'text_completeness':'complete_extracted_body_without_page_headers','observation_type':'parliamentary_minutes'})]
        units=[dict(document_ids=[1],exclusion_reason=None) for _ in range(2)]
        _,summary=document_inventory(docs,[{'document_id':1}],units)
        self.assertEqual(summary[0]['documents'],1);self.assertEqual(summary[0]['used'],1)

    def test_volume_failure_reasons_and_zero_denominators(self):
        u=dict(country='ROK',language='en',source_type='primary',source_id='example',text_form='complete_speech',version='original',
               exclusion_reason=None,component_role='main',token_count=100,expression_count=0)
        key='|'.join(u[k] for k in ('country','language','source_type','source_id','text_form','version'))
        rs=[dict(component_id=key,unit_count=n,token_count=t,expression_count=0 if n else None,status=s)
            for n,t,s in [(1,100,'insufficient_volume'),(5,100,'insufficient_volume'),(1,600,'insufficient_volume'),(0,0,'no_data')]]
        result=component_diagnostics([u],rs,{'min_month_units':5,'min_month_tokens':500})[0]
        self.assertEqual(result['volume_failures'],{'both':1,'units_only':1,'tokens_only':1})
        self.assertEqual(result['observed_months'],3);self.assertEqual(result['zero_observed_months'],3)
        self.assertEqual(result['no_data_months'],1)

if __name__=='__main__':unittest.main()
