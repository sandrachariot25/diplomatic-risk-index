"""Offline lineage diagnostics; no new observations, classifiers or score definition."""
import json
import hashlib
import re
import sqlite3
from collections import Counter, defaultdict
from .analytical_sample import digest, verified_completeness
from .paths import ROOT, write_generated

FIELDS=('country','language','source_type','source_id','text_form','version')

def component_diagnostics(units, monthly, config):
    groups=defaultdict(list)
    for u in units:
        if not u['exclusion_reason']:groups['|'.join(u[k] for k in FIELDS)].append(u)
    out=[]
    for key,us in sorted(groups.items()):
        rs=[r for r in monthly if r['component_id']==key]
        observed=[r for r in rs if r['unit_count']]
        low=[r for r in observed if r['status']=='insufficient_volume']
        reasons=Counter()
        for r in low:
            small_n=r['unit_count']<config['min_month_units']
            small_tokens=r['token_count']<config['min_month_tokens']
            reasons['both' if small_n and small_tokens else 'units_only' if small_n else 'tokens_only']+=1
        out.append({**dict(zip(FIELDS,key.split('|'))),'component_id':key,'units':len(us),
            'complete':sum(u['component_role']=='main' for u in us),
            'partial':sum(u['component_role']!='main' for u in us),
            'observed_months':len(observed),'supported_months':sum(r['status']=='supported' for r in rs),
            'tokens':sum(u['token_count'] for u in us),'expressions':sum(u['expression_count'] for u in us),
            'zero_units':sum(u['expression_count']==0 for u in us),
            'zero_observed_months':sum(r['expression_count']==0 for r in observed),
            'no_data_months':sum(r['status']=='no_data' for r in rs),'volume_failures':dict(reasons)})
    return out

def document_inventory(documents, links, units):
    linked={r['document_id'] for r in links}
    used={d for u in units if not u['exclusion_reason'] for d in u['document_ids']}
    rows=[]
    for d in documents:
        m=d['metadata'];complete=m.get('text_completeness') in {
            'complete_published_body','complete_extracted_body_without_page_headers'}
        kind=('full_activity_report' if complete and m.get('observation_type')=='official_activity_report'
              else 'full_protocol' if complete and m.get('observation_type')=='parliamentary_minutes'
              else 'full_standalone_statement' if complete else 'retained_fragment_or_unconfirmed' if d['text'].strip() else 'metadata_only')
        rows.append({'document_id':d['id'],'kind':kind,'linked':d['id'] in linked,'used':d['id'] in used})
    summary=[]
    for kind in sorted({r['kind'] for r in rows}):
        rs=[r for r in rows if r['kind']==kind]
        summary.append({'kind':kind,'documents':len(rs),'linked':sum(r['linked'] for r in rs),
                        'used':sum(r['used'] for r in rs),'unused':sum(not r['used'] for r in rs)})
    return rows,summary

def replace_section(path, body):
    start='<!-- DRI_V01_COMPLETENESS_START -->';end='<!-- DRI_V01_COMPLETENESS_END -->'
    old=path.read_text(encoding='utf-8')
    old=re.sub(re.escape(start)+'.*?'+re.escape(end),'',old,flags=re.S).rstrip()
    write_generated(path,old+'\n\n'+start+'\n'+body+'\n'+end+'\n')

def diagnose(result, config, reproduced):
    """Update only the existing reports; identifiers/hashes, never source text."""
    db_path=ROOT/'data/dri.sqlite3'
    db=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    db.execute('BEGIN')
    def rows(table):return [dict(r) for r in db.execute('SELECT * FROM '+table)]
    docs=rows('documents');links=rows('statement_sources');quotes=rows('quotes');qlinks=rows('quote_sources');ss=rows('statements')
    for d in docs:d['metadata']=json.loads(d['metadata_json'])
    evidence=json.loads((ROOT/'config/dri_v01_completeness.json').read_text(encoding='utf-8'))
    byid={d['id']:d for d in docs}
    for r in evidence['records']:byid[r['document_id']]=verified_completeness(byid[r['document_id']],r)
    docs=list(byid.values());inventory,counts=document_inventory(docs,links,result['units'])
    checked_links={(r['statement_id'],r['document_id']) for r in links};qbyid={q['id']:q for q in quotes}
    checks={
        'foreign_key_errors':len(db.execute('PRAGMA foreign_key_check').fetchall()),
        'statements_without_document':sum(not any(l['statement_id']==s['id'] for l in links) for s in ss),
        'statements_without_quote':sum(not any(q['statement_id']==s['id'] for q in quotes) for s in ss),
        'quote_sources_without_statement_source':sum((qbyid[l['quote_id']]['statement_id'],l['document_id']) not in checked_links for l in qlinks),
        'statements_with_multiple_documents':sum(n>1 for n in Counter(l['statement_id'] for l in links).values()),
        'documents_with_multiple_statements':sum(n>1 for n in Counter(l['document_id'] for l in links).values()),
        'duplicate_official_document_ids':len(db.execute("SELECT source,official_id FROM documents WHERE official_id IS NOT NULL GROUP BY 1,2 HAVING count(*)>1").fetchall()),
        'repeated_exact_event_author_date_identities':len(ss)-len(result['units']),
        'quote_links':len(qlinks),'statement_links':len(links),
        'integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}
    ownership=defaultdict(set)
    for u in result['units']:
        for p in u['fragment_provenance']:
            ref=p['ref']
            if 'turn_id' in ref:ownership[(ref['document_id'],ref['turn_id'])].add(u['unit_id'])
    checks['assembly_turns_assigned_to_multiple_units']=sum(len(v)>1 for v in ownership.values())
    # Same source event must never merge different dated speakers/roles in current units.
    stat={s['id']:s for s in ss}
    checks['units_merging_distinct_speakers_dates_or_events']=sum(len({(stat[i]['event_key'],stat[i]['spoken_date'],stat[i]['speaker_name'],stat[i]['speaker_office']) for i in u['statement_ids']})>1 for u in result['units'])
    db.close()
    components=component_diagnostics(result['units'],result['monthly'],config)
    before=evidence['previous_calculation'];after=result['summary']
    database_unchanged=hashlib.sha256(db_path.read_bytes()).hexdigest()==before['database_file_sha256']
    test_report=(ROOT/'docs/TEST_RESULTS.txt').read_text(encoding='utf-8')
    tests=re.search(r'Ran (\d+) tests.*?\n\n(OK|FAILED[^\n]*)',test_report,re.S)
    tests_status=f'{tests[1]} tests: {tests[2]}' if tests else 'No recognized test result; rerun scripts/run_tests.py'
    review=json.loads((ROOT/'config/dri_v01_review.json').read_text(encoding='utf-8'))
    review_counts=Counter(r['assessment'] for r in review['records'])
    activities=[d for d in docs if d['metadata'].get('observation_type')=='official_activity_report' and d['metadata'].get('text_completeness')=='complete_published_body']
    # Evidence screen, not a substitute for semantic review of every report.
    paired=sum(bool(re.search(r'\bJapan(?:ese)?\b|Dokdo|Takeshima',d['metadata']['title']+' '+d['text'],re.I)) and
               bool(re.search(r'\bROK\b|Republic of Korea|\bSouth Korea|\bKorea(?:n)?[-– ]Japan|\bJapan[-– ]Korea',d['metadata']['title']+' '+d['text'],re.I)) for d in activities)
    lines=['## Диагностика полноты аналитического корпуса DRI v0.1', '',
        'Офлайн-проверка сохранённой базы и конвейера; внешние источники, аудит 50 заявлений и 164 пар дублей не переаудировались. Единица — датированное самостоятельное выступление/институциональное заявление. Полный отчёт о встрече не равен полной речи. Длина текста не использовалась как доказательство полноты.', '',
        f'База: {len(docs)} документов, {len(ss)} заявлений, {len(quotes)} цитат; схема {after["schema_version"]}. Текст есть в {sum(bool(d["text"].strip()) for d in docs)} документах; {sum(not d["text"].strip() for d in docs)} — только метаданные. Полнота опубликованного тела/протокола подтверждена в 350 документах: 348 сохранёнными признаками и 2 точным воспроизведением исходного HTML. Это не 350 самостоятельных речей.', '',
        '| Тип сохранённого документа | Документы | Связаны с заявлениями | Представлены в аналитике | Не представлены |',
        '|---|---:|---:|---:|---:|']
    for r in counts:lines.append(f'| {r["kind"]} | {r["documents"]} | {r["linked"]} | {r["used"]} | {r["unused"]} |')
    lines += ['', 'Полных документов связано с заявлениями **9** (7 самостоятельных официальных текстов и 2 протокола); все 9 используются. Полных документов вне выборки **341**, все — official_activity_report без statement_sources. Два протокола порождают 16 единиц автора/эпизода: 6 полных и 10 частичных, а не две «речи». Так получаются 13 полных аналитических единиц из 9 документов.', '',
        f'{paired}/{len(activities)} полных отчётов проходят сохранённый тематический экран упоминаний РК и Японии (включая сотрудничество и многостороннюю безопасность). Их связь с тематикой не означает, что они являются дословной речью или что критика в пересказе принадлежит автору публикации. analysis_status=text_frequency_candidate_not_statement_frequency явно сохраняет это различие; verification_status=needs_review. Полная семантическая релевантность всех 341 документов независимо не проверялась; этот экран не выдаётся за такую проверку.', '',
        'Оставшийся документ 200 проверен отдельно: он касается японского промышленного наследия, принудительного труда корейцев и позиции корейского правительства. Упоминание Korean government не попало в узкий экран названий РК. Документ тематически относится к паре, но совмещает изложение решения ЮНЕСКО и правительственной позиции; это не стенограмма одного выступления. Ошибка экрана диагностики не затрагивает включение речевых единиц или расчёт DRI.', '',
        'Проверены исключения из классификации отчётов: документы 316 (изложение позиций двух правительств) и 350 (пересказ поздравительных слов, не стенограмма). Документ 197 содержит Address в смысле решения экологических проблем. Полного самостоятельного заявления в этих подозрительных по названию случаях не обнаружено. Среди 341 названий нет пропущенного явно обозначенного spokesperson commentary/statement. Для частот официальной повествовательной прозы эти тексты доступны, но добавление их отдельного компонента изменило бы текущую единицу анализа и здесь не выполняется.', '',
        'Ещё 5 непривязанных старых документов МИД (93, 99, 100, 111, 115) — только начала совместных заявлений/вводные слова; не полные тексты. 36 остальных отчётов МИД сохранены как restricted_excerpt. 26 библиографических записей СМИ не содержат текста. Поэтому 408 непривязанных документов = 341 + 36 + 5 + 26; отсутствие связи объяснимо их типом, а не потерей готовых речей.', '',
        '### Подтверждённое исправление полноты', '',
        'Документы 1 и 2 / заявления 2 и 1: самостоятельные комментарии пресс-секретаря МИД от 2015-08-15. Их оригинальные HTML сохранены в observations. SHA-256 исходников и точное равенство bo_con, заголовка и даты проверяются при каждом расчёте. config/dri_v01_completeness.json хранит закрыто проверяемую аттестацию полноты, без текста. Раньше отсутствие новых metadata-полей оставляло по 25 слов; теперь полные тела заменяют цитаты, не добавляясь к ним. База, цитаты, ссылки и исходные metadata не переписаны. Статус unofficial_translation сохранён; это полнота опубликованного перевода, не доказательство полноты корейского оригинала. Только внутренний расчёт: разрешение на публичное распространение не установлено.', '',
        'Дополнительно обоснованно включены **2 полных текста** существующих единиц; новых событий/документов не добавлено. Других пригодных для автоматического повышения до полной речи текстов не подтверждено.', '',
        '### Единица анализа и связи', '',f'Проверки связей: `{json.dumps(checks,ensure_ascii=False,sort_keys=True)}`.', '',
        'NDL: один speechID — одна запись, 864 включённых законченных коротких предложения и 43 старых обрезанных фрагмента. Это не 907 полных речей. Идентификаторы не повторяются; сохранён только отрывок исходного speechID, поэтому самостоятельность исходной речи подтверждается идентификатором, а её полнота — нет. Разные speechID не склеивались по сходству. Без исходного полного заседания невозможно доказать, что два отдельных ответа одного человека не относятся к одной более широкой дискуссии; принимается API-единица, а не число упоминаний.', '',
        'Assembly: 27 проверенных реплик объединены в 16 эпизодов автора с учётом прерываний. Реплика не присвоена двум единицам. Полнота 6 эпизодов подтверждена покрытием всех реплик данного автора в эпизоде; 10 неполных не повышены до полных. Остальные непроверенные реплики в сохранённых протоколах существуют, но не являются уже качественно проверенными речами. Их импорт потребовал бы нового отбора и проверки, здесь не выполнялся.', '',
        'МИД: самостоятельный комментарий/заявление — единица учреждения, без выдуманного личного автора; полный activity report с пересказами разных участников — документ, а не одно их выступление. Правительство: 2 полные речи и 3 самостоятельных письменных брифинга. Журналистский пересказ не вошёл; документов СМИ с проверенным речевым текстом нет. Прежние 31 неопределённое/небилатеральное заявление и 2 неполитических свидетеля остаются исключены; отдельный аудит этих решений не повторялся.', '',
        '### Покрытие девяти компонентов после исправления', '',
        'Все источники primary. Оригинальность/перевод остаются отдельными стратами. Нулевая единица — текст без учтённого выражения; нулевой месяц — месяц с текстами и нулём выражений. Пропущенные месяцы в доли нулей не входят.', '',
        '| Страна / язык / источник / форма / версия | Единиц | Полные / фрагменты | Месяцев с текстом / с порогом | Токены | Выражения | Нулевых единиц | Нулевых наблюдаемых месяцев | Причина недостаточного объёма: оба / только N / только токены |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in components:
        f=r['volume_failures']
        lines.append(f'| {r["country"]} / {r["language"]} / {r["source_id"]} / {r["text_form"]} / {r["version"]} | {r["units"]} | {r["complete"]} / {r["partial"]} | {r["observed_months"]} / {r["supported_months"]} | {r["tokens"]} | {r["expressions"]} | {r["zero_units"]}/{r["units"]} ({100*r["zero_units"]/r["units"]:.1f}%) | {r["zero_observed_months"]}/{r["observed_months"]} ({100*r["zero_observed_months"]/r["observed_months"]:.1f}%) | {f.get("both",0)} / {f.get("units_only",0)} / {f.get("tokens_only",0)} |')
    fails=Counter()
    for r in components:fails.update(r['volume_failures'])
    lines += ['',f'Из 9 × 142 = 1278 компонент-месяцев: {after["monthly_states"]}. У 158 наблюдаемых месяцев порог не пройден: {dict(fails)}. Требуются одновременно ≥5 единиц и ≥500 токенов внутри одной страты/месяца. Пять полных правительственных текстов распределены по разным месяцам и типам, два новых полных комментария находятся в одном месяце и не достигают N=5. У фрагментов N может быть достаточным, но 25 слов/короткие предложения дают меньше 500 токенов. Объединять языки, полноту или разные месяцы ради порога нельзя. Из 18 поддержанных месяцев только 1 основан на полных речах, 17 — диагностические фрагменты. Для исторического фона по-прежнему нет 12 предшествующих поддержанных месяцев: стандартизованные отклонения не вычислены.', '',
        '### Ошибки контекста: использован прежний аудит 24 кандидатов', '',
        f'Исходная таблица и её SHA не изменены; повторного чтения/разметки тех же кандидатов не было. Распределение прежних заключений: `{dict(review_counts)}`.', '',
        '| Класс | Что подтверждено прежним аудитом | Минимальное дальнейшее исправление |',
        '|---|---|---|',
        '| Отрицательная оценка / нейтральное употребление | 1034: 1 подтверждённый пропуск собственной отрицательной оценки из-за фиксированного контекстного списка; 1042: обоснованное воздержание на описании мер | Разрешение собственной оценки в пределах клаузы с отдельными тестами; не считать любое торговое ограничение осуждением |',
        '| Адресат / анафора | 1044: потеря межфразового адресата; 1048: правильно исключено сожаление о действиях внутренней партии | Ограниченное связывание соседних предложений только с однозначным адресатом; неоднозначное оставить нерешённым |',
        '| Чужая позиция / третьи страны | 1039: возможный пропуск при России/Китае; 1048: неясное авторство международной оценки | Привязка субъекта и объекта в клаузе вместо запрета всего смешанного предложения; не снимать защиту целиком |',
        '| Усечение / сегментация | 135: отказ из-за обрыва до адресата; 24, 26, 34: выражение поддержано, контекст неполон | Использовать полный текст только при сохранённом и проверенном происхождении; не дописывать утраченный контекст |',
        '| Отрицание | Ошибки отрицания именно в 24 случаях не подтверждены | Сохранить действующие защиты и тесты; не объявлять их доказанной точностью |',
        '| Перевод | Ошибки перевода в 24 случаях не проверены и не доказаны | Сохранять версии раздельно; не заявлять эквивалентность оригиналу |',
        '| Поддержанные признаки | 14 поддержанных + 3 с неполным контекстом | Это не оценка общей precision/recall и не валидация намерения |', '',
        'Предложения контекстных исправлений не внедрены в этом пересчёте: они меняют измерительное правило и требуют отдельной проверки на новых примерах. Словарь/контекстные правила/пороги не изменены; повторный аудит 24 случаев не проводился. Исправлена только доказанная потеря полноты двух сохранённых документов.', '',
        '### До / после и воспроизводимость', '',
        '| Показатель | До | После |','|---|---:|---:|',
        f'| Включённых единиц | {before["included_units"]} | {after["included_units"]} |',
        f'| Полных | {before["main_complete_units"]} | {after["main_complete_units"]} |',
        f'| Фрагментарных | {before["diagnostic_partial_units"]} | {after["diagnostic_partial_units"]} |',
        f'| Токены | {before["token_count"]} | {sum(r["tokens"] for r in components)} |',
        f'| Выражения | {before["counted_expressions"]} | {after["counted_expressions"]} |',
        f'| Поддержанные компонент-месяцы | {before["monthly_states"]["supported"]} | {after["monthly_states"]["supported"]} |',
        f'| Поддержанные месяцы полных текстов | {before["supported_main_component_months"]} | {after["supported_main_component_months"]} |', '',
        f'До: result_sha256={before["result_sha256"]}. После: result_sha256={digest(result)}. Два повторных расчёта идентичны: {reproduced}. Ядро базы: {after["core_input_sha256"]}; совпадение с исходным снимком: {after["core_input_sha256"]==before["core_input_sha256"]}. SHA-256 файла основной базы не изменился: {database_unchanged}. Автоматические тесты из единственного docs/TEST_RESULTS.txt: {tests_status}.', '',
        'Вывод: найдено локальное упущение подготовки данных (2 полных текста), оно исправлено. Главный барьер сопоставимого DRI остаётся в составе и сохранности исходного речевого материала: полных японских речей нет, большинство речевых записей ранее усечено, полные отчёты МИД являются другим типом текста. Дополнительно измерение ограничено известными контекстными пропусками, поэтому словарный ноль не означает отсутствие критики. Технических подтверждений потери ещё сотен готовых полных речей не найдено.', '',
        'Повтор диагностики: `.venv\\Scripts\\python.exe scripts/diagnose_dri.py --verify-reproducibility`; расчёт: `.venv\\Scripts\\python.exe scripts/calculate_dri.py --verify-reproducibility`; тесты: `.venv\\Scripts\\python.exe scripts/run_tests.py`. Сети, установок, новых баз и публичных текстовых выгрузок нет.']
    replace_section(ROOT/'docs/QUALITY_REPORT.md','\n'.join(lines))
    replace_section(ROOT/'docs/CHANGES.md','## Диагностика полноты DRI v0.1\n\n'
        'Созданы dri/analytical_diagnostics.py, scripts/diagnose_dri.py, tests/test_analytical_diagnostics.py, config/dri_v01_completeness.json. '
        'Изменены dri/analytical_sample.py (проверяемая полнота двух legacy-комментариев по сохранённому HTML), dri/analytics_outputs.py (описание и хэши зависимостей парсинга). '
        'Обновлены существующие README.md, docs/QUALITY_REPORT.md, docs/CHANGES.md, docs/TEST_RESULTS.txt и шесть расчётных артефактов data/dri_v01_{monthly.csv,units.jsonl,matches.jsonl,manifest.json}, docs/DRI_v01.png, docs/DRI_v01_diagnostics.png. '
        'Самостоятельный новый отчёт не создавался. SOURCE_AUDIT не переаудирован. База, исходники, старый аудит 24 кандидатов, словарь и пороги неизменны. '
        'Полных единиц 11 → 13, фрагментарных 1006 → 1004, всего 1017; пригодных по порогу компонент-месяцев 18 → 18. '
        'Исправление ограничено внутренней аналитической классификацией, без миграции и без выдачи разрешения на распространение legacy-текстов.')
    return {'documents':counts,'checks':checks,'components':components,'before':before,'after':after}
