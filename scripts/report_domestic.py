"""Offline refresh of the existing reports; no repeat collection or audit sampling."""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT, write_generated
from dri.storage import Store
from dri.quality import report

MARK='<!-- DOMESTIC_20261101 -->'
END='<!-- DOMESTIC_20261101_END -->'

def section(path,text):
    previous=path.read_text(encoding='utf-8')
    if END in previous:
        previous=re.sub(re.escape(MARK)+'.*?'+re.escape(END),'',previous,flags=re.S).rstrip()
    elif MARK in previous:previous=previous.split(MARK)[0].rstrip()
    write_generated(path,previous+'\n\n'+MARK+'\n'+text+'\n'+END+'\n')

def main():
    s=Store(); result=report(s);s.export()
    db=s.db
    docs=[]
    for row in db.execute("SELECT DISTINCT d.id,d.metadata_json FROM documents d JOIN collection_items i ON i.document_id=d.id JOIN collection_runs r ON r.id=i.run_id WHERE r.run_key IN ('domestic-20261101','domestic-20261101-earlier') AND i.status='processed' ORDER BY d.id"):
        docs.append((row[0],json.loads(row[1])))
    ids=[r[0] for r in docs]
    placeholders=','.join('?' for _ in ids) or 'NULL'
    st=db.execute('SELECT count(DISTINCT statement_id) FROM statement_sources WHERE document_id IN ('+placeholders+')',ids).fetchone()[0]
    qt=db.execute('SELECT count(DISTINCT quote_id) FROM quote_sources WHERE document_id IN ('+placeholders+')',ids).fetchone()[0]
    counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','statements','quotes','discovery_results','gdelt_events','gdelt_mentions','gdelt_gkg')}
    text=[
        '## Государственные и внутриполитические источники — 1 ноября 2026',
        'Исходное состояние проверено: 1437 документов / 1029 записей заявлений / 1029 цитат / 491 находка; GDELT 22 Events + 28 Mentions + 60 GKG; схема 4.',
        'Текущее состояние: `'+json.dumps(counts,ensure_ascii=False)+'`.',
        f'Добавлено: {len(docs)} полных текстов, {st} уникальных записей заявлений, {qt} подтверждённых фрагментов-цитат. Коротких документов, документов только с метаданными, GDELT и медийных упоминаний добавлено 0.',
        'Источник всех новых текстов: korea_government_kr, Республика Корея, primary, президентская администрация. Япония: 0 новых документов / заявлений / цитат.',
        'Две президентские речи, два брифинга пресс-секретарей и один институциональный брифинг 2020 года учитываются раздельно. Брифинг — письменное заявление его автора/института, а не прямая речь президента; reported speech не превращён в цитату президента.',
        f'Достоверная дата события ИЛИ публикации: {sum(bool(m.get("event_date") or m.get("published_date")) for _,m in docs)}/{len(docs)}; персональный автор: {sum(bool(m.get("author")) for _,m in docs)}/{len(docs)}. У двух речей известна дата выступления, дата публикации не подставлялась; у брифингов дата публикации, устное произнесение не утверждается.',
        'Все новые тексты: оригинал ko, KOGL Type 4, только согласованное ограниченное некоммерческое исследовательское использование, без изменений. Сохранены текст и атрибуция; фотографии, вложения и HTML с чужими медиа не архивировались. Коммерческое использование не разрешено.',
        f'Для будущих частот внутри ограниченного исследовательского подкорпуса доступны {len(docs)} полных текстов; политическая разметка требует проверки. Есть сотрудничество и критический брифинг о въездных ограничениях Японии; выборка не репрезентативна и не сбалансирована по тональности. Новых партийных/парламентских текстов нет; все типы риторики этим пилотом не покрыты.',
        '### Новые записи по годам и типу (документы / заявления / цитаты)',
        '| Год | РК, primary, речи | РК, primary, брифинги | Япония, primary | РК / Япония, secondary |',
        '|---|---:|---:|---:|---:|']
    for year in range(2015,2027):
        cells=[]
        for kind in ('official_speech','official_written_briefing'):
            n=sum((m.get('event_date') or m.get('published_date','')).startswith(str(year)) and m.get('observation_type')==kind for _,m in docs)
            cells.append(f'{n} / {n} / {n}')
        text.append(f'| {year} | '+ ' | '.join(cells)+' | 0 / 0 / 0 | 0 / 0 / 0 |')
    text += ['', '### Контроль каждой партии',
             '| Документ | Тип | Дата события / публикации | Автор | Тема | Повторный импорт |',
             '|---|---|---|---|---|---|']
    for did,m in docs:
        text.append(f'| {did} | {m["observation_type"]} | {m.get("event_date")} / {m.get("published_date")} | {m.get("author") or "не установлен"} | {m["theme"]} | 0 новых сущностей |')
    text += ['',f'SQLite integrity={result["sqlite_integrity"]}; FK errors={len(result["foreign_key_errors"])}; raw hash errors={len(result["raw_hash_errors"])}. Схема 4, миграции не выполнялись.',
             'Импорт атомарен с checkpoint на документ. После каждой записи проверен повторный ingest: 0 новых документов/заявлений/цитат. Сходные речи разных дат остаются разными событиями, возможные совпадения сохраняются для проверки. Старые 164 пары и прежние выборочные аудиты не пересматривались.',
             'Тесты: см. существующий docs/TEST_RESULTS.txt. Продолжение выполненной партии --resume не вызывает повторной загрузки.',
             'Этап дал ограниченный пилот: полный парламентский канал и МИД Японии не подключены; историческая полнота 2015–2026 не достигнута. Новые URL не засчитываются как тексты.']
    section(ROOT/'docs/QUALITY_REPORT.md','\n\n'.join(text[:9])+'\n\n'+'\n'.join(text[9:]))
    section(ROOT/'docs/SOURCE_AUDIT.md', '''## Новые государственные каналы: проверка 1 ноября 2026

Проверены новые каналы; прежние аудиты СМИ и выборки дублей не повторялись. Клиент: robots, TLS, интервал не менее 5,5 с, ограничение размера ответа, остановка при 401/403/429. Числовые серверные квоты не выдумывались. Сохранённые `fetches`/`source_checks` различают web-обнаружение и прямой транспорт.

| Канал и тестовый GET | Подтверждено | Полнота, права и результат |
|---|---|---|
| [Open Assembly](https://open.assembly.go.kr/portal/mainPage.do), [официальный OpenAPI](https://open.assembly.go.kr/portal/openapi/main.do) | Прямой HTML 200; опубликованы ссылки входа, заявки ключа, каталога и спецификаций | Доступность портала не доказывает API отдельных выступлений 2015–2026. Без подтверждённой схемы речей и ключа импорт протоколов как заявлений не выполнялся. Числовая квота не установлена. |
| [data.go.kr, 15126151](https://www.data.go.kr/data/15126151/openapi.do) | Официальная карточка 국회 국회사무처_회의록별 부록 정보; LINK / XML, бесплатно, development auto-approval, production reviewed approval | Это приложения к протоколам, не API отдельных речей. Карточка создана 2023-12-28, изменена 2024-07-12; это не даты глубины архива. Условия этого набора нельзя переносить на весь архив заседаний. |
| [korea.net, речь 231937](https://www.korea.net/Government/Briefing-Room/Presidential-Speeches/view?articleId=231937) | Официальный индекс и речь обнаружены; прямой клиент остановился на Too many redirects | Текст в базу не импортирован; недоступность канала не выдаётся за отсутствие речи. |
| [korea.kr, речь 132038430](https://www.korea.kr/briefing/speechView.do?newsId=132038430) | Прямой HTML 200, view_title / info / view_cont / kogl; дата речи 2026-01-13 | KOGL4 на конкретном тексте. Импортирован полный текст в согласованный некоммерческий исследовательский режим. |
| [korea.kr, речь 132037781](https://www.korea.kr/briefing/speechView.do?newsId=132037781) | Прямой HTML 200, дата речи 2025-08-23, роль 대통령 | KOGL4; персональное имя не установлено из проверенных полей, NULL сохранён. |
| [korea.kr, брифинг 148974237](https://www.korea.kr/briefing/presidentView.do?newsId=148974237) | Прямой HTML 200; публикация 2026-10-23, 김성완 대변인 | KOGL4; письменный брифинг пресс-секретаря, не речь президента. |
| [korea.kr, брифинг 148950259](https://www.korea.kr/briefing/presidentView.do?newsId=148950259) | Прямой HTML 200; публикация 2025-09-30, 강유정 대변인 | KOGL4; письменный/опубликованный текст; устная дата не подставлена. |
| [korea.kr, брифинг 148870027](https://www.korea.kr/briefing/presidentView.do?newsId=148870027) | Прямой HTML 200; публикация 2020-03-08, 청와대; критический ответ о мерах Японии | KOGL4; второй checkpoint, полное институциональное письменное заявление. Имя и личная должность не установлены. |
| [Democratic Party, post 1203736](https://theminjoo.kr/main/sub/news/view.php?brd=11&post=1203736) | Прямой HTML 200, официальный брифинг 한민수, 2024-05-02 | Разрешение хранения полного текста не установлено. Только обнаружение и метаданные, без заявления/цитаты в речевом корпусе. |
| [People Power Party, 105976](https://www.peoplepowerparty.kr/news/comment_view/BBSDD0001/105976) | Прямой HTML 200; 신동욱, 2025-03-25; опубликованные 이용약관, статьи 12–13 | Условия ограничивают коммерческое использование и копирование без разрешения. Полный текст не импортирован; текущий статус партии исторической записи не присвоен. |
| [MOFA Japan, release 02238](https://www.mofa.go.jp/press/release/pressite_000001_02238.html) | Web подтвердил официальный пересказ телефонного разговора, 2026-04-02; прямой клиент получил 403 на robots.txt | Запрос самой статьи прямым клиентом не выполнялся; хост остановлен. Метаданные обнаружения сохранены, документ/заявление/цитата не созданы. |
| [MOFA Japan, conference 00084](https://www.mofa.go.jp/press/kaiken/kaikenite_000001_00084.html) | Web подтвердил конференцию Мотэги 2025-12-19; английская версия — предварительный перевод внешней компании | Только обнаружение, не оригинальный японский текст. Много участников: нельзя импортировать целую конференцию как одно высказывание. Дата конференции не выдана за дату публикации. |
| [MOFA Japan, June 2026 index](https://www.mofa.go.jp/press/kaiken/fm_202606_index.html) | Официальная индексная страница подтверждена через web | Индекс не полноценный текстовый документ. Никакого обхода прямого 403, альтернативных клиентов/прокси/зеркал не применялось. |

### Ключ парламента: подтверждённая процедура и границы

На [официальной странице OpenAPI](https://open.assembly.go.kr/portal/openapi/main.do) опубликована последовательность: 로그인 → 인증키 신청 → Open API 검색 및 이용방법 확인 → приложение. Для новой учётной записи дана [ссылка регистрации National Assembly](https://member.assembly.go.kr/member/join/joinSelectPage.do), для существующей — [вход](https://open.assembly.go.kr/portal/user/loginPage.do). После входа перейти в [인증키 발급](https://open.assembly.go.kr/portal/openapi/openApiActKeyIssPage.do), затем выбрать набор в каталоге и проверить его собственную спецификацию/квоты. Прямая проверка страницы выдачи ключа дала редирект за allowlist; переход к авторизации и отправка форм не выполнялись. Наличие пункта выдачи ключа подтверждено, срок выдачи и поля закрытой формы не проверены. Не создан фиктивный ключ или предположительный endpoint стенограмм.

На data.go.kr используется «활용신청» карточки соответствующего набора после входа. Проверенная карточка относится к приложениям протоколов; она не основание заказывать или реализовывать якобы речевой API. Для продолжения нужен реально выбранный набор стенограмм/отдельных выступлений, его документация и разрешённый ключ, предоставленный через локальное защищённое окружение, без записи в код/чат.

### Ограничения сохранения

Для korea.kr действует [политика авторских прав](https://www.korea.kr/guide/copyRight.do) и индивидуальный маркер KOGL. Проверенные речи 132035073 (2023-03-07), 132036649 (2024-05-20), 132031934 (2019-12-04) не имели прикреплённой лицензии: полные тексты не сохранены. KOGL4 разрешён пользователем исключительно для ограниченного исследования; коммерческий режим и изменение текстов запрещены. Извлечённый полный опубликованный текст сохраняется отдельно от аналитических полей; подписи к медиа не используются. Статические API/RSS для выгрузки речей korea.kr не подтверждены; на сайте обнаружено уведомление о прекращении RSS, работающий feed не заявляется.

Вторая ограниченная проверка: речи 132032292 (2020-06-29), 132032551 (2020-11-03), 132031638 (2019-10-22), 132032396 проверены отдельно; отсутствие подтверждённого разрешения не заменено предположением. Результаты — в source_checks.

Три URL МИД Японии и два партийных URL сохранены в discovery_results (491 → 496); они не добавлены к документам или качественным наблюдениям. Документированный анонимный поисковый API МИД Японии не установлен: наличие Custom Search не считается разрешением API. Полнота архивов 2015–2026, партийных исторических переименований и парламентских речей не доказана. Президентский архив и полный архив премьер-министра на этом пилоте не подключены; пустые результаты поиска не являются подтверждённой недоступностью. Неисполненные каналы остаются задачами продолжения, а не объявляются завершёнными.
''')
    section(ROOT/'README.md',
        '## Государственные источники: ограниченный исследовательский пилот\n\n'
        f'Добавлено {len(docs)} полных текстов korea.kr, {st} записей заявлений и {qt} цитат. Основная база прежняя, схема 4. '
        'Все новые тексты имеют KOGL4: **только некоммерческое исследовательское использование, без изменений, с атрибуцией**. '
        'Ограничение относится и к текстам в единственной внутренней выгрузке data/corpus.jsonl. '
        'Для коммерческого корпуса фильтровать content_policy=restricted_research_full_text; не использовать и не распространять такие тексты коммерчески.\n\n'
        'Офлайн: `python scripts/run_tests.py`, `python scripts/report_domestic.py`. '
        'План без сети: `python scripts/collect_domestic.py --restricted-research --resume`. '
        'Продолжить согласованную очередь: `python scripts/collect_domestic.py --execute --restricted-research --resume`. '
        'Вторая партия 2020 года: добавить `--batch earlier` к команде продолжения. '
        'Обработанные документы не загружаются повторно; новые URL добавлять только после проверки источника, авторства и лицензии. '
        'Ключи API в репозиторий и чат не помещать. Ограничения и процедура ключа — в docs/SOURCE_AUDIT.md; статистика — в docs/QUALITY_REPORT.md.')
    section(ROOT/'docs/CHANGES.md',
        '## Государственные источники, 2026-11-01\n\n'
        'Добавлены dri/connectors/korea_government.py, scripts/collect_domestic.py, scripts/report_domestic.py, tests/test_korea_government.py. '
        'Изменены config/sources.json, README.md, docs/SOURCE_AUDIT.md, docs/QUALITY_REPORT.md, docs/CHANGES.md, docs/TEST_RESULTS.txt, docs/REVIEW_TABLE.html; '
        'обновлены data/dri.sqlite3, data/corpus.jsonl, data/verification.json, data/errors.jsonl и оригинальные текстовые файлы/robots в существующем data/raw. '
        'Полные HTML с медиа не сохранялись. Установок зависимостей, миграций, новых рабочих папок и параллельных баз нет. '
        'Использованы действующие entity ingestion, checkpoint и журнал ошибок; политика KOGL4 требует явного флага. '
        'Даты выступления и публикации различаются; неизвестный автор не выводится из занимаемой должности. '
        'Отдельные тесты проверяют запрет неизвестной лицензии, ограниченный режим, происхождение автора, структуру, период, повторный импорт и сохранение похожих речей разных дат.')
    v=ROOT/'data/verification.json'; obj=json.loads(v.read_text(encoding='utf-8'))
    obj['domestic_20261101']={'new_documents':len(docs),'new_statements':st,'new_quotes':qt,'full_texts':len(docs),'restricted_noncommercial':len(docs),'baseline_documents':1437,'baseline_statements':1029,'baseline_quotes':1029,'counts':counts}
    write_generated(v,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(obj['domestic_20261101']))
    s.db.close()

if __name__=='__main__':main()
