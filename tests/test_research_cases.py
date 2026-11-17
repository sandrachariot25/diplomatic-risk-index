from datetime import date, datetime, timedelta, timezone
import unittest
from scripts.research_cases import topical_evidence, aggregate, periods
from scripts.collect_live_dri import plan, KOREA_PATTERN


class ResearchCasesTests(unittest.TestCase):
    def test_multitopic_original_languages_and_unassigned(self):
        self.assertEqual(set(topical_evidence('사도광산 경제 협력 안보')), {
            'historical_memory','trade_economy','diplomatic_cooperation','security'})
        self.assertEqual(topical_evidence('挨拶を申し上げます。'), {})
        self.assertEqual(set(topical_evidence('竹島と輸出管理')), {'other_bilateral','trade_economy'})

    def test_offsets_recover_original_evidence(self):
        text='We discuss Sado and security cooperation.'
        for matches in topical_evidence(text).values():
            for m in matches:
                self.assertEqual(text[m['start']:m['end']],m['term'])

    def test_empty_and_excluded_are_not_zero_risk(self):
        self.assertIsNone(aggregate([])['cooperation_share'])
        row=dict(direction='uncertain',speaker=None,cooperation=False,intensity=None,topics=[])
        self.assertEqual(aggregate([row])['coverage'],'empty')
        self.assertEqual(aggregate([row])['excluded'],1)

    def test_first_public_report_and_nonoverlap(self):
        windows=periods(dict(date='2026-09-09',first_report='2026-09-08'),'2026-11-09')
        self.assertEqual(windows[0][2],date(2026,9,7))
        self.assertEqual(windows[1][1],date(2026,9,8))
        self.assertEqual(windows[2][2],date(2026,11,9))
        for left,right in zip(windows,windows[1:]):
            self.assertEqual(left[2]+timedelta(days=1),right[1])

    def test_live_plan_includes_all_window_months(self):
        urls=plan(date(2026,11,9))[2]
        self.assertEqual(len(urls),8)
        self.assertTrue(any('2026-08' in url for _,url in urls))
        self.assertTrue(KOREA_PATTERN.search('한·미·일 해외재난대응협력'))

