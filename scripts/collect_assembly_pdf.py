"""Internal-only, finite public-PDF pilot with sealed agent source-review evidence."""
import argparse
import hashlib
import json
import sys
from collections import Counter,defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT
from dri.storage import Store,now
from dri.http import Client,AccessBlocked
from dri.repository import register_sources,start_run,queue_item,finish_run,ingest
from dri.models import Document
from dri.statements import Statement,Quote
from dri.connectors.assembly import meeting_references
from dri.connectors.assembly_pdf import VERSION,extract,eligible,classification,floor_episodes,literal_quote_blocks

RUN='assembly-pdf-pilot-20261101-v4'

def manifest(store):
    refs={}
    for (text,) in store.db.execute("SELECT result FROM source_checks WHERE source_id='assembly_kr' ORDER BY id"):
        try:payload=json.loads(text).get('sample_response',{})
        except (ValueError,AttributeError):continue
        for method in ('nzbyfwhwaoanttzje','ncwgseseafwbuheph'):
            rows=[r for block in payload.get(method,[]) for r in block.get('row',[])]
            for r in meeting_references(rows):refs[r.record_number]=r
    return refs

def cached_pdf(store,url):
    for path,sha,stamp in store.db.execute('SELECT raw_path,sha256,fetched_at FROM fetches WHERE url=? AND status=200 AND raw_path IS NOT NULL ORDER BY id DESC',(url,)):
        p=store.root/path
        if p.exists() and p.read_bytes().startswith(b'%PDF'):
            if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:raise ValueError('Source PDF hash mismatch')
            return path,sha,stamp
    return None

def cached_extraction(store,url):
    for (text,) in store.db.execute('SELECT result FROM source_checks WHERE source_id=? AND url=? ORDER BY id DESC',('assembly_kr',url)):
        try:d=json.loads(text).get('internal_extraction')
        except (ValueError,AttributeError):continue
        if d and d.get('version')==VERSION:return d
    return None

def reviewed_statements(ref,data,qa,raw_sha):
    selected=[];parties={};episodes=floor_episodes(data['turns']);groups=defaultdict(list)
    for q in qa:
        if q['pdf_url']!=ref.pdf_url:continue
        if q['pdf_sha256']!=raw_sha:raise ValueError('QA belongs to another PDF revision')
        t=next((t for t in data['turns'] if t['ordinal']==q['ordinal']),None)
        if (not t or t['speaker_name']!=q['speaker_name'] or t['role']!=q['role']
            or t['spans']!=q['spans'] or hashlib.sha256(t['text'].encode()).hexdigest()!=q['text_sha256']):
            raise ValueError('Segmentation/text changed since source review; review again')
        required_checks={'author','date','boundaries','korean_text','bilateral_relevance'}
        if (q['status']!='pass' or not required_checks.issubset(q['checks'])
            or not all(q['checks'].values()) or not eligible(t)):
            raise ValueError('Failed/unreviewed turn cannot be imported')
        groups[(episodes[t['ordinal']],t['speaker_name'],t['role'])].append(t)
        if q.get('self_declared_party'):parties[t['speaker_name']]=q['self_declared_party']
        selected.append(t)
    statements=[]
    for (episode,name,role),turns in groups.items():
        quotes=[]
        for t in turns:
            loc=json.dumps({'protocol':ref.conf_id,'turn':t['ordinal'],'physical_page_column_y':t['spans']},ensure_ascii=False)
            for block in literal_quote_blocks(t['text']):quotes.append(Quote(block,'ko','ko','published_version',loc))
        if not quotes:raise ValueError('No substantive literal speech evidence')
        minister='외교부' in role
        statements.append(Statement(
            event_key=f'assembly:{ref.conf_id}:floor:{episode}:speaker:{name}:{role}',
            country='ROK',target_country='JPN',institution='Ministry of Foreign Affairs, Republic of Korea' if minister else 'National Assembly, Republic of Korea',
            context=f'{ref.title}; floor episode {episode}; selected complete turns '+','.join(str(t['ordinal']) for t in turns),
            published_date=None,spoken_date=ref.meeting_date,speaker_name=name,speaker_office=role,
            addressee='Parliamentary participants; Japan is the substantive topic, not necessarily the direct addressee',
            theme='historical_disputes' if ref.meeting_date.startswith('2015') else 'diplomatic_contacts',
            original_language='ko',verification_status='source_text_verified',attribution_confidence='high',
            attribution_evidence='Printed speaker marker, source meeting date and complete turn boundaries visually/textually reviewed by agent; not independent human validation. Multiple interrupted turns share a floor episode. Full protocol retained internally for context.',
            quotes=tuple(quotes),institution_type='foreign_ministry' if minister else 'parliament',
            speaker_role=role,political_affiliation=parties.get(name),
            statement_context='parliamentary_debate',position_scope='official_state_position' if minister else 'individual_position',
            metadata_evidence=ref.pdf_url+'; self-declared party only where explicitly in reviewed speech; government/opposition status not inferred.'))
    return statements,selected

def run(store,records,qa,run_key=RUN):
    config={'urls':[r.pdf_url for r in records],'parser':VERSION,'retention':'internal_research_only',
            'qa_sha256':hashlib.sha256(json.dumps(qa,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    rid=start_run(store,run_key,config,resume=True)
    client=Client(store,'windows',hosts={'record.assembly.go.kr'},retain_body=True)
    for ref in records:
        key=queue_item(store,rid,'assembly_kr',ref.pdf_url)
        item=store.db.execute('SELECT status FROM collection_items WHERE run_id=? AND item_key=?',(rid,key)).fetchone()[0]
        if item=='processed':continue
        try:
            raw=cached_pdf(store,ref.pdf_url)
            if not raw:
                # A previous published denial persists across restarts; do not retry the host.
                if store.db.execute("SELECT 1 FROM fetches WHERE url LIKE 'https://record.assembly.go.kr/%' AND status IN (401,403,429) LIMIT 1").fetchone():
                    raise AccessBlocked('Host previously denied access; no repeated request')
                client.check_robots(ref.pdf_url)
                status,headers,body,raw=client.request(ref.pdf_url)
                if status in (401,403,429):raise AccessBlocked(f'HTTP {status}; stop host')
                if status!=200 or not body.startswith(b'%PDF'):raise ValueError('Not a public text PDF')
            data=cached_extraction(store,ref.pdf_url)
            if data is None:
                data=extract(store.root/raw[0]);data['pdf_sha256']=raw[1]
                with store.db:
                    store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                        ('assembly_kr',ref.pdf_url,now(),200,json.dumps({'internal_extraction':data},ensure_ascii=False),raw[1]))
            elif data.get('pdf_sha256')!=raw[1]:raise ValueError('Cached extraction revision mismatch')
            statements,turns=reviewed_statements(ref,data,qa,raw[1])
            if statements:
                doc=Document(source='assembly_kr',url=ref.pdf_url,title=ref.title,published_date=None,event_date=ref.meeting_date,
                    text=data['text'],language='ko',publisher='National Assembly Secretariat, Republic of Korea',
                    rights='INTERNAL RESEARCH ONLY. Public protocol, source attribution retained. No public redistribution licence inferred; full text/raw files excluded from exports and views.',
                    content_policy='internal_research_only',official_identifier='assembly:minutes:'+ref.conf_id,
                    related_countries=('ROK','JPN'),country_scope='ROK',observation_type='parliamentary_minutes',
                    text_completeness='complete_extracted_body_without_page_headers',analysis_status='internal_research_context_with_reviewed_turns',
                    verification_status='reviewed_turns_only',institution=ref.organ,
                    rights_evidence='User-authorized internal research retention; publication requires separate rights review.',
                    research_metadata={'parser':VERSION,'pdf_sha256':raw[1],'conf_id':ref.conf_id,'confer_num':ref.record_number,
                        'pages':data['pages'],'reviewed_turn_ids':[t['ordinal'] for t in turns],
                        'complete_reviewed_turns':len(turns),'floor_speaker_records':len(statements),
                        'review_manifest':'data/assembly_pdf_review.json','ocr_used':False,'page_coordinates':'PDF physical pages, top-origin points, L then R'})
                outcome=ingest(store,doc,raw,statements,rid,key)
                replay=ingest(store,doc,statements=statements)
                if any(replay[k] for k in ('documents_added','statements_added','quotes_added')):raise AssertionError('Repeat import created entities')
            else:
                outcome={'documents_added':0,'statements_added':0,'quotes_added':0};replay=outcome.copy()
                with store.db:store.db.execute("UPDATE collection_items SET status='processed',updated_at=? WHERE run_id=? AND item_key=?",(now(),rid,key))
            check={'pdf_processed':True,'pages':data['pages'],'detected_turns':len(data['turns']),
                'japan_candidates':sum(bool(eligible(t)) for t in data['turns']),
                'classifications':dict(Counter(classification(t) for t in data['turns'])),
                'reviewed_turns':len(turns),'import':outcome,'repeat':replay,'parser':VERSION,'pdf_sha256':raw[1]}
            with store.db:store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                ('assembly_kr',ref.pdf_url,now(),200,json.dumps(check),raw[1]))
            finish_run(store,rid,'running')
            print(json.dumps({'url':ref.pdf_url,**check}),flush=True)
        except Exception as error:
            store.error('assembly_kr',ref.pdf_url,'pdf_collection',error)
            with store.db:store.db.execute('UPDATE collection_items SET status=?,error=?,updated_at=? WHERE run_id=? AND item_key=?',
                ('access_error' if isinstance(error,AccessBlocked) else 'parse_error',str(error),now(),rid,key))
            finish_run(store,rid,'partial')
            raise
    print(json.dumps(finish_run(store,rid)),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true')
    ap.add_argument('--report',action='store_true',help='Refresh existing reports offline')
    ap.add_argument('--batch',choices=('pilot','recent'),default='pilot');args=ap.parse_args()
    store=Store();register_sources(store)
    try:
        refs=manifest(store)
        numbers=['43902','40229','48009'] if args.batch=='pilot' else ['57630','57595','57592']
        records=[refs[k] for k in numbers]
        qa=json.loads((ROOT/'data/assembly_pdf_review.json').read_text(encoding='utf-8'))['reviewed_turns']
        print(json.dumps({'plan':[r.pdf_url for r in records],'execute':args.execute,'parser':VERSION,
            'network':'cached PDFs first; robots; >=5.5s; no API enumeration; stop on denial',
            'retention':'internal only; reviewed turns only; no OCR; no public text export'}),flush=True)
        if args.execute:run(store,records,qa,RUN+('' if args.batch=='pilot' else '-recent'))
        if args.report:report(store)
    finally:store.db.close()

def report(store):
    import re
    from dri.paths import write_generated
    from dri.quality import report as general_report
    marker='<!-- ASSEMBLY_PDF_20261101 -->';end='<!-- ASSEMBLY_PDF_20261101_END -->'
    # Retain dated results from previous stages when regenerating the common report.
    old=(ROOT/'docs/QUALITY_REPORT.md').read_text(encoding='utf-8')
    history=[]
    for tag in ('DOMESTIC_20261101','ASSEMBLY_API_20261101'):
        found=re.search('<!-- '+tag+' -->.*?<!-- '+tag+'_END -->',old,re.S)
        if found:history.append(found[0])
    integrity=general_report(store);store.export()
    quality=ROOT/'docs/QUALITY_REPORT.md';text=quality.read_text(encoding='utf-8')
    for block in history:
        if block not in text:text+='\n\n'+block
    write_generated(quality,text)
    def section(path,body):
        p=ROOT/path;t=p.read_text(encoding='utf-8')
        t=re.sub(re.escape(marker)+'.*?'+re.escape(end),'',t,flags=re.S).rstrip()
        write_generated(p,t+'\n\n'+marker+'\n'+body+'\n'+end+'\n')
    checks={}
    for url,result in store.db.execute("SELECT url,result FROM source_checks WHERE source_id='assembly_kr' ORDER BY id"):
        try:d=json.loads(result)
        except ValueError:continue
        if d.get('pdf_processed') and d.get('parser')==VERSION:checks[url]=d
    qa=json.loads((ROOT/'data/assembly_pdf_review.json').read_text(encoding='utf-8'))
    refs=manifest(store);byurl={r.pdf_url:r for r in refs.values()}
    reviewed=qa['reviewed_turns'];baseline=qa['stage_baseline']
    counts={t:store.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','statements','quotes')}
    documents=store.db.execute("SELECT id,metadata_json FROM documents WHERE source='assembly_kr' AND content_policy='internal_research_only'").fetchall()
    statement_count=store.db.execute("SELECT count(DISTINCT ss.statement_id) FROM statement_sources ss JOIN documents d ON d.id=ss.document_id WHERE d.source='assembly_kr'").fetchone()[0]
    quote_count=store.db.execute("SELECT count(DISTINCT qs.quote_id) FROM quote_sources qs JOIN documents d ON d.id=qs.document_id WHERE d.source='assembly_kr'").fetchone()[0]
    classifications=Counter()
    for d in checks.values():classifications.update(d['classifications'])
    rows=[
        '## Извлечение парламентских PDF РК — 1 ноября 2026',
        '',f'Исходно: {baseline["documents"]} документов / {baseline["statements"]} заявлений / {baseline["quotes"]} цитат, схема 4. Сейчас: {counts["documents"]} / {counts["statements"]} / {counts["quotes"]}.',
        '',f'Обработано {len(checks)} уникальных публичных PDF, {sum(d["pages"] for d in checks.values())} физических страниц. Сохранено {len(documents)} полных извлечённых контекстов протокола (без колонтитулов), {len(reviewed)} проверенных полных реплик, {statement_count} записей заявлений по автору и эпизоду и {quote_count} дословных цитатных блоков. Эти числа не складываются в единый показатель качества.',
        '',f'Найдено {sum(d["detected_turns"] for d in checks.values())} маркерных блоков до полного отсева. Из них {classifications["segmentation_needs_review"]} не прошли формальное распознавание автора/границы и не импортированы. Короткие/процедурные блоки: {classifications["short_or_procedural"]}; служебные доклады: {classifications["procedural_official_report"]}; без явного японского якоря: {classifications["not_explicitly_japan_related"]}.',
        '',f'Автоматических японских кандидатов: {sum(d["japan_candidates"] for d in checks.values())}. Подтверждённая тематическая релевантность: {len(reviewed)} проверенных реплик. Остальные кандидаты не объявлены релевантными и не импортированы. Наличие японского слова само по себе не является политическим событием.',
        '', '| Год | PDF | Маркерные блоки | Японские кандидаты | Проверенные полные реплики | Новые документы | Заявления | Цитатные блоки |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for year in range(2015,2027):
        ds=[d for u,d in checks.items() if byurl[u].meeting_date.startswith(str(year))]
        rcount=sum(byurl[q['pdf_url']].meeting_date.startswith(str(year)) for q in reviewed)
        doc_count=sum((json.loads(m).get('event_date') or '').startswith(str(year)) for _,m in documents)
        sc=store.db.execute("SELECT count(DISTINCT s.id) FROM statements s JOIN statement_sources ss ON ss.statement_id=s.id JOIN documents d ON d.id=ss.document_id WHERE d.source='assembly_kr' AND substr(s.spoken_date,1,4)=?",(str(year),)).fetchone()[0]
        qc=store.db.execute("SELECT count(DISTINCT q.id) FROM quotes q JOIN statements s ON s.id=q.statement_id JOIN quote_sources qs ON qs.quote_id=q.id JOIN documents d ON d.id=qs.document_id WHERE d.source='assembly_kr' AND substr(s.spoken_date,1,4)=?",(str(year),)).fetchone()[0]
        rows.append(f'| {year} | {len(ds)} | {sum(d["detected_turns"] for d in ds)} | {sum(d["japan_candidates"] for d in ds)} | {rcount} | {doc_count} | {sc} | {qc} |')
    rows += ['', 'Все новые тексты: Республика Корея, primary, парламентские протоколы; Япония и secondary — 0 новых записей. Место заседания отделено от органа автора: в корпусе есть депутаты и министр иностранных дел, отвечающий парламенту. Непосредственные адресаты — участники заседания; Япония — предмет высказывания, что явно указано в addressee.',
        '', '### Контроль качества',
        '',f'Целевая проверка агентом по PDF: {len(reviewed)} реплик; совпадение имени, даты, текста и границ — {len(reviewed)}/{len(reviewed)} в этой выборке. Включены 20 реплик внутри колонок 2019 года и 7 реплик 2015 года, включая переходы страниц/колонок. Это целевая, а не случайная выборка; 100% на ней не означает 100% точности парсера на остальных страницах. Независимой человеческой верификации не было.',
        '', 'Индивидуальные проверки и SHA-256 текста/страниц: внутренний data/assembly_pdf_review.json. Исходные PDF и их хэши — data/raw и observations; внутренние изображения data/assembly_layout.png и data/assembly_review_01.png … 06.png. Полные извлечения и технические результаты — source_checks в единственной базе. Изображения не являются публичным интерфейсом.',
        '', 'Порядок чтения: левая колонка → правая колонка → следующая страница. Колонтитулы исключены по проверенной геометрии A4. По завершении заседания (산회) приложения больше не сегментируются как речи. Неразобранные имена/роли и незакрытые границы из импорта исключены. OCR и автоматическая языковая правка не применялись. Неисправленные дефекты исходного текстового слоя возможны вне проверенных реплик.',
        '', 'Краткие ответы, технические распоряжения и случайные упоминания не считаются полноценными наблюдениями автоматически. Скобочные ремарки и анонимные выкрики сохранены в контексте, но удалённые куски не склеиваются в фиктивную цитату: цитатные блоки остаются непрерывными фрагментами исходного текста.',
        '', 'Несколько реплик одного говорящего в одном эпизоде парламентского вопроса–ответа не создают новые события. Ключ: CONF_ID + начало эпизода владения словом + говорящий + роль. Повторный выход того же депутата после другого выступающего — отдельный эпизод. Разные протоколы/даты не объединяются. Это консервативная единица парламентского выступления, а не атомарная семантическая претензия.',
        '', 'Есть критика соглашения/торговых мер, разъяснения правительства, поддержка соглашения и предложения прямого диалога и механизмов урегулирования. Полные ответы, включая связь с КНДР/региональной безопасностью, сохраняются; исключительно северокорейские реплики не включены. Полнота и баланс тональностей за весь период не утверждаются.',
        '', 'Для будущих частот доступны 27 проверенных реплик в их полном контексте; для частоты событий — 16 записей эпизодов/авторов. Вопросы–ответы и отбор коротких реплик создают смещение; применять эти числа как частоту всей политической риторики нельзя.',
        '',f'Повторный импорт: 0 новых документов / заявлений / цитат. Последующие запуски продолжают processed-checkpoints и не загружают PDF повторно. SQLite integrity={integrity["sqlite_integrity"]}; FK errors={len(integrity["foreign_key_errors"])}; raw hash errors={len(integrity["raw_hash_errors"])}; схема 4, миграций нет.',
        '', '### Внутреннее хранение и публикация',
        '', 'Полные протоколы, реплики и исходные PDF предназначены только для запрошенного внутреннего исследования; публикационная лицензия не присвоена. В единственной data/corpus.jsonl у внутренних документов text пуст, пути к исходникам скрыты; в существующем HTML-отчёте цитаты скрыты. Те же ограничения применены к ранее помеченным KOGL4 документам. Оригинальные данные в SQLite и data/raw сохранены. Два полных протокола — контекст, а не два политических заявления.',
        '', 'Сбор ограничен публичной выборкой. API-ключ не обходился, общий аудит не повторялся, МИД Японии не запрашивался. Следующий шаг — проверка оставшихся тематических кандидатов по той же процедуре; автоматического масштабного импорта нет.']
    section('docs/QUALITY_REPORT.md','\n'.join(rows))
    section('docs/SOURCE_AUDIT.md',
        '## Парламентские PDF: переход к внутреннему извлечению\n\n'
        'Использованы сохранённые публичные ссылки из ранее подтверждённых методов; API не переаудировался. '
        'По явному запросу пользователя полные тексты теперь сохраняются для внутреннего исследования, без утверждения права публикации. '
        f'Проверены {len(checks)} PDF; внутренние сырые файлы имеют SHA-256 и URL, протоколы связаны с CONF_ID и CONFER_NUM. '
        'Период отбора остаётся 2015-01-01–2026-10-31. Парсер читает текстовый слой; OCR не используется. '
        'Политика доступа прежняя: robots/TLS, минимум 5,5 секунды, размер до 4 МБ, остановка хоста на 401/403/429. '
        'Разрешение скачивания и внутреннего хранения не выдаётся за разрешение публичной перепубликации. '
        'Полные тексты и PDF-пути исключены из JSONL и существующей таблицы просмотра. '
        'Подробная статистика, ограничения сегментации и идентичности — в docs/QUALITY_REPORT.md.')
    section('README.md',
        '## Парламентские PDF: внутренний исследовательский корпус\n\n'
        'План без сети: `python scripts/collect_assembly_pdf.py`. '
        'Продолжить пилот с checkpoint: `python scripts/collect_assembly_pdf.py --execute`. '
        'Партия октября 2026: `python scripts/collect_assembly_pdf.py --batch recent --execute`. '
        'Обновить существующие отчёты без сети: `python scripts/collect_assembly_pdf.py --report`. '
        'Проверить код: `python scripts/run_tests.py`. Обработанные PDF не скачиваются повторно. '
        'Для импорта новых реплик необходима запись проверки с совпадающими SHA-256 PDF/текста, автором и координатами в data/assembly_pdf_review.json. '
        'Это агентная проверка по первоисточнику, не независимая человеческая разметка. '
        f'Результат этапа: {len(checks)} PDF, 27 проверенных реплик, 16 записей заявлений; полные тексты только внутри SQLite/raw. '
        'Публичная JSONL содержит лишь метаданные внутренних документов; существующий HTML не раскрывает их цитаты. '
        'Доступ к самому файлу SQLite и data/raw должен оставаться внутренним; публикация требует отдельной проверки прав. '
        'Коннектор использует уже установленные pdfplumber/pypdfium2, версии среды: '+
        __import__('importlib.metadata',fromlist=['version']).version('pdfplumber')+' / '+__import__('importlib.metadata',fromlist=['version']).version('pypdfium2')+'.')
    section('docs/CHANGES.md',
        '## Извлечение парламентских PDF — 2026-11-01\n\n'
        'Созданы dri/connectors/assembly_pdf.py, dri/publication.py, scripts/collect_assembly_pdf.py, tests/test_assembly_pdf.py, data/assembly_pdf_review.json. '
        'Изменены dri/models.py (исследовательские метаданные без миграции), dri/storage.py, dri/research.py, dri/audit_outputs.py, dri/audit_report.py, dri/quality.py, dri/expansion_outputs.py, config/sources.json. '
        'Обновлены README.md, docs/SOURCE_AUDIT.md, docs/QUALITY_REPORT.md, docs/CHANGES.md, docs/TEST_RESULTS.txt, docs/REVIEW_TABLE.html, data/dri.sqlite3, data/corpus.jsonl, data/verification.json. '
        'Добавлены исходные PDF в существующий data/raw, data/assembly_layout.png и data/assembly_review_01.png … 06.png как внутренние свидетельства проверки. '
        'Процедурные маркеры и приложения после закрытия заседания отсекаются; исправления парсера перепроверены на тех же хэшах без прироста сущностей. '
        'Два протокола служат контекстом 27 реплик; прерывания объединены в 16 эпизодов/авторов. '
        'Установок, миграций, новых баз, OCR, LLM, прогнозов и нового интерфейса нет. '
        'Тесты подтверждают границы страниц/колонок, фильтрацию служебных меток, эпизоды при прерываниях, исключение ремарок из цитат и запрет экспорта внутренних текстов.')
    v=ROOT/'data/verification.json';value=json.loads(v.read_text(encoding='utf-8'))
    value['assembly_pdf_20261101']={'parser':VERSION,'baseline':baseline,'after':counts,
        'processed_pdfs':len(checks),'physical_pages':sum(d['pages'] for d in checks.values()),
        'detected_marker_blocks':sum(d['detected_turns'] for d in checks.values()),
        'japan_candidates':sum(d['japan_candidates'] for d in checks.values()),
        'source_reviewed_complete_turns':len(reviewed),'new_documents':len(documents),
        'statement_floor_speaker_records':statement_count,'quote_blocks':quote_count,
        'review_pass_rate_in_purposive_sample':1.0,'independent_human_review':False,
        'public_text_export_allowed':False,'repeat_import_growth':{'documents':0,'statements':0,'quotes':0}}
    write_generated(v,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(value['assembly_pdf_20261101']),flush=True)

if __name__=='__main__':main()
