import io,zipfile,tempfile,unittest
from dri.paths import ROOT
from dri.storage import Store
from dri.connectors.gdelt_archive import events,mentions,save_records,gkg

def zipped(rows):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:z.writestr('fixture.CSV','\n'.join('\t'.join(r) for r in rows))
    return b.getvalue()

class ArchiveTests(unittest.TestCase):
    def row(self,a='KOR',b='JPN'):
        r=['']*61
        for i,v in {0:'123',1:'20250823',7:a,17:b,26:'043',59:'20250823120000',60:'https://example.test/article'}.items():r[i]=v
        return r
    def test_dprk_is_not_rok_and_direction_preserved(self):
        self.assertEqual(events(zipped([self.row('PRK','JPN')])),[])
        row=events(zipped([self.row('JPN','KOR')]))[0]
        self.assertEqual((row['actor1_country'],row['actor2_country']),('JPN','ROK'))
        self.assertEqual(row['event_code'],'043')
    def test_width_changes_rejected(self):
        with self.assertRaises(ValueError):events(zipped([['x']*60]))
    def test_typed_import_repeat_does_not_create_speeches(self):
        folder=ROOT/'data/test-tmp';folder.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as t:
            s=Store(t,memory=True)
            try:
                records=events(zipped([self.row()]))
                self.assertEqual(save_records(s,'gdelt_events',records,'https://data.gdeltproject.org/file','sha'),1)
                self.assertEqual(save_records(s,'gdelt_events',records,'https://data.gdeltproject.org/file','sha'),0)
                self.assertEqual(s.db.execute('SELECT count(*) FROM statements').fetchone()[0],0)
                self.assertEqual(s.db.execute('SELECT count(*) FROM documents').fetchone()[0],0)
            finally:s.db.close()
    def test_mentions_only_link_known_events_and_language_is_not_imputed(self):
        r=['']*16;r[0]='123';r[1]='20250823120000';r[2]='20250823121500';r[5]='https://example.test/article'
        self.assertEqual(mentions(zipped([r]),set()),[])
        self.assertIsNone(mentions(zipped([r]),{'123'})[0]['source_language'])
        r[14]='srclc:kor;eng:documented engine'
        self.assertEqual(mentions(zipped([r]),{'123'})[0]['source_language'],'kor')
    def test_gkg_cooccurrence_not_actor_event(self):
        r=['']*27;r[0]='20250823120000-1';r[1]='20250823120000';r[4]='https://example.test/article'
        r[9]='1#South Korea#KS#x;1#Japan#JA#x'
        self.assertEqual(len(gkg(zipped([r]))),1)
        r[9]='1#North Korea#KN#x;1#Japan#JA#x'
        self.assertEqual(gkg(zipped([r])),[])
