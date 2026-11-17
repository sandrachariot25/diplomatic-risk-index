"""Coverage counts are descriptive; no source weights or tension scores."""
import hashlib
import json
from html import escape
from .paths import ROOT
from .storage import now

def report(store):
    db=store.db
    from .audit_report import update_source_audit
    from .repository import run_counters
    with db:
        for (rid,) in db.execute('SELECT id FROM collection_runs').fetchall():
            db.execute('UPDATE collection_runs SET counters_json=? WHERE id=?',(json.dumps(run_counters(store,rid)),rid))
    update_source_audit(store)
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    foreign=db.execute('PRAGMA foreign_key_check').fetchall()
    raw_errors=[]
    for path,digest in db.execute("SELECT DISTINCT raw_path,raw_sha256 FROM observations WHERE raw_path != ''"):
        target=store.root/path
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raw_errors.append(path)
    dangling=[]
    for kind,left,right in db.execute('SELECT entity_type,left_id,right_id FROM duplicate_candidates'):
        table='statements' if kind=='statement' else 'quotes'
        if db.execute(f'SELECT count(*) FROM {table} WHERE id IN (?,?)',(left,right)).fetchone()[0]!=2:dangling.append([kind,left,right])
    invalid_language=db.execute('''SELECT l.id FROM language_links l JOIN quotes a ON a.id=l.quote_a JOIN quotes b ON b.id=l.quote_b
        WHERE a.statement_id != b.statement_id OR a.statement_id != l.statement_id OR a.published_language=b.published_language''').fetchall()
    counts={name:db.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in
            ('sources','documents','statements','quotes','statement_sources','language_links','duplicate_candidates','collection_runs')}
    missing={name:db.execute(f'SELECT count(*) FROM statements WHERE {name} IS NULL').fetchone()[0] for name in
             ('spoken_date','published_date','speaker_name','original_language')}
    coverage=[]
    for year in range(2015,2027):
        for country in ('ROK','JPN'):
            for source_type in ('primary','secondary'):
                documents=db.execute('''SELECT count(DISTINCT d.id) FROM documents d JOIN sources src ON src.id=d.source
                  WHERE substr(coalesce(d.published_date,json_extract(d.metadata_json,'$.event_date')),1,4)=? AND d.source_type=? AND
                  (EXISTS(SELECT 1 FROM statement_sources ss JOIN statements s ON s.id=ss.statement_id WHERE ss.document_id=d.id AND s.country=?)
                   OR (NOT EXISTS(SELECT 1 FROM statement_sources ss WHERE ss.document_id=d.id) AND coalesce(json_extract(d.metadata_json,'$.country_scope'),src.country)=?))''',
                  (str(year),source_type,country,country)).fetchone()[0]
                statements=db.execute('''SELECT count(DISTINCT s.id) FROM statements s JOIN statement_sources ss ON ss.statement_id=s.id
                  JOIN documents d ON d.id=ss.document_id WHERE substr(coalesce(s.spoken_date,s.published_date),1,4)=?
                  AND s.country=? AND d.source_type=?''',(str(year),country,source_type)).fetchone()[0]
                coverage.append(dict(year=year,country=country,source_type=source_type,documents=documents,unique_statements=statements))
    result={'checked_at':now(),'schema_version':db.execute('PRAGMA user_version').fetchone()[0],
            'sqlite_integrity':integrity,'foreign_key_errors':foreign,'raw_hash_errors':raw_errors,
            'dangling_duplicate_candidates':dangling,'invalid_language_links':invalid_language,
            'counts':counts,'missing_statement_fields':missing,'coverage':coverage,
            'verified_statements':db.execute("SELECT count(*) FROM statements WHERE verification_status='verified'").fetchone()[0],
            'pilot_target':{'minimum':100,'maximum':200,'reached':100<=counts['statements']<=200},
            'two_country_statements_present':db.execute('SELECT count(DISTINCT country) FROM statements').fetchone()[0]==2}
    audit_section=''
    if db.execute('SELECT 1 FROM audit_samples LIMIT 1').fetchone():
        from .audit_outputs import report_section
        audit_section,audit_stats=report_section(store)
        result['offline_audit']=audit_stats
    (store.root/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Качество, дедупликация и покрытие DRI','',f'Сформировано: {result["checked_at"]}. Основная БД: `data/dri.sqlite3`.',
           '',f'Документы: **{counts["documents"]}**; уникальные записи заявлений: **{counts["statements"]}**; цитаты: **{counts["quotes"]}**.',
           f'Ручную проверку прошли: **{result["verified_statements"]}**. Цель 100–200: **{"достигнута по числу записей" if result["pilot_target"]["reached"] else "не достигнута"}**.',
           'Пилот не является полным историческим корпусом. Нули означают отсутствие собранных записей, а не отсутствие дипломатических событий.',
           '',f'Целостность SQLite: `{integrity}`; ошибок внешних ключей: {len(foreign)}; ошибок raw-хэшей: {len(raw_errors)}.',
           f'Отсутствует дата выступления: {missing["spoken_date"]}; дата публикации: {missing["published_date"]}; личное имя: {missing["speaker_name"]}; язык оригинала: {missing["original_language"]}.',
           'Неизвестные поля оставлены NULL. Дата публикации не объявляется датой выступления. Должность — наблюдаемая на дату источника, без подстановки по имени.',
           '', '## Покрытие по годам, государствам и типам источников','',
           'В ячейке **документы / уникальные заявления**. Год документа — публикация, а при её отсутствии — явно известная дата события; год заявления — произнесение, при неизвестной дате — публикация (поля остаются раздельными).',
           'Страна документа определяется по связанному заявлению, а без атрибуции — по явно указанной области country_scope или стране издателя; это не доказательство выступления политика этой страны.',
           'Одно заявление с первичными и вторичными источниками входит в оба столбца: их суммы нельзя считать общим числом событий.',
           '', '| Год | ROK первичные | ROK вторичные | JPN первичные | JPN вторичные |','|---|---:|---:|---:|---:|']
    for year in range(2015,2027):
        cells=[]
        for country in ('ROK','JPN'):
            for stype in ('primary','secondary'):
                row=next(r for r in coverage if (r['year'],r['country'],r['source_type'])==(year,country,stype))
                cells.append(f"{row['documents']} / {row['unique_statements']}")
        lines.append(f'| {year} | '+' | '.join(cells)+' |')
    lines+=['','## Источники и языки документов','','| Источник | Тип | Язык публикации | Документы |','|---|---|---|---:|']
    for source,stype,lang,n in db.execute('SELECT source,source_type,language,count(*) FROM documents GROUP BY source,source_type,language ORDER BY source,language'):
        lines.append(f'| {source} | {stype} | {lang} | {n} |')
    lines+=['','## Темы и статус заявлений','','| Тема | Статус | Число |','|---|---|---:|']
    theme_rows=db.execute('SELECT theme,verification_status,count(*) FROM statements GROUP BY theme,verification_status').fetchall()
    theme_names=['historical_disputes','territorial_disputes','trade_economy','diplomatic_contacts','security','regional_cooperation','normalization_deescalation','unclassified']
    for theme in theme_names:
        found=[r for r in theme_rows if r[0]==theme]
        for name,status,n in found or [(theme,'not_collected',0)]:
            lines.append(f'| {name} | {status} | {n} |')
    lines+=['', 'Тематические метки получены по явным словам в заголовке/сохранённом фрагменте, это предварительная разметка. '
            'Отдельная нормализация/деэскалация остаётся пробелом этой выборки: две узкие проверки Kokkai не дали новых подходящих реплик после фильтрации. '
            'Нулевое число не означает отсутствие таких заявлений в истории.']
    lines+=['','## Запуски','','| Запуск | Статус | Обнаружено | Обработано | Документов добавлено | Заявлений добавлено | Дубли | Возможные совпадения | Ошибки доступа | Прочие ошибки |',
            '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for key,status,counters in db.execute('SELECT run_key,status,counters_json FROM collection_runs ORDER BY id'):
        c=json.loads(counters)
        lines.append('| '+key+' | '+status+' | '+' | '.join(str(c.get(k,0)) for k in ('documents_discovered','documents_processed','documents_added','statements_added','duplicates_rejected','possible_matches','access_errors','other_errors'))+' |')
    lines+=['','## Правила интерпретации','',
      '- Документ — публикация; заявление — отдельный подтверждаемый эпизод выступления/институционального комментария; цитата — дословный сохранённый фрагмент опубликованной версии.',
      '- Новая публикация об известном заявлении добавляется в statement_sources, а не создаёт новый сигнал, если идентичность выступления подтверждена явным event_key.',
      '- Сходство и даже точный текст в другую дату/другом выступлении дают possible_duplicate, сохраняя обе записи. Межъязыковое объединение только по явным доказательствам общего выступления; официальный перевод связывается отдельно.',
      '- Институциональные комментарии МИД допустимы с NULL личным именем; они остаются needs_review. Журналистский пересказ сам по себе не превращается в прямую цитату политика.',
      '- Надёжность источника — описательная категория из config/sources.json. Весов, индексов, вероятностей и LLM нет.',
      '- Два исходных полных текста оставлены без изменения как legacy_unreviewed. Новые тексты СМИ не сохраняются; для новых корейских документов оставлены только короткие исследовательские фрагменты. Число 25 слов не является универсальным юридическим разрешением.',
      '', 'Результаты автотестов: `docs/TEST_RESULTS.txt`. Таблица ручной проверки: `docs/REVIEW_TABLE.html`.']
    (ROOT/'docs/QUALITY_REPORT.md').write_text('\n'.join(lines)+'\n'+audit_section,encoding='utf-8')
    _review(store)
    media=db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',('media-bibliography-2026-10-30-validated',)).fetchone()
    if media:
        from .media_outputs import update_reports
        media_result=json.loads(media[0])
        update_reports(store,json.loads((ROOT/'data/media_manifest.json').read_text(encoding='utf-8')),media_result)
        result['media_pilot']=media_result
    from .expansion_outputs import update
    expansion=update(store)
    if expansion:result['expansion']=expansion
    return result

def _review(store):
    db=store.db
    if db.execute('SELECT 1 FROM audit_samples LIMIT 1').fetchone():
        from .audit_outputs import render_review
        if render_review(store):return
    headers=['ID','Направление','Дата выступления','Дата публикации','Имя','Должность','Орган','Адресат','Тема','Оригинальный язык','Статус','Атрибуция','Третья страна','Контекст / событие','Фрагменты опубликованных версий','Источники','Возможные дубли']
    output=['<!doctype html><html lang="ru"><meta charset="utf-8"><title>DRI — ручная проверка заявлений</title>',
      '<style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #ccd;padding:8px;vertical-align:top;min-width:120px}th{position:sticky;top:0;background:#eef}caption{text-align:left;padding:12px}td:nth-child(15){min-width:340px;white-space:pre-wrap}</style>',
      '<h1>DRI: уникальные записи заявлений для ручной проверки</h1><p>NULL/неизвестно не заменены догадками. needs_review не означает проверенную атрибуцию. Тексты — фрагменты источников, переводы помечены; индексы не рассчитаны.</p><table><thead><tr>',
      ''.join('<th>'+escape(h)+'</th>' for h in headers),'</tr></thead><tbody>']
    db.row_factory=None
    for row in db.execute('''SELECT id,country,target_country,spoken_date,published_date,speaker_name,speaker_office,institution,
           addressee,theme,original_language,verification_status,attribution_confidence,third_country_context,context FROM statements ORDER BY coalesce(spoken_date,published_date),id''').fetchall():
        sid=row[0]
        quotes=['['+lang+'; '+kind+'] '+text for lang,kind,text in db.execute('SELECT published_language,version_kind,text FROM quotes WHERE statement_id=?',(sid,))]
        from .publication import internal_statement,WITHHELD
        if internal_statement(db,sid):quotes=[WITHHELD]
        sources=[f'<a href="{escape(url,quote=True)}">{escape(source)}</a> ({escape(stype)})' for source,url,stype in db.execute('SELECT d.source,d.url,d.source_type FROM statement_sources ss JOIN documents d ON d.id=ss.document_id WHERE ss.statement_id=?',(sid,))]
        dup=[str(b if a==sid else a) for a,b in db.execute("SELECT left_id,right_id FROM duplicate_candidates WHERE entity_type='statement' AND (left_id=? OR right_id=?)",(sid,sid))]
        values=[sid,row[1]+' → '+row[2],*row[3:13],bool(row[13]),row[14]]
        output.append('<tr>'+''.join('<td>'+escape(str(v) if v is not None else 'неизвестно')+'</td>' for v in values)+
                      '<td>'+escape('\n'.join(quotes))+'</td><td>'+'<br>'.join(sources)+'</td><td>'+escape(', '.join(dup))+'</td></tr>')
    output.append('</tbody></table></html>')
    (ROOT/'docs/REVIEW_TABLE.html').write_text(''.join(output),encoding='utf-8')
