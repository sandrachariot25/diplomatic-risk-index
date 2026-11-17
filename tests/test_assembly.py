"""Synthetic API-shape fixtures; no network and no speech-corpus insertion."""
import json
import unittest
from dataclasses import asdict
from urllib.parse import parse_qs,urlsplit
from dri.connectors.assembly import (
    DATASETS, sample_url, parse_response, meeting_references, AssemblyResponseError)
from dri.storage import Store,now
from dri.repository import register_sources
from scripts.check_assembly import audit,corpus_counts

def row(agenda='1. Cooperation'):
    return dict(CONF_ID='004591',CONFER_NUM=40229,CONF_DATE='2015-12-31',
        DAE_NUM=19,TITLE='Synthetic meeting',CLASS_NAME='국회본회의',SUB_NAME=agenda,
        PDF_LINK_URL='https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=40229')

def payload(rows=None,kind='plenary'):
    return {DATASETS[kind]['method']:[{'head':[{'list_total_count':20},
            {'RESULT':{'CODE':'INFO-000','MESSAGE':'OK'}}]},{'row':rows if rows is not None else [row()]}]}

class AssemblyTests(unittest.TestCase):
    def test_sample_cannot_include_credentials_or_paginate(self):
        u=sample_url('committee',term=20,period='2019-07',committee='외교통일위원회')
        q=parse_qs(urlsplit(u).query)
        self.assertEqual(q['pIndex'],['1']);self.assertEqual(q['pSize'],['5'])
        self.assertNotIn('KEY',q);self.assertEqual(q['COMM_NAME'],['외교통일위원회'])

    def test_required_parameters_and_scope(self):
        for kwargs in [dict(term=20),dict(term=20,period='2027'),dict(term=20,period='2026-11'),dict(term=20,period='2019-13')]:
            with self.assertRaises((ValueError,TypeError)):sample_url('plenary',**kwargs)
        with self.assertRaises(ValueError):sample_url('plenary',term=20,period='2019',committee='X')

    def test_detail_opaque_id(self):
        self.assertIn('CONF_ID=N054721',sample_url('detail',conf_id='N054721'))
        self.assertIn('CONF_ID=004591',sample_url('detail',conf_id='004591'))
        with self.assertRaises(ValueError):sample_url('detail',conf_id='abc&KEY=secret')

    def test_repeated_agenda_is_one_meeting_never_speech(self):
        rows,total=parse_response(payload([row('1. Economy'),row('2. Diplomacy')]),'plenary')
        refs=meeting_references(rows)
        self.assertEqual(total,20);self.assertEqual(len(refs),1)
        self.assertEqual(refs[0].conf_id,'004591')
        self.assertEqual(len(refs[0].agenda_titles),2)
        self.assertNotIn('text',asdict(refs[0]));self.assertNotIn('speaker_name',asdict(refs[0]))

    def test_errors_are_not_empty_success(self):
        for code in ['ERROR-290','ERROR-300','ERROR-337','INFO-300']:
            with self.assertRaises(AssemblyResponseError):parse_response({'RESULT':{'CODE':code}},'plenary')
        self.assertEqual(parse_response({'RESULT':{'CODE':'INFO-200'}},'plenary'),([],0))

    def test_schema_drift_and_sample_limit(self):
        with self.assertRaises(AssemblyResponseError):parse_response({'some_speech_api':[]},'plenary')
        with self.assertRaises(AssemblyResponseError):parse_response(payload([row()]*6),'plenary')

    def test_conflicting_meeting_metadata_and_arbitrary_pdf_rejected(self):
        for other in [{**row(),'CONF_DATE':'2015-12-30'},
                      {**row(),'PDF_LINK_URL':'https://example.com/file.pdf'}]:
            with self.assertRaises(ValueError):meeting_references([row(),other])

    def test_undated_metadata_not_a_speech_and_future_excluded(self):
        with self.assertRaises(ValueError):meeting_references([{**row(),'CONF_DATE':None}])
        self.assertEqual(meeting_references([{**row(),'CONF_DATE':'2026-11-01'}]),[])

    def test_cached_repeat_never_fetches_or_changes_corpus(self):
        s=Store(memory=True);register_sources(s)
        class NoNetwork:
            def get(self,*a,**k):raise AssertionError('Cached query must not fetch')
        url=sample_url('plenary',term=19,period='2015')
        with s.db:
            s.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result) VALUES(?,?,?,?,?)',
                ('assembly_kr',url,now(),200,json.dumps({'sample_response':payload()})))
        before=corpus_counts(s)
        try:
            for _ in range(2):
                result=audit(s,NoNetwork(),[('plenary',dict(term=19,period='2015'))])
                self.assertEqual(result['network_requests_for_queries'],0)
                self.assertEqual(result['repeat_import_growth'],dict(documents=0,statements=0,quotes=0))
            self.assertEqual(corpus_counts(s),before)
            self.assertEqual(s.db.execute('SELECT count(*) FROM collection_items').fetchone()[0],1)
        finally:s.db.close()

    def test_fresh_query_is_cached_and_never_imported_as_statement(self):
        s=Store(memory=True);register_sources(s)
        url=sample_url('plenary',term=19,period='2015')
        class FakeClient:
            calls=0
            def get(self,*args,**kwargs):
                self.calls+=1
                return json.dumps(payload()),('', 'fixture', 'test'),url
        client=FakeClient()
        try:
            for _ in range(2):audit(s,client,[('plenary',dict(term=19,period='2015'))])
            self.assertEqual(client.calls,1)
            self.assertEqual(corpus_counts(s),dict(documents=0,statements=0,quotes=0))
        finally:s.db.close()

if __name__=='__main__':unittest.main()
