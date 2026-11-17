import hashlib
import json
import sqlite3
import unittest
from dri.paths import DATA
from scripts.annotate_llm_pilot import data

class HearingsImportTests(unittest.TestCase):
    def test_frozen_units_survive_expansion(self):
        units,annotations=data()
        self.assertEqual(len(units),1017)
        self.assertEqual(len(annotations),1017)

    def test_reviewed_turns_have_exact_text_and_unknown_publication(self):
        rows=[json.loads(l) for l in (DATA/'kr_hearings_annotations.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len({r['unit_id'] for r in rows}),len(rows))
        self.assertEqual(len({(r['meeting_id'],r['speaker']) for r in rows}),len(rows))
        self.assertEqual({r['date'][:4] for r in rows},{str(y) for y in range(2015,2027)})
        with sqlite3.connect((DATA/'dri.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
            for r in rows:
                text,pub=db.execute('SELECT text,published_date FROM documents WHERE id=?',r['document_ids']).fetchone()
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),r['input_text_sha256'])
                self.assertIsNone(pub)
                quote=db.execute('SELECT text FROM quotes WHERE statement_id=?',r['statement_ids']).fetchone()[0]
                self.assertEqual(quote,text)
                self.assertTrue(r['summary_ru'])
