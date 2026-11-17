"""Composition and text completeness, kept separate from speech/event quality."""
import json
import re
from collections import Counter
from html import escape
from .paths import ROOT,write_generated
from .expansion import PREFIX,counts

START='<!-- EXPANSION_START -->';END='<!-- EXPANSION_END -->'
def replace_section(path,body):
    old=path.read_text(encoding='utf-8')
    if START in old:
        first,tail=old.split(START,1);_,last=tail.split(END,1);old=first+last
    write_generated(path,old.rstrip()+'\n\n'+START+'\n'+body+'\n'+END+'\n')

def update(store):
    db=store.db
    saved=db.execute('SELECT config_json FROM collection_runs WHERE run_key=?',(PREFIX+'-baseline',)).fetchone()
    if not saved:return
    baseline=json.loads(saved[0]);after=counts(db)
    docs=[]
    for did,source,policy,text,metadata in db.execute('SELECT id,source,content_policy,text,metadata_json FROM documents WHERE id>? ORDER BY id',(baseline['last_document_id'],)):
        m=json.loads(metadata);docs.append(dict(id=did,source=source,policy=policy,text=text,metadata=m))
    full=[d for d in docs if d['metadata'].get('text_completeness') in {'complete_published_body','complete_extracted_body_without_page_headers'}]
    excerpts=[d for d in docs if d['text'] and d not in full]
    metadata_only=[d for d in docs if not d['text']]
    confirmed_quotes=db.execute("SELECT count(*) FROM quotes WHERE id>? AND verification_status IN ('verified','source_text_verified')",(baseline['last_quote_id'],)).fetchone()[0]
    witnesses=db.execute("SELECT count(*) FROM statement_metadata WHERE statement_id>? AND speaker_category='nonpolitical_witness'",(baseline['last_statement_id'],)).fetchone()[0]
    checkpoints=[json.loads(r[0]) for r in db.execute('SELECT config_json FROM collection_runs WHERE run_key LIKE ?',(PREFIX+'-queue-%-checkpoint',))]
    delta={k:after[k]-baseline['counts'][k] for k in after}
    gdelt={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() else 0 for t in ('gdelt_events','gdelt_mentions','gdelt_gkg')}
    stats=dict(baseline=baseline['counts'],after=after,delta=delta,new_full_text_documents=len(full),
        report_date='2026-11-01',data_cutoff='2026-10-31',
        new_restricted_excerpt_documents=len(excerpts),new_confirmed_quotes=confirmed_quotes,
        new_quotes_total=delta['quotes'],new_unique_statement_records=delta['statements'],
        new_political_statement_candidates=delta['statements']-witnesses,new_nonpolitical_witness_records=witnesses,
        new_gdelt_events=gdelt['gdelt_events'],new_media_mentions=gdelt['gdelt_mentions'],new_gkg_records=gdelt['gdelt_gkg'],new_metadata_only_documents=len(metadata_only),
        text_frequency_candidates=sum(d['metadata'].get('observation_type')!='parliamentary_minutes' for d in full),verified_rhetoric_frequency_observations=0,goal=2000,
        goal_reached=False,batch_checkpoints=len(checkpoints),
        discovery_states=dict(db.execute('SELECT status,count(*) FROM discovery_results GROUP BY status')))
    lines=['## Расширение к контрольной отметке 2 000: состав и полнота текста','',
      'Единица ниже — уникальный документ источника. Полный текст отчёта о встрече пригоден как кандидат для частот слов/тем публикаций, '
      'но не становится политическим заявлением, событием или независимым дипломатическим сигналом. '
      'Репрезентативность и корректность направления требуют проверки; полноценный частотный анализ политической риторики пока не обеспечен.',
      '', '| Показатель | До этапа | После | Прирост |','|---|---:|---:|---:|']
    for key in after:lines.append(f"| {key} | {baseline['counts'][key]} | {after[key]} | {delta[key]} |")
    lines+=['','| Раздельный результат | Новых |','|---|---:|',
      f'| Полные опубликованные тексты | {len(full)} |',f'| Ограниченные фрагменты документов | {len(excerpts)} |',
      f'| Дословные цитаты, подтверждённые по источнику (source_text_verified/verified) | {confirmed_quotes} |',f"| Все новые записи цитат (включая needs_review) | {delta['quotes']} |",
      f"| Новые технически уникальные записи заявлений | {delta['statements']} |",f"| Машинные записи Events GDELT | {gdelt['gdelt_events']} |",f"| Медийные упоминания GDELT Mentions | {gdelt['gdelt_mentions']} |",f"| GKG совместные упоминания стран | {gdelt['gdelt_gkg']} |",
      f'| Только метаданные | {len(metadata_only)} |',f'| Кандидаты для частот текста документов, не частот высказываний | {len(full)} |',
      f"| Из записей заявлений: политические кандидаты, ещё needs_review | {delta['statements']-witnesses} |",
      f'| Из записей заявлений: явно неполитические эксперты, исключены из политических частот | {witnesses} |',
      '| Проверенные новые наблюдения для частот политической риторики | 0 |','',
      'Цель 2 000 не достигнута. Простые URL, discovery_results, библиография, фрагменты и GDELT не добавляются к количеству полных текстов. '
      'В этот показатель не включены старые legacy-тексты с нерешёнными правами и прежние короткие выдержки. '
      'Слова cooperation/protest и тема не заменяют верифицированную тональность; тональность не кодировалась.',
      'source_text_verified подтверждает буквальное соответствие цитаты API и его атрибуции; статус заявления остаётся needs_review. '
      'Это не независимая проверка политического смысла, направленности и полноты выступления.',
      'Контейнеры цитат уже входят в число фрагментных документов; документы, связанные заявления и цитаты — пересекающиеся сущности. '
      'Их нельзя складывать как независимые наблюдения. Неполитические эксперты сохранены с отдельной категорией, не удалены и не приписаны правительству.',
      '', '### Новые документы: каждый год, государство издателя и тип источника','',
      '| Год | РК primary: полные / фрагменты / metadata | РК secondary | Япония primary | Япония secondary | GDELT events / mentions / GKG |',
      '|---|---:|---:|---:|---:|---:|']
    for year in range(2015,2027):
        cells=[]
        for country,stype in [('ROK','primary'),('ROK','secondary'),('JPN','primary'),('JPN','secondary')]:
            selected=[d for d in docs if d['metadata'].get('country_scope')==country and d['metadata'].get('source_type')==stype and (d['metadata'].get('published_date') or d['metadata'].get('event_date') or '').startswith(str(year))]
            cells.append(' / '.join(str(n) for n in (sum(d in full for d in selected),sum(d in excerpts for d in selected),sum(d in metadata_only for d in selected))))
        gd=[]
        for table,col in [('gdelt_events','event_date'),('gdelt_mentions','mention_observed_at'),('gdelt_gkg','observed_at')]:
            gd.append(db.execute(f'SELECT count(*) FROM {table} WHERE substr({col},1,4)=?',(str(year),)).fetchone()[0] if gdelt[table] else 0)
        lines.append(f'| {year} | '+' | '.join(cells)+' | '+' / '.join(map(str,gd))+' |')
    lines+=['','GDELT учитывается по году события (Events) и по времени регистрации (Mentions/GKG); дата регистрации не объявляется датой публикации. '
      'Коды KOR/JPN — атрибуты акторов машинного извлечения; PRK исключён. В GKG KS/JA — географические совместные упоминания, не направленное взаимодействие. '
      'Несколько GlobalEventID могут описывать один реальный эпизод: автоматического объединения или объявления независимости не было.',
      '', '| Год | Actor1 → Actor2 | Events | Mentions связанных событий |','|---|---|---:|---:|']
    for year in range(2015,2027):
        for a,b in [('ROK','JPN'),('JPN','ROK')]:
            e=db.execute('SELECT count(*) FROM gdelt_events WHERE substr(event_date,1,4)=? AND actor1_country=? AND actor2_country=?',(str(year),a,b)).fetchone()[0] if gdelt['gdelt_events'] else 0
            m=db.execute('SELECT count(*) FROM gdelt_mentions m JOIN gdelt_events e ON e.event_id=m.event_id WHERE substr(m.mention_observed_at,1,4)=? AND e.actor1_country=? AND e.actor2_country=?',(str(year),a,b)).fetchone()[0] if gdelt['gdelt_mentions'] else 0
            lines.append(f'| {year} | {a} → {b} | {e} | {m} |')
    lines+=['','### Направления и тематика','',
      'Страна издателя РК и Japan как тема не доказывают, что все слова принадлежат корейскому политику или обращены непосредственно Японии. '
      'Актор/адресат для новых отчётов не домысливаются; гражданство участников из имени не выводится. '
      'Отбор требует явной РК и Японии; КНДР сама по себе не удовлетворяет фильтру.',
      '', '| Тема по текстовым признакам, не проверенная тональность | Документы |','|---|---:|']
    for theme,n in Counter(d['metadata'].get('theme') or 'unclassified' for d in docs).most_common():lines.append(f'| {theme} | {n} |')
    lines+=['','### Заполненность исходных полей новых документов','',
      '| Поле | Не установлено |','|---|---:|']
    for field in ('published_date','event_date','author','institution','observation_addressee','language','rights_evidence'):
        lines.append(f"| {field} | {sum(not d['metadata'].get(field) for d in docs)} |")
    lines+=['','NULL даты события не заменяется датой публикации. Персональный автор пресс-релиза и участники не восстанавливаются по должности. '
      'Для документов МИД установлен издатель/институт; личные участники остаются в исходном тексте до отдельной атрибуции. '
      'Англоязычные материалы МИД являются опубликованной институциональной версией, а не доказательством языка произнесённой речи.']
    lines+=['','### Контрольные точки','',
      'У каждой партии свой collection_run и список discovery ID. Обработанные URL проверяются по document_aliases до сети; '
      'повторное ingestion выполняется в памяти с тем же исходным текстом и хэшем, без повторной загрузки. '
      'Исключения за периодом/темой и сетевые отказы сохранены в discovery_results и collection_items; ошибки — в errors. '
      'Автоматического повторения отказов нет. После прерывания продолжается зафиксированная партия.',
      '', '| Партия МИД РК | Новых документов | Проверен повтор | Пропуски технически обязательных полей этой партии |','|---|---:|---:|---:|']
    for c in checkpoints:lines.append(f"| {c['batch_run_id']} | {len(c['added_document_ids'])} | {len(c['repeat_verified_document_ids'])} | {c['mandatory_missing']} |")
    lines+=['','У новых японских цитат отдельно сохранены годовые страницы и nextRecordPosition в collection_runs. '
      'Финальная офлайн-проверка повторяет только документы текущего расширения со всеми связанными заявлениями и цитатами. '
      'Правило технической даты уточнено: достаточно документированной даты события ИЛИ публикации; дата публикации не домысливается. '
      'Распределения контрольной точки пересчитаны по её партии, чтобы параллельный писатель другого источника не попадал в её счётчики.',
      '', '### Подтверждённые ограничения текущего запуска','',
      '- В предшествующем запуске МИД РК и NDL были остановлены после тайм-аутов транспорта 180 с. Это не HTTP 403/429 и не доказательство отсутствия документов. Результаты продолжения 1 ноября приведены отдельно ниже.',
      '- Остались ранее обнаруженные URL и следующие страницы NDL. Принципиальная недостижимость 2 000 не доказана; текущий запуск остановлен с сохранёнными позициями, а число качественных наблюдений не дополнено искусственно.',
      '- Полные речи NDL не сохраняются; короткая цитата не заменяет полный контекст и не разрешает частоты слов всей речи. '
      'Полные тексты МИД пригодны лишь для частот этого документального подкорпуса после проверки релевантности; они не отражают частоту самостоятельных политических заявлений.',
      '- Исторические выборки не репрезентативны. Поисковая очередь МИД и порядок API создают смещения по годам; актуальный охват японских записей приведён в таблице по годам. '
      'Нулевые ячейки не означают отсутствие дипломатической активности.']
    replace_section(ROOT/'docs/QUALITY_REPORT.md','\n'.join(lines))
    audit=['## Расширение корпуса: новые подтверждения и ограничения','',
      'Прежние аудиты десяти СМИ, 50 заявлений и 164 пар не повторялись. Новые пробы касались права на собственные тексты МИД, '
      'архива стенограмм РК и документированных архивов GDELT.',
      '', '- [Политика МИД РК](https://www.mofa.go.kr/www/wpge/m_4190/contents.do) получена напрямую через клиент: '
      'для собственных произведений МИД по умолчанию действует KOGL Type 1; специальные условия материала имеют приоритет. '
      'Новый сбор сохраняет только собственную прозу пресс-релиза с указанием МИД, даты, заголовка и URL; вложения, фото и чужие материалы не включаются. '
      'Отдельные ограничения/сторонняя атрибуция оставляют материал фрагментом. Это условное правило, не разрешение на всё содержимое домена.',
      '- [Архив парламента РК](https://record.assembly.go.kr/assembly/mnts/minutes/search.do?schwrd=%EC%A7%80%EB%B0%A9) '
      'и реально обнаруженная страница [XML viewer 55170](https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id=55170&type=summary) '
      'доступны напрямую (web-инструмент давал ошибку). HTML сам по себе не подтвердил надёжную привязку всех реплик, '
      'полный экспорт и условия корпусного хранения. Массовый импорт стенограмм РК не включён; платные API/ключи не использовались.',
      '- [NDL API](https://kokkai.ndl.go.jp/api.html), раздел 4: права отдельных выступающих сохраняются; '
      'новый сбор допускает только полное короткое предложение до 90 символов, буквальное соответствие источнику и оригинальные speechID. '
      'Выборка с `any=日韓`, без фильтра министерской должности, включает разные роли; страницы по 20 API-записей сортируются по новой дате. '
      'Не каждый ответ содержит подходящую короткую цитату. Это не репрезентативная частота и не лицензия на полные речи.',
      '- [GDELT raw data](https://gdeltproject.org/data.html), [официальное описание файлов](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/), '
      '[Events/Mentions codebook](https://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf). '
      'Успешно проверены интервалы 2015-12-28 12:00, 2019-08-02 00:00, 2020-06-15 12:00, 2025-08-23 12:00 UTC. '
      'Они не покрывают все дни и годы. Отсутствие пары в одном файле не означает отсутствие событий за год. '
      'Оригинальные ZIP и хэши сохранены в существующем data/raw; статьи по SOURCEURL/MentionIdentifier не загружались.',
      '- GKG за 2015-12-28 12:00: первый запрос остановлен локальным пределом 4 МБ, не серверным запретом. '
      'Один повтор с отдельным пределом 16 МБ получил архив 7 049 874 байта. Общий лимит HTML остался 4 МБ; распаковка ограничена 64 МБ. '
      'Совместные географические упоминания KS/JA хранятся отдельно от событий KOR/JPN. Полные тексты СМИ из GKG не извлекаются.',
      '', 'Для раздельного GDELT-хранения выполнена аддитивная миграция 3→4. '
      'Резервная копия: `data/backups/pre-schema-004.sqlite3`; новые таблицы gdelt_events/gdelt_mentions/gdelt_gkg. '
      'Основная база прежняя; новая параллельная рабочая база не создавалась. Статистика типов не суммируется в показатель качества.']
    replace_section(ROOT/'docs/SOURCE_AUDIT.md','\n'.join(audit))
    path=ROOT/'data/verification.json';v=json.loads(path.read_text(encoding='utf-8'));v['expansion']=stats
    write_generated(path,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
    path=ROOT/'docs/REVIEW_TABLE.html';html=path.read_text(encoding='utf-8')
    html=re.sub(r'<section id="expansion">.*?</section>','',html,flags=re.S)
    block=['<section id="expansion"><h2>Новые документы: полнота и права</h2><p>Это отчёты источника, не выделенные речи. Проверить участников, дату события, непосредственного адресата и пригодность частотного анализа.</p><table><tr><th>ID</th><th>Дата публикации / событие</th><th>Источник</th><th>Тип / полнота</th><th>Статус</th><th>Права</th></tr>']
    for d in docs:
        m=d['metadata'];block.append('<tr>'+''.join('<td>'+x+'</td>' for x in (str(d['id']),escape(str(m.get('published_date')))+' / '+escape(str(m.get('event_date'))),'<a href="'+escape(m['url'],quote=True)+'">'+escape(m['title'])+'</a>',escape(str(m.get('observation_type')))+' / '+escape(str(m.get('text_completeness'))),escape(str(m.get('analysis_status'))),escape(m.get('rights',''))))+'</tr>')
    block.append('</table></section>')
    write_generated(path,html.replace('</html>',''.join(block)+'</html>'))
    return stats
