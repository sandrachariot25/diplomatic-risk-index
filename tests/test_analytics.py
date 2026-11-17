"""Synthetic behavioural checks; passing tests does not validate political accuracy."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from dri.analytics import monthly_components,robust_background,calculate
from dri.analytical_sample import distinct_fragments,assemble_unit,digest
from dri.tokenization import Segmenter
from dri.rhetoric import Matcher
from dri.paths import ROOT

CONFIG=json.loads((ROOT/'config/dri_v01.json').read_text())
LEXICON=json.loads((ROOT/CONFIG['lexicon']).read_text(encoding='utf-8'))

class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.segmenter=Segmenter();cls.matcher=Matcher(LEXICON,cls.segmenter)

    def matches(self,text,lang='en',target='JPN'):
        _,m=self.matcher.match(text,lang,target);return m

    def counted(self,*args,**kwargs):return [m for m in self.matches(*args,**kwargs) if m['decision']=='counted']

    def test_inflection_and_longest_nonoverlap(self):
        self.assertEqual(len(self.counted('We strongly condemned Japan.')),1)
        self.assertEqual(len(self.counted('We strongly condemn Japan and strongly condemn Japan again.')),2)

    def test_word_boundaries_not_substrings(self):
        self.assertEqual(self.counted('Japanese Protestant condemnations were catalogued.'),[])

    def test_korean_segmentation_and_conjugation(self):
        ts=self.segmenter.tokenize('일본의조치를강력히규탄합니다.','ko')
        self.assertGreater(len(ts),5)
        self.assertEqual(len(self.counted('우리 정부는 일본의 조치를 강력히 규탄합니다.','ko')),1)

    def test_korean_pdf_word_wrap_tolerance(self):
        self.assertIn('규제',[t.lemma for t in self.segmenter.tokenize('수출규 제','ko')])

    def test_japanese_segmentation_and_lemma(self):
        ts=self.segmenter.tokenize('韓国の措置に強く抗議しました。','ja')
        self.assertGreater(len(ts),5)
        self.assertEqual(len(self.counted('韓国の措置に強く抗議しました。','ja','ROK')),1)

    def test_explicit_and_intrinsic_negation(self):
        self.assertEqual(self.counted('We do not strongly condemn Japan.'),[])
        self.assertEqual(self.counted('韓国を強く非難しない。','ja','ROK'),[])
        self.assertEqual(len(self.counted('韓国の措置は容認できない。','ja','ROK')),1)
        self.assertEqual(len(self.counted('일본의 조치는 용납할 수 없다.','ko')),1)

    def test_quoted_or_reported_foreign_position(self):
        self.assertEqual(self.counted('Japan said "we strongly condemn South Korea".'),[])
        self.assertEqual(self.counted('It was reported that Japan imposed sanctions.'),[])

    def test_third_country_is_not_counterpart(self):
        self.assertEqual(self.counted('We strongly condemn North Korea while cooperating with Japan.'),[])
        self.assertEqual(self.counted('일본과 협력하며 북한을 강력히 규탄합니다.','ko'),[])

    def test_missing_target_and_foreign_subject(self):
        self.assertEqual(self.counted('We strongly condemn these actions.'),[])
        self.assertEqual(self.counted('Japan strongly condemns these actions.'),[])
        self.assertEqual(len(self.counted('The ROK government strongly condemns Japan.')),1)

    def test_measures_description_is_not_automatic_hostility(self):
        self.assertEqual(self.counted('We discuss Japan export restrictions.'),[])
        self.assertEqual(len(self.counted('We criticize Japan export restrictions.')),1)
        self.assertEqual(self.counted('일본의 수출규제법을 검토합니다.','ko'),[])
        self.assertEqual(self.counted('韓国の輸出規制法を批判します。','ja','ROK'),[])

    def test_humanitarian_concern_is_not_directed_hostility(self):
        self.assertEqual(self.counted('We express grave concern about Japan after the earthquake.'),[])

    def test_hypothetical_not_asserted(self):
        self.assertEqual(self.counted('If Japan acts, we could take countermeasures.'),[])

    def test_document_and_quotation_never_add_same_words(self):
        text='We strongly condemn Japan.'
        s={'id':1,'event_key':'official:1','country':'ROK','target_country':'JPN','speaker_name':None,
           'institution':'MOFA','spoken_date':None,'published_date':'2020-01-01','original_language':'en'}
        d={'id':1,'source':'mofa_kr','source_type':'primary','language':'en','url':'https://example.org/1',
           'text':text,'content_policy':'full_text','metadata':{'text_completeness':'complete_published_body','observation_type':'official_institutional_statement'}}
        qs=[{'id':i,'text':text,'published_language':'en'} for i in [1,2]]
        u=assemble_unit([s],[d],qs,{1:[{'document_id':1}],2:[{'document_id':1}]},{},{})
        self.assertEqual(len(u['fragments']),1);self.assertEqual(u['fragments'][0]['text'],text)
        self.assertEqual(u['date_basis'],'publication_date_of_official_statement')

    def test_duplicate_and_overlapping_quote_intervals(self):
        a={'text':'alpha beta gamma delta','ref':{'document_id':1},'source_interval':[0,22],'_source':'alpha beta gamma delta epsilon'}
        b={'text':'gamma delta epsilon','ref':{'document_id':1},'source_interval':[11,30],'_source':a['_source']}
        self.assertEqual(len(distinct_fragments([a,a,b])),1)
        # Independent repeated floor turns remain distinct, even with identical words.
        self.assertEqual(len(distinct_fragments([{**a,'scope':'turn1'},{**a,'scope':'turn2'}])),2)

    def test_transitive_source_overlap_does_not_double_count_bridge(self):
        source='abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMN'
        fs=[{'text':source[a:b],'ref':{'document_id':1,'quote_id':i},
             'source_interval':[a,b],'_source':source} for i,(a,b) in enumerate([(0,20),(30,50),(15,35)])]
        merged=distinct_fragments(fs)
        self.assertEqual(len(merged),1);self.assertEqual(merged[0]['text'],source)

    def unit(self,n=1,tokens=1000,hits=1,month='2020-01'):
        return dict(unit_id=n,statement_ids=[n],country='ROK',target_country='JPN',language='en',source_id='mofa_kr',
            source_type='primary',text_form='complete_official_statement',version='original',component_role='main',
            date=month+'-01',date_basis='speech_date',token_count=tokens,expression_count=hits,
            suppressed_candidates=0,exclusion_reason=None)

    def test_micro_rate_not_equal_average_of_short_and_long(self):
        config={**CONFIG,'period_start':'2020-01','period_end':'2020-02'}
        rows=monthly_components([self.unit(tokens=10,hits=1),self.unit(n=2,tokens=990,hits=0)],config)
        self.assertEqual(rows[0]['raw_rate_per_1000'],1)
        self.assertEqual(rows[0]['status'],'insufficient_volume')
        self.assertIsNone(rows[1]['raw_rate_per_1000']);self.assertIsNone(rows[1]['expression_count'])
        self.assertEqual(rows[1]['measurement_state'],'no_texts')

    def test_zero_observed_is_different_from_missing(self):
        rows=monthly_components([self.unit(hits=0)],{**CONFIG,'period_start':'2020-01','period_end':'2020-02'})
        self.assertEqual(rows[0]['raw_rate_per_1000'],0)
        self.assertIsNone(rows[1]['raw_rate_per_1000'])

    def test_sparse_and_zero_mad_never_produce_fake_anomaly(self):
        history=[dict(month=f'2019-{i:02}',status='supported',raw_rate_per_1000=0) for i in range(1,13)]
        r=robust_background(dict(month='2020-01',status='supported',raw_rate_per_1000=100),history,CONFIG)
        self.assertIsNone(r['robust_deviation']);self.assertIsNone(r['anomaly_flag'])

    def test_no_future_information_changes_historical_background(self):
        history=[dict(month=f'2019-{i:02}',status='supported',raw_rate_per_1000=i) for i in range(1,13)]
        current=dict(month='2020-01',status='supported',raw_rate_per_1000=20)
        old=robust_background(current,history,CONFIG)
        new=robust_background(current,history+[dict(month='2021-01',status='supported',raw_rate_per_1000=1e9)],CONFIG)
        self.assertEqual(old,new);self.assertEqual(old['background_months'],12)
        self.assertAlmostEqual(old['robust_deviation'],(20-6.5)/(1.4826*3))

    def test_end_to_end_reproducibility_on_synthetic_snapshot(self):
        unit=self.unit();unit.update(event_key='synthetic:1',speaker_name=None,institution='MOFA',
            document_ids=[1],quote_ids=[1],source_urls=['https://example.org/1'],input_text_sha256='fixture',
            fragments=[{'text':'We strongly condemn these actions by Japan.','ref':{'document_id':1}}])
        with patch('dri.analytics.load_sample',side_effect=lambda p:([copy.deepcopy(unit)],{'statement_records':1})):
            a=calculate(Path('unused'),CONFIG,LEXICON);b=calculate(Path('unused'),CONFIG,LEXICON)
        self.assertEqual(digest(a),digest(b));self.assertEqual(a['units'][0]['expression_count'],1)

if __name__=='__main__':unittest.main()
