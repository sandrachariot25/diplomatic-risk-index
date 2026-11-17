"""Update existing quality report and review table; no parallel report copies."""
import json
from collections import Counter
from html import escape
from .paths import ROOT,write_generated
from .corpus_audit import SAMPLE,summary

LABELS={'direct_address':'Прямое требование/протест другой стороне','official_bilateral':'Официальная двусторонняя коммуникация без установленного прямого обращения',
 'domestic_bilateral':'Внутриполитическая речь о двусторонних отношениях','regional_security':'Региональная безопасность и явная координация сторон',
 'regional_cooperation':'Региональное сотрудничество вне доказанной военной тематики','third_country_only':'В сохранённом фрагменте — третьи страны без явной двусторонней связи',
 'incidental_reference':'Случайное упоминание / сравнение, связь с политикой не показана','indeterminate':'Контекста недостаточно'}

def report_section(store):
    db=store.db;stats=summary(db)
    total=db.execute('SELECT count(*) FROM statements').fetchone()[0]
    party=stats['established_party_status']
    lines=['','## Офлайн-аудит: стратифицированная выборка 50','',
     'Этот раздел описывает прежний офлайн-аудит исходных 173 документов и 163 заявлений; новые библиографические записи СМИ в него не входят. '
     'Институциональные признаки описательные: значимость парламентской, партийной или внешнеполитической риторики не ранжируется.',
     '', '**Ключевое ограничение прежнего сбора:** 73 японские записи — выступления представителей исполнительной власти на парламентской площадке. '
     'Это не выборка независимых депутатских, партийных или оппозиционных речей. Фильтр `speakerPosition=大臣` включал также чиновников `大臣官房`. '
     'Орган выступающего и место выступления теперь разделены. В будущем фильтр должности необязателен; текущий корпус этим не расширялся.',
     '', 'Выборка: **50** записей, **25 ROK + 25 JPN**. Сначала взята одна запись из каждой пары год–страна (24 страты), '
     'затем добраны редкие темы, типы институтов и роли при сохранении баланса стран. Порядок воспроизводим по отпечатку event_key/ID. '
     'Это целевая стратифицированная проверка, не случайная репрезентативная оценка частоты ошибок в генеральной совокупности.',
     'При неизвестной дате речи год страты определяется по публикации; дата речи остаётся NULL. '
     'Все 50 заявлений имеют первичные источники: в пяти записях СМИ нет выделенных заявлений, поэтому вторичная страта заявлений отсутствует.',
     '', 'Оценены только сохранённые фрагменты и контекст записи. 50 заметок — разбор агентом, **не независимая человеческая верификация и не сверка полного оригинала**. '
     'Остальные 113 оценены консервативными правилами с тем же ограничением. Исходный verification_status не повышен.',
     '', '| Год | В выборке ROK | В выборке JPN |','|---|---:|---:|']
    for year in range(2015,2027):
        values=[db.execute('''SELECT count(*) FROM audit_samples a JOIN statements s ON s.id=a.statement_id
          WHERE a.sample_key=? AND substr(coalesce(s.spoken_date,s.published_date),1,4)=? AND s.country=?''',(SAMPLE,str(year),country)).fetchone()[0] for country in ('ROK','JPN')]
        lines.append(f'| {year} | {values[0]} | {values[1]} |')
    lines+=['','### Релевантность: оценка фрагмента, не исключение записи','',
      'Адресат/направление в исходной базе — прежняя аннотация. Категории ниже не доказывают, что каждое упоминание Кореи было адресованным ей политическим сигналом. '
      'Парламентский контекст не является основанием считать запись нерелевантной. Даже incidental_reference и third_country_only сохранены, не исключены из будущей проверки.',
      '', '| Категория | В выборке 50 | Во всём корпусе 163 |','|---|---:|---:|']
    for category,label in LABELS.items():lines.append(f'| {label} (`{category}`) | {stats["sample_relevance"].get(category,0)} | {stats["corpus_relevance"].get(category,0)} |')
    lines+=['','Примеры проблем: ID 62 называет бейсбольные команды; ID 70 обсуждает неизвестные выступающему корейские guidelines; '
      'ID 42 в сохранённой части отвечает о Северных территориях, хотя Корея есть в перечне вопросов. '
      'ID 136 обрывается на expresses, ID 125 — на that the; политическая позиция не восстанавливалась по догадке. '
      'ID 154/74 требуют уточнения темы от security к территориальному спору; ID 47 использует название соглашения с economic, но обсуждает исторические претензии. '
      'Предложения исправлений хранятся отдельно, прежние темы/цитаты не перезаписаны.',
      '', '### Представленность институтов: автор позиции и площадка','',
     '| Тип | Заявления по органу выступающего | Заявления на такой площадке | Документы по органу |','|---|---:|---:|---:|']
    for kind in ('parliament','foreign_ministry','government','head_of_state_administration','political_party','other','unknown'):
        docs=db.execute('''SELECT count(DISTINCT ss.document_id) FROM statement_sources ss JOIN statement_metadata m ON m.statement_id=ss.statement_id WHERE m.institution_type=?''',(kind,)).fetchone()[0]
        if kind=='foreign_ministry':
            docs+=db.execute("SELECT count(*) FROM documents d WHERE d.source IN ('mofa_kr','mofa_jp') AND NOT EXISTS(SELECT 1 FROM statement_sources ss WHERE ss.document_id=d.id)").fetchone()[0]
        elif kind=='unknown':
            docs+=db.execute("SELECT count(*) FROM documents d WHERE d.source NOT IN ('mofa_kr','mofa_jp') AND NOT EXISTS(SELECT 1 FROM statement_sources ss WHERE ss.document_id=d.id)").fetchone()[0]
        lines.append(f'| {kind} | {stats["institution_counts"].get(kind,0)} | {stats["venue_counts"].get(kind,0)} | {docs} |')
    lines+=['', 'Площадка неизвестна для 90 официальных публикаций МИД; не подставлена «пресс-конференция». '
      'Ноль parliament в столбце автора означает пробел текущей выборки рядовых депутатов/комитетских представителей, а не низкую важность парламента. '
      'Две речи в разных палатах одного премьера не превращают его в двух разных политических акторов. '
      'Пять несвязанных публикаций МИД учтены по издателю; пять библиографических записей СМИ — unknown по органу автора позиции. '
      'Если один документ в будущем содержит несколько выступающих из разных институтов, он может входить более чем в одну группу документов.',
      '', '| Категория выступающего | Заявления |','|---|---:|']
    for kind,n in sorted(stats['speaker_categories'].items()):lines.append(f'| {kind} | {n} |')
    lines+=['','### Даты, имена, политическая принадлежность и направленность','',
      f'- Дата произнесения установлена у {stats["established_speech_dates"]}/{total} ({100*stats["established_speech_dates"]/total:.1f}%); публикация не заменяет её.',
      f'- Личное имя установлено у {stats["established_names"]}/{total} ({100*stats["established_names"]/total:.1f}%). Безымянные институциональные заявления сохранены.',
      f'- Статус правящая партия/оппозиция на дату речи: {party}/{total}. Нельзя выводить его из имени политика, министерской должности или нынешнего состава правительства.',
      '- В прежних 163 записях партийная принадлежность не была установлена: старое speakerGroup не сохранялось. Новые записи NDL сохраняют сообщённую парламентскую группу на дату речи; это не подстановка статуса власти/оппозиции и не переаудит старых записей.',
      '- Проверенная тональность: positive 0, negative 0, neutral 0; unknown 163. Unknown не означает нейтральность. Явные слова protest/congratulates сами по себе не являются проверенной оценкой всей речи.',
      '', '### Завершённая проверка исходных 164 предполагаемых совпадений (не повторялась)','',
      'Это **82 пары заявлений + 82 пары цитат**, не 164 дополнительных заявления. Проверены идентификаторы, даты, контекст, язык, буквальное совпадение и связи источников. '
      'Все исходные пары сохраняют статус possible_duplicate; слияний и удалений нет.',
      '', '| Структурный результат | Пары |','|---|---:|']
    for kind,n in stats['duplicate_review_counts'].items():lines.append(f'| {kind} | {n} |')
    lines+=['', '162 пары относятся к разным публикациям, но дата произнесения неизвестна: нельзя объявлять их ни доказанным повтором одной речи, ни доказанными разными речами только по дате публикации. '
      'Две пары — заявления/цитаты ID 162 и 163: одинаковый фрагмент речи премьера в разных палатах 2024-10-04, разные speechID и контексты; сохраняются отдельно.',
      'Подтверждённые перепечатки одной цитаты несколькими СМИ, повтор одного speechID и официально связанные языковые версии среди этих пар не обнаружены. '
      'Это ограничение имеющихся связей и фрагментов: по одной короткой цитате нельзя доказать, что переводов или перепечаток нигде нет.',
      '', '### Готовность к будущей проверке последовательности сигналов','',
      'Представление `signal_timeline` хранит раздельно statement_date, published_date, first_observed_by_collector_at, '
      'тип органа, площадку, роль, принадлежность/статус на дату, контекст, scope позиции и результаты аудита. '
      'Пока только подготовлены поля: временные лаги, прогнозная значимость, причинность и индекс не рассчитывались.',
      'Парламентская риторика не получает меньший вес. Но текущий отбор исполнительных выступающих, отсутствие независимых депутатов/партийных речей, '
      'неизвестные даты 90 высказываний, неизвестная партийность, короткие незавершённые цитаты, смещение японской годовой выборки к концу года '
      'и нерешённые возможные дубли мешают проверке гипотезы. Нужны как эпизоды обострения, так и контрольные периоды без него; текущая выборка их не устанавливает.',
      'Недостаточно представлены 2015 год РОК (4 записи) и отдельные годы с 5–6 записями; формального баланса достаточно для аудита, недостаточно для ряда ежедневной риторики. '
      'Отсутствие записей не означает отсутствие дипломатической активности.',
      '163 — технически уникальные записи по идентификаторам, а не доказанные 163 независимых дипломатических сигнала. '
      'Окончательная канонизация выступлений и оценка соответствия адресату остаются предметом проверки.',
      '', f'Оригинальные доменные записи сохранены: `{stats["core_records_preserved"]}`. Независимой ручной верификации требуют **{stats["requires_human_verification"]}** записей; '
      'проверка 50 фрагментов не переводит их автоматически в verified. Все 164 пары доступны в основной таблице проверки.']
    return '\n'.join(lines)+'\n',stats

def render_review(store):
    db=store.db
    ids=[r[0] for r in db.execute('SELECT statement_id FROM audit_samples WHERE sample_key=? ORDER BY sampling_rank',(SAMPLE,))]
    if not ids:return False
    headers=['ID','Страна → тема-адресат','Дата речи','Дата публикации','Имя','Роль на дату','Орган автора','Площадка',
     'Партийная принадлежность','Власть/оппозиция на дату','Тип контекста / scope','Адресат из исходной записи','Тема / предложение уточнения',
     'Цитата, язык оригинала / публикации','Источники и URL / тип','Верификация','Категория релевантности','Обоснование / качество фрагмента','Контекст / событие','Возможные дубли']
    def cell(v):return escape(str(v) if v is not None else 'не установлено')
    output=['<!doctype html><html lang="ru"><meta charset="utf-8"><title>DRI — аудит 50 заявлений</title>',
     '<style>body{font:14px system-ui;margin:24px;color:#182b39}table{border-collapse:collapse}td,th{border:1px solid #bbc8d2;padding:8px;vertical-align:top;min-width:115px}th{position:sticky;top:0;background:#e9eff5}td.quote,td.reason{min-width:320px;white-space:pre-wrap}.scroll{overflow:auto;max-height:78vh;border:1px solid #bbc8d2}summary{cursor:pointer;margin:20px 0}p{max-width:1100px}</style>',
     '<h1>DRI: стратифицированная проверка 50 заявлений</h1><p>25 РОК + 25 Япония, все годы 2015–2026. Только сохранённые фрагменты и контекст; '
     'это разбор агентом, не независимая человеческая верификация полного источника. Неизвестные даты, партийность и статус не восстановлены догадками. '
     'Парламентская площадка отделена от органа выступающего; весов нет. Библиография СМИ не содержит выделенных заявлений и не входит в выборку.</p>',
     '<p><a href="#rest">Остальные заявления</a> · <a href="#pairs">Исходные 164 пары и новые кандидаты</a></p>']
    def table(statement_ids,label):
        result=['<h2>'+escape(label)+'</h2><div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>']
        for sid in statement_ids:
            cur=db.execute('''SELECT s.id,s.country,s.target_country,s.spoken_date,s.published_date,s.speaker_name,
               m.speaker_role,m.institution_type,m.venue_institution_type,m.political_affiliation,m.government_opposition_status,
               m.statement_context,m.position_scope,s.addressee,s.theme,a.theme_suggestion,s.original_language,
               s.verification_status,a.assessment_status,a.relevance_category,a.reason,a.excerpt_quality,s.context
               FROM statements s JOIN statement_metadata m ON m.statement_id=s.id LEFT JOIN statement_assessments a ON a.statement_id=s.id WHERE s.id=?''',(sid,))
            row=cur.fetchone()
            quote='\n'.join('['+lang+'; '+kind+'] '+text for text,lang,kind in db.execute('SELECT text,published_language,version_kind FROM quotes WHERE statement_id=? ORDER BY id',(sid,)))
            from .publication import internal_statement,WITHHELD
            if internal_statement(db,sid):quote=WITHHELD
            sources='<br>'.join('<a href="'+escape(url,quote=True)+'">'+cell(src)+'</a> / '+cell(kind) for src,url,kind in db.execute(
             'SELECT d.source,d.url,d.source_type FROM statement_sources ss JOIN documents d ON d.id=ss.document_id WHERE ss.statement_id=?',(sid,)))
            dups=[str(b if a==sid else a) for a,b in db.execute("SELECT left_id,right_id FROM duplicate_candidates WHERE entity_type='statement' AND (left_id=? OR right_id=?)",(sid,sid))]
            values=[row[0],row[1]+' → '+row[2],*row[3:11],str(row[11])+' / '+str(row[12]),row[13],row[14]+(' → '+row[15]+' (предложение, не замена)' if row[15] else ''),
                    quote+'\nОригинальный язык: '+(row[16] or 'не установлен'),sources,row[17]+' / '+(row[18] or 'not_assessed'),LABELS.get(row[19],LABELS['indeterminate']),(row[20] or 'Новая запись, прежний аудит не повторялся')+'\nФрагмент: '+(row[21] or 'needs_context'),row[22],', '.join(dups)]
            result.append('<tr id="statement-'+str(sid)+'">'+''.join('<td'+(' class="quote"' if i==13 else ' class="reason"' if i==17 else '')+'>'+(str(v) if i==14 else cell(v))+'</td>' for i,v in enumerate(values))+'</tr>')
        result.append('</tbody></table></div>');return ''.join(result)
    output.append('<section id="sample" data-sample-size="50">'+table(ids,'Основная выборка 50')+'</section>')
    rest=[r[0] for r in db.execute('SELECT id FROM statements ORDER BY coalesce(spoken_date,published_date),id') if r[0] not in set(ids)]
    output.append('<details id="rest"><summary>Остальные '+str(len(rest))+' записей — сохранены</summary>'+table(rest,'Полный остаток корпуса')+'</details>')
    output.append('<details id="pairs"><summary>Предполагаемые совпадения: исходные 164 и новые; ничего не объединено</summary><div class="scroll"><table><tr><th>ID</th><th>Сущность</th><th>Пара ID</th><th>Статус</th><th>Структурная проверка</th><th>Доказательства и ограничения</th></tr>')
    for cid,kind,a,b,status,classification,evidence in db.execute('''SELECT c.id,c.entity_type,c.left_id,c.right_id,c.status,r.classification,r.evidence_json
      FROM duplicate_candidates c LEFT JOIN duplicate_reviews r ON r.candidate_id=c.id ORDER BY c.id'''):
        output.append('<tr>'+''.join('<td>'+cell(v)+'</td>' for v in (cid,kind,f'{a} / {b}',status,classification,evidence))+'</tr>')
    output.append('</table></div></details></html>')
    write_generated(ROOT/'docs/REVIEW_TABLE.html',''.join(output))
    return True
