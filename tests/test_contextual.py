"""Behavioural synthetic cases; no independent political-label accuracy claim."""
import copy
import json
import unittest
from dri.contextual import ContextClassifier,compact_view
from dri.contextual_index import aggregate,monthly_rows
from dri.contextual_outputs import merge_expert_fields
from dri.analytical_sample import digest
from dri.paths import ROOT

RULES=json.loads((ROOT/'config/dri_v02_rules.json').read_text(encoding='utf-8'))
CONFIG=json.loads((ROOT/'config/dri_v02.json').read_text(encoding='utf-8'))

class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=ContextClassifier(RULES)

    def classify(self,text,language='en',target='JPN',fragments=None):
        return self.c.classify({'language':language,'target_country':target,'exclusion_reason':None,
            'fragments':fragments or [{'text':text,'ref':{'document_id':1}}]})

    def test_short_strong_signal_and_length_invariance(self):
        short='We will impose sanctions on Japan.'
        a=self.classify(short);b=self.classify(short+' Bilateral documents were archived for administrative purposes.'*40)
        self.assertEqual(a['intensity'],3);self.assertEqual(a['intensity'],b['intensity'])

    def test_multiple_quotation_blocks_not_multiple_scores(self):
        f={'text':'We strongly protest against Japan.','ref':{'document_id':1}}
        a=self.classify('',fragments=[f]);b=self.classify('',fragments=[f,f])
        self.assertEqual(a['intensity'],2);self.assertEqual(a['intensity'],b['intensity'])

    def test_english_neutral_and_cooperative_need_explicit_frame(self):
        self.assertEqual(self.classify('We met with the Japanese delegation.')['direction'],'neutral')
        self.assertEqual(self.classify('We will strengthen bilateral cooperation with Japan.')['direction'],'cooperative')
        self.assertIsNone(self.classify('We reviewed Japan in a technical appendix.')['intensity'])

    def test_negation_does_not_become_neutral(self):
        r=self.classify('We do not strongly protest against Japan.')
        self.assertEqual(r['classification_status'],'needs_review');self.assertIsNone(r['intensity'])
        self.assertIn('negation',r['context_flags'])

    def test_quoted_and_reported_positions_abstain(self):
        for text in ['He said, "We strongly protest against Japan."','He said we strongly protest against Japan.']:
            self.assertIsNone(self.classify(text)['intensity'])

    def test_foreign_actor_is_not_owned_position(self):
        r=self.classify('Japan strongly protests against South Korea.')
        self.assertIsNone(r['intensity'])

    def test_third_country_hostility_not_bilateral(self):
        self.assertIsNone(self.classify('We strongly condemn North Korea while cooperating with Japan.')['intensity'])

    def test_bilateral_cooperation_with_third_country_topic(self):
        r=self.classify('北朝鮮への対応等を念頭に、日韓の戦略的連携を強化していくことが重要です。','ja','ROK')
        self.assertEqual(r['direction'],'cooperative');self.assertEqual(r['intensity'],0)

    def test_mixed_own_positions_abstain(self):
        r=self.classify('We strongly protest against Japan. We will strengthen cooperation with Japan.')
        self.assertEqual(r['classification_reason'],'mixed_owned_positions');self.assertIsNone(r['intensity'])

    def test_hypothetical_and_question_abstain(self):
        for text in ['If needed, we will impose sanctions on Japan.','Should we strongly protest against Japan?']:
            self.assertIsNone(self.classify(text)['intensity'])

    def test_historical_position_not_current_owned_position(self):
        self.assertIsNone(self.classify('In 1965 we strongly protest against Japan.')['intensity'])
        self.assertIsNone(self.classify('In 1965 we will strengthen cooperation with Japan.')['intensity'])

    def test_unclosed_quote_needs_review(self):
        result=self.classify('He announced: "We strongly protest against Japan.')
        self.assertIsNone(result['intensity']);self.assertTrue(result['quotation_present'])
        self.assertEqual(self.classify('We strongly protest against Japan. Later he said "unrelated unfinished passage')['intensity'],2)

    def test_korean_evaluation_separate_from_export_keyword(self):
        r=self.classify('일본의 과도하고 불합리한 조치에 한국은 대응했습니다.','ko')
        self.assertEqual(r['direction'],'confrontational');self.assertEqual(r['intensity'],1)
        self.assertIsNone(self.classify('일본의 수출 규제를 검토합니다.','ko')['intensity'])

    def test_korean_restriction_advocacy(self):
        r=self.classify('일본에 대해서 강력한 보복 조치를 해야 합니다.','ko')
        self.assertEqual(r['intensity'],3)

    def test_korean_cooperation_and_protest(self):
        self.assertEqual(self.classify('우리는 일본과 협력을 강화하겠습니다.','ko')['direction'],'cooperative')
        self.assertEqual(self.classify('우리 정부는 일본에 강력히 항의합니다.','ko')['intensity'],2)

    def test_japanese_negation_and_intrinsic_negation(self):
        self.assertIsNone(self.classify('韓国に強く抗議しない。','ja','ROK')['intensity'])
        self.assertEqual(self.classify('韓国の措置は容認できない。','ja','ROK')['intensity'],1)

    def test_japanese_own_restriction_and_foreign_subject(self):
        self.assertEqual(self.classify('我が国は韓国への制裁を実施する。','ja','ROK')['intensity'],3)
        self.assertIsNone(self.classify('韓国は強く抗議しました。','ja','ROK')['intensity'])

    def test_cjk_pdf_spaces_preserve_offsets(self):
        text='우리 정부는 일본에 강력히 항 의합니다.'
        r=self.classify(text,'ko');e=r['evidence'][0]
        self.assertEqual(r['intensity'],2)
        self.assertIn('항 의',text[e['char_start']:e['char_end']])
        view,positions=compact_view('日 韓','ja');self.assertEqual(view,'日韓');self.assertEqual(positions,[0,2])

    def test_korean_boundaries_precede_space_removal(self):
        r=self.classify('1970년의 사건을 보도했습니다. 일본의 부당한 조치에 우리는 대응합니다.','ko')
        self.assertEqual(r['intensity'],1)
        self.assertEqual(r['classification_status'],'rule_supported')

    def unit(self,i=1,intensity=2,status='rule_supported',country='ROK',source='mofa_kr'):
        return dict(unit_id=i,exclusion_reason=None,classification_status=status,intensity=intensity,
            direction='undetermined' if status!='rule_supported' else 'confrontational' if intensity else 'cooperative',
            country=country,source_id=source,institution='Institution',language='en',selection_theme='diplomatic_contacts',date='2020-01-01')

    def test_unknowns_not_zero_and_source_length_not_weight(self):
        us=[self.unit(),self.unit(2,0),self.unit(3,None,'needs_review')]
        us[0]['token_count']=10000;us[1]['token_count']=5
        r=aggregate(us,CONFIG)
        self.assertEqual(r['observed_intensity_0_3'],1);self.assertEqual(r['classified_units'],2)
        self.assertAlmostEqual(r['undetermined_share'],1/3)
        self.assertAlmostEqual(r['abstention_only_lower_bound'],2/3)
        self.assertAlmostEqual(r['abstention_only_upper_bound'],5/3)

    def test_months_without_data_or_without_labels_are_missing(self):
        config={**CONFIG,'period_start':'2020-01','period_end':'2020-02'}
        rows=monthly_rows([self.unit(intensity=None,status='needs_review')],config)
        pooled=[r for r in rows if r['scope']=='pooled_sample']
        self.assertIsNone(pooled[0]['observed_intensity_0_3']);self.assertIsNone(pooled[1]['observed_intensity_0_3'])
        self.assertEqual(pooled[0]['measurement_status'],'no_classified_units');self.assertEqual(pooled[1]['measurement_status'],'no_data')

    def test_bilateral_coverage_guard(self):
        us=[self.unit(i) for i in range(5)]
        self.assertFalse(aggregate(us,CONFIG,True)['coverage_supported'])
        self.assertEqual(aggregate(us,CONFIG,True)['dri_v02'],2)
        us[-1]['country']='JPN'
        self.assertTrue(aggregate(us,CONFIG,True)['coverage_supported'])

    def test_source_sensitivity_includes_unaffected_months(self):
        units=[self.unit(),{**self.unit(2,source='kokkai_jp'), 'date':'2020-02-01'}]
        rows=monthly_rows(units,{**CONFIG,'period_start':'2020-01','period_end':'2020-02'})
        january=next(r for r in rows if r['scope']=='pooled_sample' and r['month']=='2020-01')
        self.assertEqual(january['sensitivity']['without_source:kokkai_jp']['observed_intensity_0_3'],january['dri_v02'])

    def test_noun_protest_is_not_an_owned_performative(self):
        self.assertIsNone(self.classify('The protest against Japan was discussed in a report.')['intensity'])

    def test_partner_plus_demand_is_mixed(self):
        r=self.classify('韓国は重要な隣国であり、適切な対応を強く求めてまいります。','ja','ROK')
        self.assertEqual(r['classification_reason'],'mixed_owned_positions');self.assertIsNone(r['intensity'])

    def test_japanese_neutral_factual_meeting(self):
        r=self.classify('韓国との間で日韓の防衛相会談を実施をいたしまして、意見交換を行ったわけでございます。','ja','ROK')
        self.assertEqual(r['direction'],'neutral')

    def test_deterministic_and_excluded_never_counted(self):
        us=[self.unit(i) for i in range(5)];us[0]['exclusion_reason']='nonpolitical'
        self.assertEqual(aggregate(us,CONFIG)['available_units'],4)
        self.assertEqual(digest(aggregate(us,CONFIG)),digest(aggregate(copy.deepcopy(us),CONFIG)))

    def test_expert_labels_preserved_on_same_snapshot(self):
        rec=dict(input_text_sha256='a',rules_sha256='b',expert_direction=None,expert_notes=None)
        prev={**rec,'expert_direction':'neutral','expert_notes':'Independent review'}
        self.assertEqual(merge_expert_fields(rec,prev)['expert_direction'],'neutral')

    def test_changed_annotated_snapshot_cannot_silently_overwrite(self):
        rec=dict(input_text_sha256='a',rules_sha256='new',expert_direction=None)
        with self.assertRaises(ValueError):merge_expert_fields(rec,{**rec,'rules_sha256':'old','expert_direction':'cooperative'})

    def test_empty_expert_form_can_be_refreshed(self):
        rec=dict(input_text_sha256='a',rules_sha256='new',expert_direction=None)
        self.assertEqual(merge_expert_fields(rec,{**rec,'rules_sha256':'old'}),rec)

if __name__=='__main__':unittest.main()
