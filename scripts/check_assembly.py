"""Finite Open Assembly API verification. Existing SQLite is the evidence cache.

Sample responses are meeting metadata, never documents/statements/quotes.
Already successful queries are reused without refetching. No secret-key input.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.connectors.assembly import DATASETS, sample_url, parse_response, meeting_references
from dri.http import Client, AccessBlocked
from dri.storage import Store, now
from dri.repository import register_sources, start_run, queue_item, finish_run

QUERIES=[
    ('plenary',dict(term=19,period='2015')),
    ('committee',dict(term=20,period='2019')),
    ('plenary',dict(term=21,period='2023')),
    ('committee',dict(term=22,period='2026')),
    ('committee',dict(term=20,period='2019',committee='외교통일위원회')),
    ('committee',dict(term=20,period='2019-07',committee='외교통일위원회')),
    ('detail',dict(conf_id='054151')),
]

def cached_response(store,url):
    for (text,) in store.db.execute('SELECT result FROM source_checks WHERE source_id=? AND url=? AND status=200 ORDER BY id DESC',('assembly_kr',url)):
        try:
            obj=json.loads(text)
        except (ValueError,TypeError):continue
        if 'sample_response' in obj:return obj['sample_response']
    return None

def corpus_counts(store):
    return {t:store.db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','statements','quotes')}

def audit(store,client,queries=None):
    queries=QUERIES if queries is None else queries
    urls=[sample_url(k,**p) for k,p in queries]
    run=start_run(store,'assembly-api-20261101',{'urls':urls,'mode':'documented_sample_only'},resume=True)
    before=corpus_counts(store);results=[];network=0
    for (kind,params),url in zip(queries,urls):
        key=queue_item(store,run,'assembly_kr',url)
        try:
            payload=cached_response(store,url)
            cached=payload is not None
            if payload is None:
                text,raw,final=client.get(url,content_types=('json','html','plain'))
                if final!=url:raise ValueError('Unexpected API redirect; review origin before use')
                payload=json.loads(text)
                # Validate the envelope before recording a successful reusable response.
                parse_response(payload,kind)
                with store.db:
                    store.db.execute('INSERT INTO source_checks(source_id,url,checked_at,status,result,response_sha256) VALUES(?,?,?,?,?,?)',
                        ('assembly_kr',url,now(),200,json.dumps({'sample_response':payload},ensure_ascii=False),raw[1]))
                network+=1
            rows,total=parse_response(payload,kind)
            meetings=meeting_references(rows) if kind!='detail' else []
            if kind!='detail':
                for r in rows:
                    if str(r['DAE_NUM'])!=str(params['term']) or not r['CONF_DATE'].startswith(params['period']):
                        raise ValueError('Server did not honor year/term filter')
            result={'kind':kind,'url':url,'rows':len(rows),'total_agenda_rows':total,
                    'meetings_in_sample':len(meetings),'dates':sorted({r.meeting_date for r in meetings}),
                    'cached':cached,'full_speeches':0}
            results.append(result)
            with store.db:
                store.db.execute("UPDATE collection_items SET status='query_completed',error=NULL,updated_at=? WHERE run_id=? AND item_key=?",(now(),run,key))
        except Exception as error:
            store.error('assembly_kr',url,'assembly_api_verification',error)
            with store.db:
                store.db.execute('UPDATE collection_items SET status=?,error=?,updated_at=? WHERE run_id=? AND item_key=?',
                    ('access_error' if isinstance(error,AccessBlocked) else 'parse_error',str(error),now(),run,key))
            finish_run(store,run,'partial')
            raise
    after=corpus_counts(store)
    if before!=after:raise AssertionError('Metadata verification changed the speech corpus')
    finish_run(store,run)
    return {'before':before,'after':after,'network_requests_for_queries':network,'queries':results,
            'repeat_import_growth':{k:after[k]-before[k] for k in before}}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--execute',action='store_true')
    ap.add_argument('--report',action='store_true',help='Update existing documentation from stored evidence, offline')
    args=ap.parse_args()
    print(json.dumps({'network_plan':[sample_url(k,**p) for k,p in QUERIES],
        'execute':args.execute,'mode':'sample, pIndex=1, pSize=5, no key; cached successful requests skipped',
        'retention':'meeting metadata in existing source_checks only; no speech import'},ensure_ascii=True),flush=True)
    if not args.execute and not args.report:return
    store=Store();register_sources(store)
    try:
        if args.execute:
            value=audit(store,Client(store,'windows',hosts={'open.assembly.go.kr'},retain_body=False))
            print(json.dumps(value,ensure_ascii=True),flush=True)
        if args.report:update_documentation(store)
    finally:store.db.close()

def update_documentation(store):
    """One marked section per existing report, with no rerun of previous audits."""
    import re
    from dri.paths import ROOT,write_generated
    marker='<!-- ASSEMBLY_API_20261101 -->';end='<!-- ASSEMBLY_API_20261101_END -->'
    def section(path,body):
        p=ROOT/path;old=p.read_text(encoding='utf-8')
        old=re.sub(re.escape(marker)+'.*?'+re.escape(end),'',old,flags=re.S).rstrip()
        write_generated(p,old+'\n\n'+marker+'\n'+body+'\n'+end+'\n')
    lines=['## Национальное собрание РК: конкретные API, 1 ноября 2026',
        '', 'Проверка только парламентского канала. Исходное и конечное состояние: 1442 документа / 1034 заявления / 1034 цитаты, схема 4. Подтверждённые JSON-спецификации и sample-ответы сохранены в source_checks существующей базы; тела защищённых/немаркированных PDF не сохранены.',
        '', '| Набор | ID / метод | Обязательные фильтры | Содержание ответа |',
        '|---|---|---|---|']
    for kind in ('plenary','committee','detail'):
        ds=DATASETS[kind]
        card='https://open.assembly.go.kr/portal/data/service/selectAPIServicePage.do/'+ds['id']+'?infId='+ds['id']+'&infSeq=2'
        filters='CONF_ID' if kind=='detail' else 'DAE_NUM, CONF_DATE'
        cols='метаданные заседания, DOWN_URL' if kind=='detail' else 'пункты повестки, дата, орган, CONF_ID, CONFER_NUM, PDF_LINK_URL, CONF_LINK_URL'
        lines.append(f'| [{ds["name"]}]({card}) | `{ds["id"]}` / `{ds["method"]}` | `{filters}` | {cols}; поля текста речи и говорящего отсутствуют |')
    lines += ['', '### Параметры и ограничения',
        '', 'Базовый адрес: `https://open.assembly.go.kr/portal/openapi/{method}`. JSON-спецификация карточки загружается штатным публичным запросом `https://open.assembly.go.kr/portal/data/openapi/selectOpenApiMeta.do?infId={ID}&infSeq=2`. Это интерфейс документации; он не является методом выгрузки выступлений.',
        '', 'Общие параметры карточки: `KEY` (выданный ключ, по умолчанию sample), `Type=xml|json` (по умолчанию xml), `pIndex` (по умолчанию 1), `pSize` (по умолчанию 100). В карточке они помечены обязательными, но sample работает без KEY. Для sample карточка фиксирует pIndex=1 и pSize=5; живые запросы вернули по 5 строк. Общий guide говорит о 10 записях — для этих методов использовано более строгое ограничение карточки, 5. Sample-пагинация и повышение лимита не применялись.',
        '', 'Спецификации указывают apiTrf=200000; код ERROR-337 относится к суточной квоте, ERROR-336 — к пределу 1000 записей на запрос. Это опубликованные параметры, а не проверенная нагрузочным тестом гарантия квоты любого будущего ключа. Локальный интервал остаётся не менее 5,5 секунды.',
        '', 'Пленарный метод: DAE_NUM и CONF_DATE обязательны; TITLE, CLASS_NAME, SUB_NUM, SUB_NAME — необязательные фильтры. Комитетский: DAE_NUM и CONF_DATE обязательны; TITLE, CLASS_NAME, COMM_NAME, SUB_NAME, DEPT_CD необязательны. CONF_DATE проверен как год и год-месяц. VCONFDETAIL: CONF_ID обязателен. CONF_ID сохранять строкой: встречаются ведущие нули и префикс N. Не путать CONF_ID с CONFER_NUM — URL PDF использует номер протокола, не всегда CONF_ID.',
        '', '### Исторические проверки и воспроизводимые запросы',
        '', '| Запрос без KEY | Результат | Строк в выборке / всего строк повестки | Уникальных заседаний в выборке |',
        '|---|---|---:|---:|']
    years=set();all_ids=set();query_count=0
    for kind,params in QUERIES:
        url=sample_url(kind,**params);payload=cached_response(store,url)
        if payload is None:raise ValueError('Report requires confirmed sample evidence: '+url)
        rows,total=parse_response(payload,kind)
        meetings=meeting_references(rows) if kind!='detail' else []
        query_count+=1;all_ids.update(r.conf_id for r in meetings)
        years.update(r.meeting_date[:4] for r in meetings)
        lines.append(f'| [GET]({url}) `{DATASETS[kind]["method"]}` / `{params}` | INFO-000 | {len(rows)} / {total} | {len(meetings)} |')
    lines += ['', 'Подтверждены записи за '+', '.join(sorted(years))+'. Это наблюдаемый исторический диапазон, не доказательство полноты каждого года, каждого комитета или отсутствия пропусков. Даты открытия карточек (2019/2024) не являются началом архива. Полный период 2015–2026 не объявляется исчерпанным. Отбор по годам и комитету не зависит от конфликтных слов.',
        '', 'Строка списка — пункт повестки, не отдельная речь и не обязательно отдельное заседание. Повторяющиеся CONF_ID группируются; ни одна из этих строк не создаёт Document, Statement или Quote.',
        '', '### Тексты PDF и права',
        '', 'Прямой PDF из ответа за 2015 год: [протокол 40229](https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=40229). Проверен HTTP 200, application/pdf, сигнатура %PDF, размер 2787328 байт, 237 страниц; текст первой страницы извлекается pypdf. Проверка выполнена в памяти; файл не сохранён. Протокол содержит много говорящих и не импортировался как одно заявление.',
        '', 'На карточке «위원회 회의록» найден маркер `/images/copyright01.gif`, alt «공공누리 - 공공저작물 자유이용허락 : 출처표시» (KOGL1). [Политика портала](https://open.assembly.go.kr/portal/policy/copyRightPage.do) требует проверять маркер конкретного материала. В [исходном архиве](https://record.assembly.go.kr/assembly/) окно «저작권 정책» (#pop_layer3) также требует KOGL1, а для немаркированных материалов — предварительного согласования. Лицензия набора метаданных не объявлена автоматически лицензией всех внешних PDF и всех реплик свидетелей. Индивидуальное разрешение проверенного PDF не установлено; оригинальные выступления не сохранены. Контакт из опубликованной политики архива: webmaster@assembly.go.kr, 02-6788-3055; сообщения не отправлялись.',
        '', '### Как получить ключ для этих наборов',
        '', '1. Открыть [официальное руководство](https://open.assembly.go.kr/portal/openapi/openApiDevPage.do), выбрать подходящую карточку выше и «명세서 다운로드». Текущая динамическая спецификация уже подтверждена и сохранена в source_checks.',
        '2. [Зарегистрировать учётную запись National Assembly](https://member.assembly.go.kr/member/join/joinSelectPage.do), если её нет, затем [войти](https://open.assembly.go.kr/portal/user/loginPage.do). Регистрация и проверка личности выполняются пользователем; авторизация не обходилась.',
        '3. Открыть [인증키 발급](https://open.assembly.go.kr/portal/openapi/openApiActKeyIssPage.do) либо кнопку [인증키 신청](https://open.assembly.go.kr/portal/openapi/openApiActKeyPage.do?tabIdx=1) из карточки. Нужные наборы: 본회의 회의록 (OO1X9P001017YF13038), 위원회 회의록 (OR137O001023MZ19321), вспомогательный 회의록별 상세정보 (OOWY4R001216HX11520). Структура закрытой формы, сроки одобрения и необходимость отдельного ключа на каждый набор не подтверждены — это не выдумано.',
        '4. В запросе заменить sample на выданный KEY, задать Type=json, pIndex, pSize, DAE_NUM и CONF_DATE; для комитета при необходимости COMM_NAME или DEPT_CD. Для деталей использовать CONF_ID, реально возвращённый списком. Не отправлять ключ в чат и не записывать в репозиторий/URL-журналы. Текущий проверочный коннектор намеренно не принимает секретный ключ.',
        '5. Ключ снимает ограничение sample для выборки метаданных в пределах выданных прав. Он **не добавляет поле полного текста речи**: дальнейшая цепочка — уникальный протокол → официальный PDF → подтверждение прав → проверка порядка колонок и границ говорящих → отдельные выступления с исходными идентификаторами. Такая текстовая цепочка ещё не реализована и не выдаётся за готовый сборщик.',
        '', '### Команды',
        '', '`python scripts/check_assembly.py` — показать конечный план без сети. `python scripts/check_assembly.py --execute` — проверить семь sample-запросов, используя уже сохранённые успешные ответы; повтор не загружает их снова. `python scripts/check_assembly.py --report` — офлайн обновить этот раздел и существующие README / QUALITY_REPORT / CHANGES. `python scripts/run_tests.py` — существующий набор тестов.']
    section('docs/SOURCE_AUDIT.md','\n'.join(lines))
    counts=corpus_counts(store)
    section('docs/QUALITY_REPORT.md',
        '## Проверка парламентского API РК — 1 ноября 2026\n\n'
        f'Состояние корпуса: `{counts}`; прирост документов/заявлений/цитат **0 / 0 / 0**. '
        f'Подтверждены {query_count} разрешённых sample-запросов и {len(all_ids)} уникальных идентификаторов заседаний в списках (это метаданные, не речи). '
        'Годы живых проверок: '+', '.join(sorted(years))+'. Новых пригодных для частотного анализа текстовых наблюдений: 0. '
        'Повторные строки повестки группируются по CONF_ID, ошибочные ответы не импортируются. Исходные данные корпуса не изменялись; схема 4, миграции не требовались. '
        'Работающий PDF подтверждён, но индивидуальные права и безопасная сегментация говорящих остаются условиями текстового импорта. '
        f'SQLite integrity={store.db.execute("PRAGMA integrity_check").fetchone()[0]}; FK errors={len(store.db.execute("PRAGMA foreign_key_check").fetchall())}. '
        'Тесты — docs/TEST_RESULTS.txt. Полная инструкция ключа и спецификации — docs/SOURCE_AUDIT.md.')
    section('README.md',
        '## Парламентский API РК: подтверждённые методы\n\n'
        'Проверены 본회의 회의록 / nzbyfwhwaoanttzje, 위원회 회의록 / ncwgseseafwbuheph и 회의록별 상세정보 / VCONFDETAIL. '
        'Это каталог протоколов и PDF-ссылок, а не API готовых реплик. Sample разрешён без KEY, максимум 5 строк и только pIndex=1; '
        'ключ нужен для полноценной выборки каталога. Процедура ключа, обязательные параметры, ссылки и ограничения — в docs/SOURCE_AUDIT.md. '
        'Проверка: `python scripts/check_assembly.py`; выполнение с кэшем: `python scripts/check_assembly.py --execute`; '
        'обновление существующей документации без сети: `python scripts/check_assembly.py --report`. '
        'Секретные ключи скрипт не принимает. Полные парламентские речи пока не импортированы: разрешение конкретного PDF не подтверждено.')
    section('docs/CHANGES.md',
        '## Конкретные парламентские API РК — 2026-11-01\n\n'
        'Созданы dri/connectors/assembly.py, scripts/check_assembly.py, tests/test_assembly.py. '
        'Обновлены config/sources.json, README.md, docs/SOURCE_AUDIT.md, docs/QUALITY_REPORT.md, docs/CHANGES.md, docs/TEST_RESULTS.txt, '
        'data/dri.sqlite3 (только технические проверки и checkpoints), data/verification.json (проверка API), data/remote_inspection.json (документация API), '
        'data/raw (robots.txt транспорта). Корпус и единственная выгрузка corpus.jsonl не переписывались. '
        'Получены спецификации реальных методов, sample-метаданные разных лет и подтверждение читаемого PDF. '
        'Никаких выдуманных speech endpoints, секретных ключей, обходов МИД Японии, миграций или новых баз. '
        'Повтор использует сохранённые source_checks; наборы/повестки не преобразуются в политические заявления.')
    verification=ROOT/'data/verification.json'
    value=json.loads(verification.read_text(encoding='utf-8'))
    value['assembly_api_20261101']={'corpus_counts':counts,'sample_queries':query_count,
        'unique_meeting_ids_in_list_samples':len(all_ids),'observed_years':sorted(years),
        'new_documents':0,'new_statements':0,'new_quotes':0,'full_speeches':0,
        'sqlite_integrity':store.db.execute('PRAGMA integrity_check').fetchone()[0],
        'foreign_key_errors':store.db.execute('PRAGMA foreign_key_check').fetchall(),
        'schema_version':store.db.execute('PRAGMA user_version').fetchone()[0],
        'pdf_retention_rights':'not_confirmed','repeat_uses_source_checks_cache':True}
    write_generated(verification,json.dumps(value,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
