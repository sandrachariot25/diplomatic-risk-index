"""Update canonical reports with explicitly limited media evidence."""
import json
from collections import Counter
from html import escape
from .paths import ROOT,write_generated

START='<!-- MEDIA_AUDIT_START -->';END='<!-- MEDIA_AUDIT_END -->'
def section(path,body):
    old=path.read_text(encoding='utf-8')
    if START in old:
        a,b=old.split(START,1);_,c=b.split(END,1);old=a+c
    write_generated(path,old.rstrip()+'\n\n'+START+'\n'+body+'\n'+END+'\n')

def update_reports(store,rows,result):
    from .identity import fingerprint
    if fingerprint(rows)!=result['manifest_sha256']:
        raise ValueError('Media manifest changed after recorded validation; refusing stale report')
    audits=json.loads((ROOT/'config/media_audit.json').read_text(encoding='utf-8'))
    sources={r['id']:r for r in json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))}
    n=Counter(r['source'] for r in rows)
    lines=['## СМИ: ограниченный аудит 2026-10-30','',
      'Это проверка осуществимости, а не завершённый аудит десятилетнего архива. Исходные десять изданий оставлены без замены. '
      'Ноль найденных статей при отказе инструмента не доказывает отсутствие публикаций. Нет подтверждённого открытого API новостных статей у этих десяти СМИ. '
      'Точные серверные лимиты не установлены; локальная пауза 5,5 с не объявляется лимитом издателя. RSS не является историческим архивом или лицензией на полный текст.',
      '', '| СМИ / страна издателя | Доступ / API, RSS, поиск | Историческое покрытие | Отобрано | Цитат сохранено | Новых заявлений | Ограничения / доказательства |',
      '|---|---|---|---:|---:|---:|---|']
    for a in audits:
        s=sources[a['id']]
        links='; '.join('[доказательство '+str(i+1)+']('+u+')' for i,u in enumerate(a['evidence']))
        lines.append(f"| {s['name']} / {s['country']} | {a['access']}. {a['channels']} | {a['history']} | {n[a['id']]} | 0 | 0 | {a['notes']} {links} |")
    lines+=['','### Поля и языковые версии','']
    for a in audits:
        lines.append('- **'+sources[a['id']]['name']+'**: '+a['languages']+'. '+a['notes'])
    lines+=['','### Проверенные запросы и происхождение','',
      '- `GET https://www.koreaherald.com/rss` → опубликованная ссылка `https://www.koreaherald.com/rss/newsAll`; XML прочитан web-инструментом. '
      '`GET https://world.kbs.co.kr/service/about_rss.htm?lang=e` → опубликованная ссылка `https://world.kbs.co.kr/rss/rss_news.htm?id=Po&lang=e`; лента прочитана web-инструментом.',
      '- `GET https://feed.koreatimes.co.kr/k/foreignaffairs.xml` → web-инструмент не смог получить ответ; endpoint не включён. '
      'Ссылка опубликована на официальной RSS-странице, но успешная загрузка не заявляется.',
      '- `GET https://www.koreaherald.com/article/10560185` → доступен; первая публикация 2025-08-23, обновление 2025-08-24. '
      '`GET https://www.koreaherald.com/article/2136020` → web 403; повторные попытки не выполнялись.',
      '- Поисковые запросы: `site:world.kbs.co.kr Japan Korea summit 2023 2019`, '
      '`site:koreajoongangdaily.joins.com Japan Korea summit 2023 2015`, '
      '`site:japantimes.co.jp/news/2025/ "Ishiba" "Lee" summit`, '
      '`site:japantimes.co.jp/news/2019/ "South Korea" "export"`. Это запросы web-поиска, не выдуманные API издателей.',
      '', 'Все импортируемые записи с датой, URL и основанием даты находятся в `data/media_manifest.json`. '
      'Сохраняется библиография, а не исходный HTML статьи. Прямая RSS-проба проекта: KBS остановлен robots Disallow до запроса feed; канал отключён. '
      'Korea Herald: robots разрешил feed, получены 50 элементов, один заголовок-кандидат с Japan сохранён в discovery_results, статус unreviewed. '
      'Ни одна статья по ленте не загружалась; кандидат не входит в 21 импортированный документ. '
      'Ненаблюдавшийся персональный автор оставлен NULL; '
      'язык публикации не подставляется как язык оригинала речи. Страна издателя не определяет гражданство цитируемого политика.',
      '', 'В поиске есть кооперация/нормализация и спорные темы у обеих стран издателей. Это целевая подборка, '
      'не сбалансированная выборка политической риторики. Подтверждённых новых депутатских высказываний нет; '
      'парламентский пробел сохранён. Тональность статей не кодировалась, веса не назначались. '
      'Наблюдавшиеся цитаты и пересказы не превращены в новые события. Права для повторного использования цитат не установлены; '
      'автоматическое извлечение цитат выключено. Все новые документы остаются в очереди проверки.']
    section(ROOT/'docs/SOURCE_AUDIT.md','\n'.join(lines))
    growth={k:result['after'][k]-result['baseline'][k] for k in result['baseline']}
    body=['## Библиографический пилот СМИ','',
      'Ниже зафиксирован результат предшествующего пилота СМИ; текущий объём корпуса указан в начале отчёта и разделе расширения.',
      'Исходные документы, заявления, цитаты и связи сохранены по хэшам строк каждого доменного набора. '
      'Это проверка сохранности перед текущим импортом; прежняя выборка 50 не пересматривалась. Схема базы не менялась.',
      '', '| Сущность | До | После | Прирост |','|---|---:|---:|---:|']
    for k in growth:body.append(f"| {k} | {result['baseline'][k]} | {result['after'][k]} | {growth[k]} |")
    body+=['',f"Набор: {len(rows)} публикация; ROK {sum(n[a['id']] for a in audits if sources[a['id']]['country']=='ROK')}, JPN {sum(n[a['id']] for a in audits if sources[a['id']]['country']=='JPN')}. "
      'Новых прямых цитат и заявлений: 0. Предел 100 — потолок, не целевое число. Полное покрытие 2015–2026 и баланс стран не достигнуты.',
      '', 'Повторный **фактический** вызов ingestion для всего набора: `'+json.dumps(result['repeat_before'],ensure_ascii=False)+'` → `'+json.dumps(result['repeat_after'],ensure_ascii=False)+'`. '
      'Уникальные сущности и связи не выросли. Сетевых запросов при импорте: 0. Совпадения не объединялись и не удалялись.']
    section(ROOT/'docs/QUALITY_REPORT.md','\n'.join(body))
    path=ROOT/'data/verification.json';v=json.loads(path.read_text(encoding='utf-8'));v['media_pilot']=result
    write_generated(path,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
    path=ROOT/'docs/REVIEW_TABLE.html';html=path.read_text(encoding='utf-8')
    table=['<section id="media"><h2>СМИ: библиография для ручной проверки</h2><p>Это документы, не новые заявления. Цитаты и связь с выступлением не установлены; дата публикации не является датой речи.</p><table><tr><th>СМИ</th><th>Публикация / URL</th><th>Дата</th><th>Автор</th><th>Проверить</th></tr>']
    for r in rows:
        table.append('<tr><td>'+escape(r['source'])+'</td><td><a href="'+escape(r['url'],quote=True)+'">'+escape(r['title'])+'</a></td><td>'+r['published_date']+'</td><td>'+escape(r.get('author') or 'не установлен')+'</td><td>Права, полный контекст, дословность, автор речи, дата/идентичность выступления, тип перевода; metadata_only</td></tr>')
    table.append('</table></section>')
    write_generated(path,html.replace('</html>',''.join(table)+'</html>'))
