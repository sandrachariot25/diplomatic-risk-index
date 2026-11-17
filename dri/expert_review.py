"""A blind, frozen human review set. Read-only corpus; append-only expert labels."""
import copy
import hashlib
import json
import os
import random
import re
import sqlite3
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from contextlib import contextmanager,nullcontext
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from .analytical_sample import load_sample,digest
from .tokenization import prepare
from .paths import ROOT,inside,write_generated

REGISTRY=ROOT/'data/dri_expert_annotations.json'
WORKBOOK=ROOT/'data/dri_expert_review.xlsx'
CONFIG=ROOT/'config/expert_annotation.json'
HEADERS=['ID','Дата','Говорящий','Государство','Язык','Оригинальный текст','Направленность','Интенсивность 0–3','Адресат','Позиция / цитирование','Уверенность эксперта','Комментарий эксперта','Институт','Исходный URL','Полнота / версия','Релевантность','Отрицание','Исторический контекст']
EXPERT_COLUMNS={6:'direction',7:'intensity',8:'target',9:'ownership',10:'confidence',11:'comment',15:'relevance',16:'negation',17:'history'}

def sha_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def selection(units,seed_ids,config,candidate_ids):
    eligible={u['unit_id']:u for u in units if not u['exclusion_reason']}
    if len(set(seed_ids))!=len(seed_ids) or not set(seed_ids)<=eligible.keys():raise ValueError('Invalid seed IDs')
    rng=random.Random(config['random_seed']);order=sorted(eligible);rng.shuffle(order);rank={n:i for i,n in enumerate(order)}
    selected=set(seed_ids);quotas=config['language_quotas']
    def room(u):return sum(eligible[i]['language']==u['language'] for i in selected)<quotas[u['language']]
    def feature(u,key):
        if key in {'confrontational','neutral','cooperative','undetermined'}:return u['direction']==key
        if key=='no_v01_candidate':return u['unit_id'] not in candidate_ids
        return key in u['context_flags']
    def deficit_score(u):
        score=sum(feature(u,k) and sum(feature(eligible[i],k) for i in selected)<v for k,v in config['minimums'].items())
        score+=sum(eligible[i]['date'][:4]==u['date'][:4] for i in selected)<config['minimum_per_year']
        return score
    def add_where(predicate):
        candidates=[u for i,u in eligible.items() if i not in selected and room(u) and predicate(u)]
        if not candidates:raise ValueError('Cannot satisfy frozen sampling protocol; do not silently relax it')
        u=min(candidates,key=lambda u:(-deficit_score(u),rank[u['unit_id']]))
        selected.add(u['unit_id'])
    # Rare language and interpretable context candidates, not only conflict triggers.
    forced=[u for u in eligible.values() if
        (config['include_all_korean'] and u['language']=='ko') or
        (config['include_all_historical_flags'] and 'historical' in u['context_flags']) or
        (config['include_all_intensity_one_candidates'] and u['intensity']==1)]
    for u in sorted(forced,key=lambda u:rank[u['unit_id']]):
        if u['unit_id'] not in selected:
            if not room(u):raise ValueError('Pinned cases exceed language quota')
            selected.add(u['unit_id'])
    # Constrained random sampling. Rarest requirements first; SHA-free PRNG seed
    # and sorted population make the protocol reproducible independent of row order.
    requirements=[(k,v,lambda u,k=k:feature(u,k)) for k,v in config['minimums'].items()]
    requirements += [(str(y),config['minimum_per_year'],lambda u,y=y:u['date'].startswith(str(y))) for y in range(2015,2027)]
    requirements.sort(key=lambda t:sum(t[2](u) for u in eligible.values()))
    for _,minimum,predicate in requirements:
        while sum(predicate(eligible[i]) for i in selected)<minimum:add_where(predicate)
    for lang,quota in quotas.items():
        while sum(eligible[i]['language']==lang for i in selected)<quota:add_where(lambda u,lang=lang:u['language']==lang)
    if len(selected)!=config['sample_size']:raise ValueError('Wrong total sample size')
    chosen=[eligible[i] for i in selected];chosen.sort(key=lambda u:rank[u['unit_id']])
    return chosen

def source_view(unit,meta,limit=1000):
    parts=[prepare(f['text']) for f in unit['fragments']]
    text='\n\n'.join(parts)
    if not text or len(text)>200000:raise ValueError('Missing/unexpected source text')
    chunks=[text[i:i+limit] for i in range(0,len(text),limit)]
    display=chunks[0] if len(chunks)==1 else chunks[0]+'\n[Продолжение: лист «Тексты», тот же ID. Это весь сохранённый материал, а не восстановленная речь.]'
    forms={'complete_speech':'полное выступление','complete_official_statement':'полный официальный текст',
        'selected_turns_partial_floor':'отдельные реплики, эпизод неполон','sentence_excerpt':'одно предложение из выступления',
        'legacy_excerpt':'старый усечённый отрывок','short_quote_fragment':'короткая цитата'}
    version={'original':'опубликованный оригинал','unofficial_translation':'опубликованный неофициальный перевод',
        'published_original_unknown':'язык оригинала не установлен'}.get(meta['version'],meta['version'])
    row=[unit['unit_id'],unit['date'],unit['speaker_name'] or 'Личное имя не установлено',
        {'ROK':'Республика Корея','JPN':'Япония'}[unit['country']],unit['language'],display,
        None,None,None,None,None,None,unit['institution'],'\n'.join(unit['source_urls']),
        forms.get(unit['text_form'],unit['text_form'])+'; '+version,None,None,None]
    continuations=[[unit['unit_id'],i+1,chunk] for i,chunk in enumerate(chunks) if i>0]
    return row,continuations

def current_data():
    units,snapshot=load_sample(ROOT/'data/dri.sqlite3');byid={u['unit_id']:u for u in units}
    auto=[json.loads(line) for line in (ROOT/'data/dri_v02_units.jsonl').read_text(encoding='utf-8').splitlines()]
    manifest=json.loads((ROOT/'data/dri_v02_manifest.json').read_text(encoding='utf-8'))
    if snapshot['core_input_sha256']!=manifest['summary']['core_input_sha256']:raise ValueError('Corpus differs from the frozen v0.2 snapshot')
    if sha_file(ROOT/'data/dri_v02_units.jsonl')!=manifest['outputs_sha256']['data/dri_v02_units.jsonl']:raise ValueError('Automatic ledger hash mismatch')
    for u in auto:
        if u['input_text_sha256']!=byid[u['unit_id']]['input_text_sha256']:raise ValueError('Text identity mismatch')
    return byid,auto,snapshot

def prepare_review():
    config=json.loads(CONFIG.read_text(encoding='utf-8'));byid,auto,snapshot=current_data()
    baseline=json.loads((ROOT/'data/dri_v02_review.json').read_text(encoding='utf-8'))
    seed_ids=[r['unit_id'] for r in baseline['records']]
    candidates={json.loads(line)['unit_id'] for line in (ROOT/'data/dri_v01_matches.jsonl').read_text(encoding='utf-8').splitlines()}
    chosen=selection(auto,seed_ids,config,candidates)
    records=[];rows=[];continuations=[]
    for m in chosen:
        u=byid[m['unit_id']];row,tail=source_view(u,m,config['main_text_limit'])
        records.append({'unit_id':u['unit_id'],'statement_ids':u['statement_ids'],'input_text_sha256':u['input_text_sha256'],
                        'source_view_sha256':digest([row,tail])})
        rows.append(row);continuations.extend(tail)
    sample_id='DRI-EXPERT-'+digest([config,records])[:16]
    stats={key:dict(sorted(Counter(u[key] for u in chosen).items())) for key in ('language','country','source_id','institution_type','direction','text_form')}
    stats['year']=dict(sorted(Counter(u['date'][:4] for u in chosen).items()))
    stats['context_flags']=dict(sorted(Counter(f for u in chosen for f in u['context_flags']).items()))
    stats['no_v01_candidate']=sum(u['unit_id'] not in candidates for u in chosen)
    stats['intensity_one_candidates']=sum(u['intensity']==1 for u in chosen)
    frozen={'sample_id':sample_id,'instruction_version':config['guideline']['version'],'instruction_sha256':digest(config['guideline']),
        'protocol_sha256':digest(config),'random_seed':config['random_seed'],'baseline_32_ids':sorted(seed_ids),
        'core_input_sha256':snapshot['core_input_sha256'],'automatic_ledger_sha256':sha_file(ROOT/'data/dri_v02_units.jsonl'),
        'publication_policy':'internal_research_only','records':records,'composition':stats}
    registry={**frozen,'annotations':[]}
    if REGISTRY.exists():
        old=json.loads(REGISTRY.read_text(encoding='utf-8'))
        if {k:v for k,v in old.items() if k!='annotations'}!=frozen:raise ValueError('Frozen sample changed; existing annotations must not be overwritten')
        registry=old
    else:write_generated(REGISTRY,json.dumps(registry,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    payload={'sample_id':sample_id,'guideline':config['guideline'],'headers':HEADERS,'rows':rows,'continuations':continuations}
    write_generated(ROOT/'.venv/dri_expert_workbook_payload.json',json.dumps(payload,ensure_ascii=False,sort_keys=True)+'\n')
    return registry,payload

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def read_xlsx(path):
    """Read cell values without evaluating formulas or loading macros/external links."""
    path=inside(path)
    if path.suffix.lower()!='.xlsx':raise ValueError('Expected XLSX')
    sheets={}
    with ZipFile(path) as z:
        if len(z.infolist())>1000 or sum(i.file_size for i in z.infolist())>30000000:raise ValueError('Unexpected workbook size')
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(si.itertext()) if not list(si) else ''.join(t.text or '' for t in si.iter('{'+NS['s']+'}t')) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        book=ET.fromstring(z.read('xl/workbook.xml'))
        props=book.find('s:workbookPr',NS)
        if props is not None and props.get('date1904') in {'1','true'}:raise ValueError('1904 date system unsupported; preserve original workbook')
        for s in book.find('s:sheets',NS):
            target=rels[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            name=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            if '..' in name:raise ValueError('Invalid worksheet path')
            values={}
            for cell in ET.fromstring(z.read(name)).findall('.//s:sheetData/s:row/s:c',NS):
                ref=cell.attrib['r']
                if ref in values:raise ValueError('Duplicate cell reference')
                if cell.find('s:f',NS) is not None:raise ValueError('Formulas are not accepted in the annotation workbook')
                kind=cell.get('t');v=cell.find('s:v',NS)
                if kind=='inlineStr':value=''.join(t.text or '' for t in cell.findall('.//s:t',NS))
                elif v is None or v.text is None:value=None
                elif kind=='s':value=strings[int(v.text)]
                elif kind=='b':value=v.text=='1'
                elif kind in {'str','d','e'}:value=v.text
                else:
                    number=float(v.text);value=int(number) if number.is_integer() else number
                values[ref]=value
            sheets[s.attrib['name']]=values
    return sheets

def col_name(n):
    out=''
    while n:n,r=divmod(n-1,26);out=chr(65+r)+out
    return out

def normalize_date(value):
    if isinstance(value,(float,int)) and not isinstance(value,bool):
        if not float(value).is_integer():raise ValueError('Date contains a non-midnight time')
        return (datetime(1899,12,30)+timedelta(days=value)).date().isoformat()
    if isinstance(value,str) and 'T' in value:
        date=datetime.fromisoformat(value.replace('Z','+00:00'))
        if any((date.hour,date.minute,date.second,date.microsecond)):raise ValueError('Date contains a non-midnight time')
        return date.date().isoformat()
    return value

def rows_from_cells(cells,width):
    indexes=sorted({int(re.search(r'\d+$',ref)[0]) for ref,v in cells.items() if v is not None})
    return [(n,[cells.get(col_name(i)+str(n)) for i in range(1,width+1)]) for n in indexes]

def validate_answers(values,guideline):
    answer={field:values[col] for col,field in EXPERT_COLUMNS.items()}
    for field,value in answer.items():
        if isinstance(value,str):answer[field]=value.strip() or None
    if all(v is None for v in answer.values()):return None
    for field in ('direction','target','ownership','confidence','relevance'):
        if answer[field] not in guideline[field]:raise ValueError('Missing/invalid expert field: '+field)
    for field in ('negation','history'):
        if answer[field] is not None and answer[field] not in guideline['optional_flags']:raise ValueError('Invalid '+field)
    intensity=answer['intensity']
    if isinstance(intensity,str) and intensity in {'0','1','2','3'}:intensity=int(intensity)
    if isinstance(intensity,bool) or intensity is not None and (not isinstance(intensity,(int,float)) or intensity not in range(4)):raise ValueError('Intensity must be an integer 0..3 or blank')
    if intensity is not None:intensity=int(intensity)
    answer['intensity']=intensity
    if answer['direction']=='неопределённая':
        if intensity is not None:raise ValueError('Undetermined is not zero; leave intensity blank')
    elif answer['direction']=='конфронтационная':
        if intensity not in (1,2,3):raise ValueError('Confrontation requires intensity 1..3')
    elif intensity!=0:raise ValueError('Neutral/cooperative requires explicit 0')
    opposite={'Республика Корея':'Япония','Япония':'Республика Корея'}.get(values[3])
    if answer['direction']!='неопределённая' and answer['target']!=opposite:raise ValueError('A definite dyadic rating requires the other state as target')
    if answer['relevance']!='относится к паре РК–Япония' or answer['ownership']!='собственная позиция':
        if answer['direction']!='неопределённая':raise ValueError('Non-dyadic or non-owned position requires undetermined direction')
    if answer['direction']=='неопределённая' or answer['confidence']=='низкая' or answer['target']=='несколько адресатов':
        if not isinstance(answer['comment'],str) or not answer['comment']:raise ValueError('A comment is required for uncertainty/low confidence/multiple targets')
    if answer['comment'] is not None and (not isinstance(answer['comment'],str) or len(answer['comment'])>10000):raise ValueError('Invalid comment')
    return answer

def validated_workbook(path,registry,source_rows,continuations,guideline):
    sheets=read_xlsx(path)
    if set(sheets)!={'Разметка','Инструкция','Тексты'}:raise ValueError('Unexpected/missing sheets')
    if sheets['Инструкция'].get('B3')!=registry['instruction_version'] or sheets['Инструкция'].get('B4')!=registry['sample_id']:raise ValueError('Instruction version/sample mismatch')
    for n,(label,body) in enumerate(guideline['instructions'],7):
        if sheets['Инструкция'].get('A'+str(n))!=label or sheets['Инструкция'].get('B'+str(n))!=body:raise ValueError('Instruction text changed')
    main=sheets['Разметка']
    if [main.get(col_name(i)+'1') for i in range(1,len(HEADERS)+1)]!=HEADERS:raise ValueError('Column headers changed')
    expected={r[0]:r for r in source_rows};seen=set();answers=[]
    for number,row in rows_from_cells(main,len(HEADERS)):
        if number==1:continue
        sid=row[0]
        if isinstance(sid,bool) or sid not in expected:raise ValueError('Unknown/missing ID at row '+str(number))
        if sid in seen:raise ValueError('Duplicate ID '+str(sid))
        seen.add(sid)
        for i,value in enumerate(row):
            if i in EXPERT_COLUMNS:continue
            actual=normalize_date(value) if i==1 else value
            if actual!=expected[sid][i]:raise ValueError(f'Source field changed for ID {sid}, column {HEADERS[i]}')
        try:answer=validate_answers(row,guideline)
        except ValueError as e:raise ValueError(f'ID {sid}: {e}') from e
        if answer is not None:answers.append((sid,answer))
    if seen!=set(expected):raise ValueError('Missing IDs; keep unfilled rows in the workbook')
    tails=[row for n,row in rows_from_cells(sheets['Тексты'],3) if n>1]
    if sorted(tails,key=lambda r:(r[0],r[1]))!=sorted(continuations,key=lambda r:(r[0],r[1])):raise ValueError('Original context continuations changed')
    return answers

def update_documentation(registry):
    start='<!-- EXPERT_REFERENCE_START -->';end='<!-- EXPERT_REFERENCE_END -->'
    def section(path,text):
        old=(ROOT/path).read_text(encoding='utf-8');old=re.sub(re.escape(start)+'.*?'+re.escape(end),'',old,flags=re.S).rstrip()
        write_generated(ROOT/path,old+'\n\n'+start+'\n'+text+'\n'+end+'\n')
    stats=registry['composition']
    lines=['## Набор независимой экспертной разметки', '',
        f'Подготовлены {len(registry["records"])} уникальных единицы: исходные 32 сохранены по ID и дополнены 112 без повторов. Набор {registry["sample_id"]}; фиксированное зерно {registry["random_seed"]}; инструкция {registry["instruction_version"]}, SHA-256 {registry["instruction_sha256"]}.', '',
        'Единственная таблица для заполнения — data/dri_expert_review.xlsx. Три листа: Разметка (одна строка на высказывание), Инструкция и Тексты (только продолжения длинных исходников по тому же ID). Все экспертные поля пусты. В книгу не включены предложения модели, причины правил, страты отбора или скрытые прогнозы. Автоматические оценки отдельно в прежнем data/dri_v02_units.jsonl, неизменённом на этом этапе.', '',
        'Сохранён весь доступный оригинальный языковой материал выбранных единиц; длинный текст разбит на последовательные части без смыслового отбора и подсветки. Усечённые цитаты не достраиваются до полных речей. Язык en — опубликованная английская версия, а не доказательство языка исходного выступления; тип перевода сохранён. Машинный перевод не применён. Все тексты в XLSX предназначены для внутреннего исследования.', '',
        'Отбор: закреплены исходные 32 ID, все 21 корейская единица, все сохранённые исторические флаги и кандидаты интенсивности 1. Затем ограничения по редким категориям/контекстам/годам и квоты EN=40, JA=83, KO=21; недостающие места заполнены случайным порядком с фиксированным зерном. Порядок исходной базы не влияет на результат. Это обогащённая диагностическая выборка, не случайная репрезентативная оценка распространённости риторики. Названия автоматических категорий ниже описывают прежние прогнозы, не эталонные экспертные ответы.', '']
    for key,title in [('language','Язык'),('year','Год'),('source_id','Источник'),('institution_type','Тип института'),('direction','Прежняя автоматическая категория'),('text_form','Полнота')]:
        lines += [f'| {title} | Единицы |','|---|---:|']
        lines += [f'| {k} | {v} |' for k,v in stats[key].items()];lines.append('')
    lines += [f'Контекстные флаги старого классификатора (пересекаются): `{stats["context_flags"]}`. Кандидаты косвенной критики/умеренной оценки (прежняя интенсивность 1): {stats["intensity_one_candidates"]}. Без какого-либо кандидата словаря v0.1, включая подавленные совпадения: {stats["no_v01_candidate"]}. Флаги — средства отбора, а не подтверждённые экспертные свойства.', '',
        '### Воспроизведение и импорт', '',
        'Подготовка/проверка: `.venv\\Scripts\\python.exe scripts/prepare_expert_review.py --data-only`. Создание XLSX (если ещё не существует): `.venv\\Scripts\\python.exe scripts/prepare_expert_review.py`. Повтор не перезаписывает существующую книгу. Для явного пересоздания незаполненной книги есть --rebuild-blank; при любых заполненных экспертных ячейках перезапись запрещена.', '',
        'Проверка заполненного файла без записи: `.venv\\Scripts\\python.exe scripts/import_expert_review.py --file data/dri_expert_review.xlsx --reviewer expert_01`. Сохранение: та же команда с `--execute`. Эксперт работает только с XLSX; команду выполняет исследователь. Разрешён частичный прогресс при сохранении всех строк и неизменных исходников. Полностью пустые строки оценки пропускаются; частично заполненные строки или недопустимые сочетания отклоняют весь импорт.', '',
        'data/dri_expert_annotations.json — единственный внутренний машинный реестр выборки и будущих экспертных аннотаций, не вторая SQLite-база и не дополнительная таблица для заполнения. Он хранит ID, хэши, протокол и пока пустой annotations; исходных текстов в нём нет. Импорт читает единую основную SQLite в режиме read-only, связывает метки с unit_id и statement_ids, проверяет источник и полный показанный контекст. Правила/версия инструкции, типы значений, соответствие направленности и интенсивности, дубли и все исходные поля проверяются до атомарной записи.', '',
        'Идентичный повтор пропускается без изменения времени и числа аннотаций. Другой эксперт имеет независимую запись. Противоречащий ответ того же эксперта для той же версии инструкции отклоняется, а не молча перезаписывается. Версия и SHA инструкции, хэш текста и ID аннотации сохраняются. Изменение авто-прогноза не перезаписывает экспертный ответ; механизм не запускает обучение, оценку качества или индекс. Для последующего присоединения меток к корпусу предусмотрена dri.expert_review.expert_labels().', '',
        'Схема и содержимое основной базы, исходные тексты, результаты v0.1/v0.2 и прежние 32 записи не изменены. Текущий этап не создаёт экспертных ответов. Не рассчитываются accuracy, precision, recall или согласие экспертов. Тесты — docs/TEST_RESULTS.txt.']
    section('docs/QUALITY_REPORT.md','\n'.join(lines))
    section('README.md','## Независимая экспертная разметка\n\n'
        'Рабочая книга: data/dri_expert_review.xlsx (144 высказывания, исходные 32 включены). '
        'Инструкция находится внутри книги; заполняются только жёлтые поля, прогнозов модели в книге нет. '
        'Внутренний материал: книгу и data/dri_expert_annotations.json не публиковать. '
        'Импорт с проверкой: `.venv\\Scripts\\python.exe scripts/import_expert_review.py --file data/dri_expert_review.xlsx --reviewer expert_01`; '
        'добавьте --execute для сохранения. Метод отбора, ограничения и состав — в существующем docs/QUALITY_REPORT.md.')
    section('docs/CHANGES.md','## Подготовка независимой экспертной разметки\n\n'
        'Созданы config/expert_annotation.json, dri/expert_review.py, scripts/prepare_expert_review.py, scripts/import_expert_review.py, scripts/build_expert_review.mjs, tests/test_expert_review.py. '
        'Единственная новая таблица: data/dri_expert_review.xlsx; единственный машинный реестр: data/dri_expert_annotations.json. '
        'Обновлены .gitignore, README.md, docs/QUALITY_REPORT.md, docs/CHANGES.md, docs/TEST_RESULTS.txt. '
        'Технический JSON и превью находятся в уже существующей .venv; зависимости используются из встроенного окружения, установка и сеть не нужны. '
        'Основная SQLite и схема 4, тексты, исходный review из 32 записей и все расчётные артефакты DRI сохранены. '
        'Новая модель, ответы экспертов, обучение и оценка точности не создавались.')

def merge_annotations(registry,answers,reviewer,stamp):
    if not re.fullmatch(r'[\w.@-]{2,100}',reviewer):raise ValueError('Use a stable reviewer ID, 2..100 letters/digits/._@-')
    out=copy.deepcopy(registry);records={r['unit_id']:r for r in registry['records']}
    existing={(a['unit_id'],a['reviewer'],a['instruction_version']):a for a in out['annotations']};added=repeat=0
    if len(existing)!=len(out['annotations']):raise ValueError('Existing annotation identities are duplicated')
    for a in out['annotations']:
        if (a['unit_id'] not in records or a['sample_id']!=registry['sample_id']
            or a['instruction_version']!=registry['instruction_version'] or a['instruction_sha256']!=registry['instruction_sha256']
            or a['input_text_sha256']!=records[a['unit_id']]['input_text_sha256']
            or digest(a['answer'])!=a['answer_sha256']):raise ValueError('Existing expert annotation integrity mismatch')
    for sid,answer in answers:
        if sid not in records:raise ValueError('ID outside frozen sample')
        key=(sid,reviewer,registry['instruction_version']);fingerprint=digest(answer)
        if key in existing:
            if existing[key]['answer_sha256']!=fingerprint:raise ValueError('Conflicting existing annotation; explicit adjudication required, no overwrite')
            repeat+=1;continue
        record={'annotation_id':digest([registry['sample_id'],key,records[sid]['input_text_sha256']]),
            'unit_id':sid,'statement_ids':records[sid]['statement_ids'],'sample_id':registry['sample_id'],'reviewer':reviewer,
            'instruction_version':registry['instruction_version'],'instruction_sha256':registry['instruction_sha256'],
            'input_text_sha256':records[sid]['input_text_sha256'],'answer':answer,'answer_sha256':fingerprint,'imported_at':stamp}
        out['annotations'].append(record);existing[key]=record;added+=1
    return out,{'added':added,'already_present':repeat,'filled_rows':len(answers),'total_annotations':len(out['annotations'])}

@contextmanager
def annotation_lock():
    path=REGISTRY.with_suffix('.json.lock')
    try:descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as e:raise RuntimeError('Another annotation import is running; no changes made') from e
    try:
        os.write(descriptor,str(os.getpid()).encode());yield
    finally:
        os.close(descriptor);path.unlink()

def import_review(path,reviewer,execute=False):
    with annotation_lock() if execute else nullcontext():return _import_review(path,reviewer,execute)

def _import_review(path,reviewer,execute=False):
    registry=json.loads(REGISTRY.read_text(encoding='utf-8'));config=json.loads(CONFIG.read_text(encoding='utf-8'))
    if digest(config['guideline'])!=registry['instruction_sha256'] or digest(config)!=registry['protocol_sha256']:raise ValueError('Instruction/protocol changed')
    byid,auto,_=current_data();metadata={u['unit_id']:u for u in auto};source_rows=[];continuations=[]
    for record in registry['records']:
        u=byid[record['unit_id']]
        if u['input_text_sha256']!=record['input_text_sha256'] or u['statement_ids']!=record['statement_ids']:raise ValueError('Source identity changed')
        row,tail=source_view(u,metadata[u['unit_id']],config['main_text_limit'])
        if digest([row,tail])!=record['source_view_sha256']:raise ValueError('Source display metadata changed')
        source_rows.append(row);continuations.extend(tail)
    answers=validated_workbook(path,registry,source_rows,continuations,config['guideline'])
    out,stats=merge_annotations(registry,answers,reviewer,datetime.now(timezone.utc).isoformat())
    if execute and stats['added']:write_generated(REGISTRY,json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    return {'execute':execute,**stats,'database_mode':'read_only','automatic_results_changed':False}

def expert_labels(registry_path=REGISTRY):
    """Future evaluation joins by unit_id/statement_ids; no training or scoring here."""
    registry=json.loads(Path(registry_path).read_text(encoding='utf-8'))
    return copy.deepcopy(registry['annotations'])
