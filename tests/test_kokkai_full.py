import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dri.migrations import KOKKAI_FULL_SCHEMA  # noqa: E402
from scripts.collect_kokkai_full import parse, save, resume_point, page_url  # noqa: E402


def record(sid, order=1, date='2019-07-03', url=None):
    return {'speechID': sid, 'issueID': 'X', 'date': date, 'nameOfHouse': '衆議院', 'nameOfMeeting': '外務委員会',
            'issue': '第1号', 'speechOrder': order, 'speaker': '山田太郎', 'speakerYomi': 'やまだたろう',
            'speakerGroup': '立憲民主党', 'speakerPosition': None, 'speakerRole': None,
            'speech': '○山田委員　韓国との関係について伺います。', 'speechURL': url or f'https://kokkai.ndl.go.jp/txt/{sid}',
            'meetingURL': 'https://kokkai.ndl.go.jp/txt/m'}


class KokkaiFullTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript(KOKKAI_FULL_SCHEMA)

    def test_parse_skips_roster_and_keeps_full_speech(self):
        body = json.dumps({'numberOfRecords': 2, 'nextRecordPosition': None,
                           'speechRecord': [record('a', order=0), record('b')]})
        total, nxt, rows = parse(body)
        self.assertEqual((total, nxt, [r['speechID'] for r in rows]), (2, None, ['b']))
        self.assertTrue(rows[0]['speech'].endswith('伺います。'))

    def test_parse_rejects_foreign_host_and_out_of_period(self):
        with self.assertRaises(ValueError):
            parse(json.dumps({'numberOfRecords': 1, 'speechRecord': [record('a', url='https://evil.example/a')]}))
        with self.assertRaises(ValueError):
            parse(json.dumps({'numberOfRecords': 1, 'speechRecord': [record('a', date='2014-12-31')]}))

    def test_save_is_idempotent_and_policy_is_fixed(self):
        _, _, rows = parse(json.dumps({'numberOfRecords': 1, 'speechRecord': [record('b')]}))
        self.assertEqual(save(self.db, rows, 'h'), 1)
        self.assertEqual(save(self.db, rows, 'h'), 0)
        self.assertEqual(self.db.execute('SELECT content_policy FROM kokkai_speeches_full').fetchone()[0],
                         'restricted_research_full_text')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE kokkai_speeches_full SET content_policy='public'")

    def test_resume_point_follows_checkpoints(self):
        self.assertEqual(resume_point(self.db, 2019), 1)
        self.db.execute("INSERT INTO kokkai_full_pages VALUES('韓国',2019,1,'t',120,50,51,'h')")
        self.assertEqual(resume_point(self.db, 2019), 51)
        self.db.execute("INSERT INTO kokkai_full_pages VALUES('韓国',2019,101,'t',120,20,NULL,'h')")
        self.assertIsNone(resume_point(self.db, 2019))

    def test_request_is_bounded_to_documented_endpoint(self):
        url = page_url(2026, 1)
        self.assertTrue(url.startswith('https://kokkai.ndl.go.jp/api/speech?'))
        self.assertIn('until=2026-10-31', url)


if __name__ == '__main__':
    unittest.main()
