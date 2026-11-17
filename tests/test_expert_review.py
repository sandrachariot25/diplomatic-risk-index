"""Synthetic annotation tests never create human answers in the real registry."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from dri.paths import ROOT
from dri.analytical_sample import digest
from dri.expert_review import (CONFIG,HEADERS,EXPERT_COLUMNS,WORKBOOK,selection,validate_answers,
    merge_annotations,normalize_date,col_name,validated_workbook,read_xlsx,annotation_lock)

CFG=json.loads(CONFIG.read_text(encoding='utf-8'));GUIDE=CFG['guideline']

class ExpertReviewTests(unittest.TestCase):
    def row(self):
        return [1,'2020-01-02','Synthetic speaker','Республика Корея','en','Synthetic source text',
            None,None,None,None,None,None,'Synthetic institute','https://example.test/1','fragment',None,None,None]

    def filled(self):
        row=self.row();row[6]='нейтральная';row[7]=0;row[8]='Япония';row[9]='собственная позиция';row[10]='высокая';row[15]='относится к паре РК–Япония'
        return row

    def registry(self):
        return {'sample_id':'SYNTHETIC_TEST','instruction_version':GUIDE['version'],'instruction_sha256':digest(GUIDE),
            'records':[{'unit_id':1,'statement_ids':[10],'input_text_sha256':'synthetic-only'}],'annotations':[]}

    def sheets(self,rows=None):
        main={col_name(i+1)+'1':value for i,value in enumerate(HEADERS)}
        for n,row in enumerate(rows or [self.row()],2):main.update({col_name(i+1)+str(n):value for i,value in enumerate(row)})
        guide={'B3':GUIDE['version'],'B4':'SYNTHETIC_TEST'}
        for n,(label,body) in enumerate(GUIDE['instructions'],7):guide['A'+str(n)]=label;guide['B'+str(n)]=body
        return {'Разметка':main,'Инструкция':guide,'Тексты':{'A1':'ID','B1':'Часть','C1':'Оригинальный текст: продолжение'}}

    def validate_book(self,sheets,rows=None,tails=None):
        with patch('dri.expert_review.read_xlsx',return_value=sheets):
            return validated_workbook(Path('synthetic.xlsx'),self.registry(),rows or [self.row()],tails or [],GUIDE)

    def test_sampling_seed_includes_32_and_ignores_population_order(self):
        units=[json.loads(l) for l in (ROOT/'data/dri_v02_units.jsonl').read_text(encoding='utf-8').splitlines()]
        seeds=[r['unit_id'] for r in json.loads((ROOT/'data/dri_v02_review.json').read_text(encoding='utf-8'))['records']]
        candidates={json.loads(l)['unit_id'] for l in (ROOT/'data/dri_v01_matches.jsonl').read_text(encoding='utf-8').splitlines()}
        a=selection(units,seeds,CFG,candidates);b=selection(list(reversed(units)),seeds,CFG,candidates)
        ids=[u['unit_id'] for u in a]
        self.assertEqual(ids,[u['unit_id'] for u in b]);self.assertEqual(len(set(ids)),144);self.assertTrue(set(seeds)<=set(ids))
        for lang,n in CFG['language_quotas'].items():self.assertEqual(sum(u['language']==lang for u in a),n)
        self.assertEqual({u['date'][:4] for u in a},{str(y) for y in range(2015,2027)})

    def test_blank_answers_are_not_neutral(self):self.assertIsNone(validate_answers(self.row(),GUIDE))

    def test_explicit_zero_is_retained(self):self.assertEqual(validate_answers(self.filled(),GUIDE)['intensity'],0)

    def test_undetermined_requires_blank_intensity_and_comment(self):
        row=self.filled();row[6]='неопределённая';row[7]=None;row[11]='Контекста недостаточно'
        self.assertIsNone(validate_answers(row,GUIDE)['intensity'])
        row[7]=0
        with self.assertRaises(ValueError):validate_answers(row,GUIDE)

    def test_partial_rows_rejected(self):
        row=self.row();row[11]='Only a note'
        with self.assertRaises(ValueError):validate_answers(row,GUIDE)

    def test_direction_intensity_consistency(self):
        for direction,intensity in [('нейтральная',1),('кооперативная',None),('конфронтационная',0),('конфронтационная',4),('конфронтационная',True),('конфронтационная',1.5)]:
            row=self.filled();row[6]=direction;row[7]=intensity
            with self.assertRaises(ValueError):validate_answers(row,GUIDE)

    def test_enum_values_and_low_confidence_comment(self):
        row=self.filled();row[10]='certain'
        with self.assertRaises(ValueError):validate_answers(row,GUIDE)
        row[10]='низкая'
        with self.assertRaises(ValueError):validate_answers(row,GUIDE)

    def test_dprk_and_domestic_target_not_dyadic_confrontation(self):
        for target in ['КНДР','Республика Корея','внутренний адресат']:
            row=self.filled();row[6]='конфронтационная';row[7]=2;row[8]=target
            with self.assertRaises(ValueError):validate_answers(row,GUIDE)

    def test_quote_and_third_country_relevance_cannot_be_owned_neutral(self):
        row=self.filled();row[9]='цитирование чужой позиции'
        with self.assertRaises(ValueError):validate_answers(row,GUIDE)
        row=self.filled();row[15]='только третьи государства'
        with self.assertRaises(ValueError):validate_answers(row,GUIDE)

    def test_blank_workbook_produces_no_answers(self):self.assertEqual(self.validate_book(self.sheets()),[])

    def test_immutable_text_date_and_id_validated(self):
        for cell,value in [('F2','Altered original'),('B2','2020-01-03'),('A2',999)]:
            sheets=self.sheets();sheets['Разметка'][cell]=value
            with self.assertRaises(ValueError):self.validate_book(sheets)

    def test_duplicates_and_missing_rows_rejected(self):
        with self.assertRaises(ValueError):self.validate_book(self.sheets([self.row(),self.row()]))
        sheets=self.sheets();sheets['Разметка']={k:v for k,v in sheets['Разметка'].items() if k.endswith('1')}
        with self.assertRaises(ValueError):self.validate_book(sheets)

    def test_instruction_version_and_actual_text_must_match(self):
        for cell in ['B3','B4','B7']:
            sheets=self.sheets();sheets['Инструкция'][cell]='changed'
            with self.assertRaises(ValueError):self.validate_book(sheets)

    def test_context_continuation_must_match(self):
        sheets=self.sheets();sheets['Тексты'].update({'A2':1,'B2':2,'C2':'altered'})
        with self.assertRaises(ValueError):self.validate_book(sheets,tails=[[1,2,'original']])

    def test_sorting_rows_does_not_change_identity(self):
        second=self.row();second[0]=2
        sheets=self.sheets([second,self.filled()])
        answers=self.validate_book(sheets,rows=[self.row(),second]);self.assertEqual(answers[0][0],1)

    def test_filled_answer_preserves_source_row(self):
        row=self.filled();before=copy.deepcopy(row);answers=self.validate_book(self.sheets([row]))
        self.assertEqual(row,before);self.assertEqual(answers[0][1]['intensity'],0)

    def test_repeat_import_is_idempotent_and_keeps_initial_time(self):
        registry=self.registry();answers=[(1,validate_answers(self.filled(),GUIDE))]
        first,stats=merge_annotations(registry,answers,'synthetic_expert','t1')
        second,repeat=merge_annotations(first,answers,'synthetic_expert','t2')
        self.assertEqual(stats['added'],1);self.assertEqual(repeat['already_present'],1);self.assertEqual(first,second)
        self.assertEqual(registry['annotations'],[])

    def test_conflict_does_not_overwrite_previous_expert(self):
        registry,_=merge_annotations(self.registry(),[(1,validate_answers(self.filled(),GUIDE))],'synthetic_expert','t1')
        original=copy.deepcopy(registry);changed=self.filled();changed[6]='кооперативная'
        with self.assertRaises(ValueError):merge_annotations(registry,[(1,validate_answers(changed,GUIDE))],'synthetic_expert','t2')
        self.assertEqual(registry,original)

    def test_second_expert_has_independent_label(self):
        registry,_=merge_annotations(self.registry(),[(1,validate_answers(self.filled(),GUIDE))],'synthetic_one','t1')
        registry,stats=merge_annotations(registry,[(1,validate_answers(self.filled(),GUIDE))],'synthetic_two','t2')
        self.assertEqual(stats['total_annotations'],2)

    def test_existing_annotation_tampering_rejected(self):
        registry,_=merge_annotations(self.registry(),[(1,validate_answers(self.filled(),GUIDE))],'synthetic_one','t1')
        registry['annotations'][0]['answer']['intensity']=3
        with self.assertRaises(ValueError):merge_annotations(registry,[],'synthetic_one','t2')

    def test_real_dates_accept_iso_and_excel_serial(self):
        self.assertEqual(normalize_date('2024-06-13T00:00:00.000Z'),'2024-06-13')
        self.assertEqual(normalize_date(45292),'2024-01-01')
        with self.assertRaises(ValueError):normalize_date(45292.5)

    def test_import_lock_prevents_lost_concurrent_updates(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.venv') as folder:
            with patch('dri.expert_review.REGISTRY',Path(folder)/'synthetic.json'):
                with annotation_lock():
                    with self.assertRaises(RuntimeError):
                        with annotation_lock():pass
                self.assertFalse((Path(folder)/'synthetic.json.lock').exists())

    def test_formulas_are_never_evaluated_or_imported(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.venv') as folder:
            file=Path(folder)/'synthetic.xlsx'
            with ZipFile(file,'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns="'+ 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Test" r:id="r1"/></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
            with self.assertRaises(ValueError):read_xlsx(file)

    @unittest.skipUnless(WORKBOOK.exists(),'Workbook not yet authored')
    def test_real_workbook_has_only_blind_fields(self):
        sheets=read_xlsx(WORKBOOK);header=[sheets['Разметка'].get(col_name(i)+'1') for i in range(1,19)]
        self.assertEqual(header,HEADERS);self.assertEqual(set(sheets),{'Разметка','Инструкция','Тексты'})
        self.assertFalse(any('авто' in str(v).lower() or 'прогноз' in str(v).lower() for v in header))

if __name__=='__main__':unittest.main()
