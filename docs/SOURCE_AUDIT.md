# Технический аудит DRI

<!-- CURRENT_SOURCE_AUDIT_START -->
## Реестр источников и сохранённая история подключения каналов

Основная база не менялась: `data/dri.sqlite3`. Ниже — накопленные сведения реестра и прежних пилотов; результаты текущего этапа находятся в разделе «Расширение корпуса: новые подтверждения и ограничения». Первоначальный аудит сохранён как история проверок.
Открытая главная страница не доказывает доступность статей, архива или лицензию. Неизвестная глубина архива не заменена предположением. Числовые веса источникам не назначены.

| Источник | Страна издателя / тип | Реальная проверка | Хранение | Надёжность (категория) |
|---|---|---|---|---|
| [GDELT: DOC discovery; separate Events/Mentions/GKG archives](https://gdeltproject.org) | международный / discovery | HTTP 200: {"gkg_country_cooccurrence": 60, "bounded_retry_after_local_4MB_cap": true} | metadata_only | automated_discovery_or_event_extraction |
| [National Assembly of Korea](https://www.assembly.go.kr) | ROK / primary | Подтверждены sample API и публичные PDF; внутреннее извлечение и границы импорта описаны в разделе парламентского PDF-пилота. Тексты технических журналов не публикуются. | internal_research_only | official_parliamentary_record |
| [Democratic Party of Korea](https://theminjoo.kr) | ROK / primary | Ошибка сети/TLS; подробности source_checks | metadata_only | official_party_publication |
| [House of Representatives Japan](https://www.shugiin.go.jp) | JPN / primary | HTTP 302: root_http_302; document access and licence not established | metadata_only | official_parliamentary_record |
| [Prime Minister's Office of Japan](https://japan.kantei.go.jp) | JPN / primary | Ошибка сети/TLS; подробности source_checks | metadata_only | official_institutional_record |
| [National Diet Library speech transcripts](https://kokkai.ndl.go.jp) | JPN / primary | API JSON подтверждён за 2015–2026; robots перенаправляет на главную, действует явно опубликованное разрешение API | excerpt_only | official_parliamentary_record |
| [Republic of Korea Policy Briefing — official speeches and presidential briefings](https://www.korea.kr) | ROK / primary | HTTP 200: {"import": {"document_id": 1442, "documents_added": 1, "statements_added": 1, "quotes_added": 1, "duplicates_rejected": 0, "possible_matches": 0}, "replay": {"document_id": 1442, "documents_added": 0, "statements_added": 0, "quotes_added": 0, "duplicates_rejected": 3, "possible_matches": 0}, "field_check": {"dated": true, "named": false}, "theme": "diplomatic_contacts"} | item_licence_required | official_institutional_record |
| [Japan Ministry of Defense](https://www.mod.go.jp) | JPN / primary | HTTP 403: root_http_403; document access and licence not established | metadata_only | official_institutional_record |
| [MOFA Japan](https://www.mofa.go.jp) | JPN / primary | Ошибка сети/TLS; подробности source_checks | metadata_only | official_institutional_record |
| [MOFA Republic of Korea](https://www.mofa.go.kr) | ROK / primary | HTML-поиск и документы подтверждены; отмечались также TLS-ошибки отдельных запросов | excerpt_only | official_institutional_record |
| [People Power Party](https://www.peoplepowerparty.kr) | ROK / primary | Ошибка сети/TLS; подробности source_checks | metadata_only | official_party_publication |
| [Office of the President, Republic of Korea](https://www.president.go.kr) | ROK / primary | HTTP 200: New channel HTML accessible; no document imported | metadata_only | official_institutional_record |
| [AFP](https://www.afp.com) | международный / secondary | HTTP 301: root_http_301; document access and licence not established | metadata_only | news_agency_secondary |
| [Associated Press](https://apnews.com) | международный / secondary | HTTP 403: root_http_403; document access and licence not established | metadata_only | news_agency_secondary |
| [The Asahi Shimbun](https://www.asahi.com) | JPN / secondary | HTTP 200: root_http_200; document access and licence not established | metadata_only | newspaper_secondary |
| [The Japan Times](https://www.japantimes.co.jp) | JPN / secondary | HTTP 200: root_http_200; document access and licence not established | metadata_only | newspaper_secondary |
| [Korea JoongAng Daily](https://koreajoongangdaily.joins.com) | ROK / secondary | HTTP 301: robots_unavailable_301 | metadata_only | newspaper_secondary |
| [KBS](https://news.kbs.co.kr) | ROK / secondary | HTTP 200: root_http_200; document access and licence not established | metadata_only | broadcaster_secondary |
| [The Korea Herald](https://www.koreaherald.com) | ROK / secondary | HTTP 200: root_http_200; document access and licence not established | metadata_only | newspaper_secondary |
| [The Korea Times](https://www.koreatimes.co.kr) | ROK / secondary | bibliography_only; успешное получение документов не подтверждено | metadata_only | newspaper_secondary |
| [Kyodo / Kyodo News+](https://english.kyodonews.net) | JPN / secondary | HTTP 200: root_http_200; document access and licence not established | metadata_only | news_agency_secondary |
| [NHK World](https://www3.nhk.or.jp) | JPN / secondary | HTTP 303: root_http_303; document access and licence not established | metadata_only | broadcaster_secondary |
| [Reuters](https://www.reuters.com) | международный / secondary | HTTP 200: root_disallowed_by_robots | metadata_only | news_agency_secondary |
| [The Yomiuri Shimbun / The Japan News](https://www.yomiuri.co.jp) | JPN / secondary | bibliography_only; успешное получение документов не подтверждено | metadata_only | newspaper_secondary |
| [Yonhap](https://en.yna.co.kr) | ROK / secondary | HTTP 200: root_http_200; document access and licence not established | metadata_only | news_agency_secondary |

### Реально подключённые каналы

**MOFA Korea.** Форма живого HTML подтверждает `srchWord` и `srchTp=0` (заголовок), страницы переключаются `page`. Ссылки используют `f_view(идентификатор)`; импортируются только фактически опубликованные seq. Отдельный комментарий/statement пресс-секретаря создаёт институциональное заявление с неизвестным личным именем и датой произнесения. Сообщение о встрече не становится заявлением автоматически. Новые тела ответов не архивируются; остаётся до 25 слов. Проверены даты документов, за пределы 2015-01-01—2026-10-28 импорт запрещён.

**NDL Kokkai.** [Официальная спецификация](https://kokkai.ndl.go.jp/api.html) описывает GET `/api/speech`, JSON/XML, поиск по дате и должности, максимум 100 результатов, последовательные запросы с паузой. Регистрация не требуется. Выполнена выборка `any=韓国`, `speakerPosition=大臣`, по одному году, 20 результатов запроса, до 6 отобранных реплик за год. Уникальность — `speechID`; сохранены японский язык, имя, должность и дата заседания. Дата публикации отсутствует и остаётся NULL. API сортирует новые заседания первыми: это создаёт смещение к концу года, а не репрезентативную выборку. Берётся короткий фрагмент вокруг первого упоминания 韓国/日韓; соответствие темы, адресата и контекст требуют ручной проверки.

Дополнительная узкая выборка `any=日中韓` за 2024 год дала две новые реплики о региональном сотрудничестве. Выборки `any=韓国 関係改善` за 2023 и 2018 годы после строгой проверки короткого фрагмента и исключения известных speechID не дали новых записей. Этот тематический пробел сохранён явно, а не заполнен предположениями.

Тестовый запрос (реально успешный; перед повтором соблюсти паузу):

```text
GET https://kokkai.ndl.go.jp/api/speech?any=%E9%9F%93%E5%9B%BD&speakerPosition=%E5%A4%A7%E8%87%A3&from=2015-01-01&until=2015-12-31&maximumRecords=20&recordPacking=json
```

robots.txt Kokkai отвечает редиректом на главную, а не правилом Disallow. Исключение в сборщике относится только к явно разрешённому документацией `/api/speech` на этом хосте и только при таком редиректе. Оно не действует при Disallow, 401, 403 или 429. Общий клиент для других сайтов по-прежнему прекращает сбор при неизвестных правилах.

Права на индивидуальные выступления Kokkai принадлежат выступающим; API не передаёт их автоматически. Полные новые стенограммы/JSON-ответы не сохранялись, только метаданные, хэш и до 90 последовательных японских символов для исследования. Это не разрешение перепубликовать полный корпус выступлений или переводы.

### Вторичные источники и документированные продукты

Пять записей Yonhap/AP в `data/secondary_manifest.json` — библиографические метаданные из web-поиска с явно наблюдавшейся датой публикации, а не прямые загрузки статей. Поля текста пусты; новых заявлений/цитат по этим записям не создано. Их соответствие конкретным выступлениям пока не проверено, поэтому нет искусственных связей с похожими событиями.

- [Yonhap copyright](https://en.yna.co.kr/view/AEN20200320005600315) и [уведомление 2026](https://www.yna.co.kr/amp/view/AKR20260611091000011): разрешение на массовую выгрузку не установлено. Сохраняется только библиография.
- Reuters robots запретил корень; статьи не запрашивались. [Reuters Connect terms](https://www.reutersconnect.com/general-terms) ограничивают автоматическое извлечение; наличие лицензии на Connect не предполагается и не переносится на другие продукты.
- [AFP документирует Content API](https://www.afp.com/en/agency/inside-afp/press-release/afp-launches-its-new-api-afp-content-api). Доступ клиента, токены, квоты и архив 2015–2026 не подтверждены; коммерческий API не выдан за свободный endpoint.
- [AP ENPS/Storytelling](https://developer.ap.org/enps-storytelling/) — отдельный продукт с договором/ключом, не открытый API исторических статей AP News. Прямой AP News вернул 403. Эти продукты не подключены.
- [Japan Times: переиспользование](https://www.japantimes.co.jp/republishing/jp/): права требуют отдельной проверки; статьи не сохранялись.
- KBS, JoongAng Daily, Korea Herald, Kyodo, NHK и Asahi: выполнены указанные в таблице точечные проверки доступа. Разрешённый исторический API, RSS-глубина, лицензия массового сохранения, полнота за каждый год и гарантированные автор/текст статьи **не подтверждены**. 200 на главной не объявляется подтверждением этих возможностей. Ключи и подписки не создавались.

### Остальные первичные источники

[Канцелярия премьер-министра Японии](https://japan.kantei.go.jp/policies/terms_e.html) публикует PDL 1.0, но прямой доступ к проверенному хосту завершился сетевой ошибкой, а старый пример страницы через web-инструмент — 404. У корейского президентского сайта и Национального собрания прямые проверки также завершились сетевыми ошибками. У нижней палаты Японии — перенаправление, у Минобороны — 403; автоматический архивный сбор не выполнялся. Это ограничения текущей среды проверки, а не утверждения об отсутствии исторических данных.

Полные результаты новых проб хранятся структурированно в `source_checks` и `fetches` единственной базы; тела защищённых страниц не сохранены. Имеющиеся старые audit/raw-файлы и два исходных документа не удалялись и не подменялись.

## Первоначальная проверка (сохранённая история)
<!-- CURRENT_SOURCE_AUDIT_END -->



































Проверка: **2026-10-28**, Республика Корея — Япония, целевой интервал
2015-01-01 — 2026-10-28. Наличие отдельных документов и архива не доказывает
полноту. Ни один источник не признан полным за весь интервал.

Результат пилота: **2 документа MOFA Korea**, исходные HTTP-байты, извлечённый
английский текст, календарная дата публикации и ссылка сохранены. Личный автор
не указан; `author=null`. **Корпус из двух МИД пока не получен:** MOFA Japan
отклоняет прямые запросы HTTP 403. Обход блокировки не выполнялся.

## Таблица подтверждённых источников и границ проверки

| Источник | Подтверждённый способ / тестовый GET | Результат проверки | История / полнота | Текст, дата, автор, ссылка |
|---|---|---|---|---|
| MOFA Korea, English press releases | [HTML-документ 315568](https://www.mofa.go.kr/eng/brd/m_5676/view.do?seq=315568), второй `seq=315569` | Через Windows TLS: HTTP 200, парсер проверен на настоящем HTML. Python/OpenSSL первоначально отклонил цепочку сертификата. | Подтверждены документы августа 2015. [Индекс](https://www.mofa.go.kr/eng/brd/m_5676/list.do) присутствует в поисковом представлении и содержит материалы 2026; историческая пагинация по всем годам не проверена. | Полный текст HTML, дата `YYYY-MM-DD`, URL, издатель. В двух примерах нет личного автора. Английский текст имеет пометку unofficial translation: это оригинал английской публикации, не корейский первоисточник. |
| MOFA Korea, RSS | [Страница RSS](https://www.mofa.go.kr/eng/wpge/m_20360/contents.do), [HTTPS RSS press release](https://www.mofa.go.kr/www/brd/rss.do?brdId=302) | HTTP 200, `application/rss+xml`, XML разобран, 29 items. На странице отдельно опубликован `brdId=303` для press briefing; его полноценный ответ не проверен. | RSS — текущая лента, не исторический архив. Глубина удержания не опубликована в проверенной странице. | Заголовки, pubDate, links; у двух проверенных items нет description. Есть некорректные ссылки вида `http://www.mofa.go.kr:443/www/brd/m_5676/...`: их нельзя слепо обходить. Сопоставление с HTML обязательно. |
| MOFA Japan, press releases / bilateral archive | [Пример документа 2025](https://www.mofa.go.jp/press/release/pressite_000001_01500.html), [архив отношений](https://www.mofa.go.jp/region/asia-paci/korea/archives.html) | Прямые GET: HTTP 403 (Akamai). Через web-поиск доступны текстовые представления, но они не выданы за прямой сбор HTML. | Тематический архив перечисляет 2015–2026. [Общий архив пресс-релизов](https://www.mofa.go.jp/press/release/index.html) направляет до 2021 в NDL WARP. Отдельные старые тематические ссылки могут оставаться на основном сайте. Доступность каждой не проверена. | В web-представлении примера есть текст, дата, URL, институциональная атрибуция; наличие личного автора не гарантировано. Прямой парсер экспериментальный, на живом HTML не подтверждён. |
| data.go.kr — MOFA COVID safety notices | [Официальная карточка 15080336](https://www.data.go.kr/data/15080336/openapi.do) | Карточка HTTP 200, подтверждены REST/JSON, схема и адрес. Рабочий запрос к API с ключом не выполнен: ключа нет. Это не API пресс-релизов. | Карточка зарегистрирована 2021-04-09; временной охват не указан. Регистрация не означает начало всех записей. Полнота 2015–2026 не подтверждена. | Схема содержит `html_origin_cn`, `txt_origin_cn`, `wrt_dt`, title и notice ID; есть также legacy-поля. Личного автора и стабильного URL страницы в перечне не подтверждено; URL вложения не заменяет permalink документа. |
| Япония: data.go.jp → e-Gov Data Portal | [Актуальная документация](https://data.e-gov.go.jp/data/api_guide); [GET package_search?q=mofa&rows=1](https://data.e-gov.go.jp/data/api/action/package_search?q=mofa&rows=1) | HTTP 200, JSON `success=true`, `result.count=350`. Первый результат `maff_20140918_0425`, организация `org_1700`: свободный поиск `mofa` не является точным фильтром издателя. | Каталог метаданных и ссылок на ресурсы, не полный архив заявлений МИД. Старая ссылка `www.data.go.jp/for-developer/for-developer/` вернула 404 через web-инструмент. | Метаданные/описания и ссылки ресурсов; исходный текст, автор и дата публикации документа требуют отдельного ресурса. `metadata_modified` нельзя использовать как дату заявления. |
| GDELT DOC 2.0 | [Документация](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/); [GET artlist, Japan Korea, 1d, 5 записей](https://api.gdeltproject.org/api/v2/doc/doc?query=Japan%20Korea&mode=artlist&maxrecords=5&timespan=1d&format=json) | Прямой запрос: HTTP 429. Тело требует не более 1 запроса / 5 секунд. Повтор не делался; успешный JSON в этой среде не подтверждён. | По опубликованной документации DOC — скользящее окно последних 3 месяцев; не средство выгрузки 2015–2026. Статья документации 2017 года, текущая глубина экспериментально не проверена. | Поисковые метаданные/URL, не API выдачи полного оригинального текста. `seendate` не надёжная дата публикации; личный автор не гарантирован. Текст получать у издателя с его правилами. |
| GDELT Events / Mentions / GKG raw, BigQuery | [Официальная страница данных](https://gdeltproject.org/data.html), [описание 2.0](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/), [Event codebook](https://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf) | Документированные архивы и BigQuery подтверждены официальными страницами. Файлы и облачные запросы не загружались/не выполнялись. Не помечены как проверенные живые endpoints. | 2.0 стартовал 2015-02-19; для начала 2015 требуется проверить 1.0. Обещание исторического backfill в старой статье не считается доказательством его выполнения. Непрерывность файлов 2015–2026 не проверена. | Структурированные производные записи и URL источников, а не полный текст статей. Даты события/наблюдения нельзя смешивать с датой публикации. Это медиапокрытие, не гарантированный реестр официальных заявлений. |

## Ограничения и условия использования

**MOFA Korea.** robots.txt получен через Windows trust; `User-agent: *`, `Allow: /`.
Опубликованный числовой rate limit в проверенных страницах не найден. Принята
локальная пауза 5,5 секунды; это настройка проекта, не утверждение о квоте МИД.
Достоверную актуальную общую лицензию английских пресс-релизов установить не
удалось. Проверенный старый путь `/www/wpge/m_20346/contents.do` вернул HTTP 200,
но содержал «страница не найдена» — он **не подтверждает политику**. Нельзя
переносить лицензию data.go.kr или другой корейской организации на эти документы.
Снимки оставлены для локального исследования; разрешение на публичное
переиздание корпуса не утверждается. Для публикации нужно подтвердить условия
конкретных страниц/KOGL и права на вложения; изображения не собираются.

**MOFA Japan.** robots.txt и два HTML-запроса дали 403; дальнейший прямой сбор
остановлен. Публичная документация [Legal Notices](https://www.mofa.go.jp/about/legalmatters.html)
указывает PDL 1.0 по умолчанию с исключениями: атрибуция источника, URL и даты
доступа; маркировка изменений, проверка прав третьих сторон. Числовой лимит
автоматического доступа не установлен в изученных материалах. API пресс-релизов
и RSS именно дипломатических заявлений не подтверждены. Не путать с RSS
министерства финансов `mof.go.jp`. [RSS anzen.mofa.go.jp](https://www.anzen.mofa.go.jp/c_info/oshirase_rss.html)
документирован для предупреждений путешественникам, не заменяет архив заявлений;
его endpoint в этом аудите не тестировался.

**data.go.kr.** Карточка COVID API указывает бесплатность, development traffic
10 000, автоматическое одобрение и возможность увеличения при регистрации
использования. Ошибки описывают дневные/секундные ограничения; точная секундная
квота не указана. Нужны serviceKey и одобрение использования; квота конкретного
аккаунта не проверена. Карточка указывает отсутствие ограничений лицензии для
данного набора. Это не общее разрешение для всего портала или HTML МИД.
Полученный robots.txt портала сохранён в `data/audit/5fb40eaa02b62bcb.bin`.

**e-Gov.** Метаданные доступны без ключа; документация запрещает использование
API изменения данных. Квота запросов в прочитанной документации не найдена.
[Условия портала](https://data.e-gov.go.jp/info/terms) ссылаются на PDL 1.0:
атрибуция и обозначение обработки. Лицензию конечного ресурса проверять отдельно;
у первого тестового результата `license_title=null`, это не CC0. robots.txt
вернул 404; это отсутствие файла, не гарантия любых способов доступа.

**GDELT.** Без ключа; лимит 1/5 секунд подтверждён телом 429, суточная квота не
подтверждена. robots.txt API вернул 404. Официальная страница называет базу
свободной и открытой, но это не передача прав на статьи внешних издателей.
Для исторических BigQuery-запросов могут понадобиться аккаунт, проект и бюджет;
облачные ресурсы не создавались. Сентимент, Goldstein и другие готовые оценки
GDELT не импортировались и не использовались как вероятность конфликта.

## Тестовые запросы

Из корня проекта ниже можно выполнить **сначала просмотрев адреса и правила**.
Команды приведены для воспроизводимости; они не означают, что каждый сервис
успешно выдаёт данные. Скрипт сохраняет статус, заголовки, UTC-время, SHA-256,
ошибку и тело ответа, не устанавливает пакеты.

```powershell
# Корейский HTML: штатный сбор с robots.txt; сначала только план.
python -m dri collect --limit 2 --transport windows
python -m dri collect --limit 2 --transport windows --execute

# RSS, подтверждённый на официальной странице (HTTPS вместо опубликованного HTTP).
python scripts/probe.py --windows 'https://www.mofa.go.kr/www/brd/rss.do?brdId=302'

# e-Gov: живая JSON-проверка; q=mofa — свободный поиск, не фильтр организации.
python scripts/probe.py 'https://data.e-gov.go.jp/data/api/action/package_search?q=mofa&rows=1'

# GDELT: при текущем 429 НЕ повторять до снятия ограничения/паузы.
python scripts/probe.py 'https://api.gdeltproject.org/api/v2/doc/doc?query=Japan%20Korea&mode=artlist&maxrecords=5&timespan=1d&format=json'
```

Документированный корейский API (не запускался без ключа):

```text
GET https://apis.data.go.kr/1262000/CountryCovid19SafetyServiceNew/getCountrySafetyNewsListNew
  ?serviceKey=<PERSONAL_KEY>
  &returnType=JSON
  &numOfRows=1
  &pageNo=1
  &cond%5Bcountry_iso_alp2%3A%3AEQ%5D=JP
```

Не передавайте персональный ключ в публичный лог или `scripts/probe.py`: скрипт
аудита сохраняет URL. Для этого API перед внедрением нужен транспорт с
редактированием секретов и проверкой схемы на реальном ответе. Не добавлен
фиктивный API корейских или японских пресс-релизов.

## Артефакты доказательств

Прямые пробы: `data/audit/*.json` рядом с телами `*.bin`.
Сохранённые ответы включают cookies сервера; это локальные технические
доказательства, не публичный пакет для распространения.

| Проверка | Локальное доказательство |
|---|---|
| MOFA Japan robots 403 | `data/audit/bd9e18dc4aa2f4ba.json` |
| MOFA Japan документ 403 | `data/audit/3dd1376cd29449ca.json` |
| MOFA Japan тематический архив 403 | `data/audit/abb73fdf064cca2c.json` |
| e-Gov JSON success | `data/audit/3b7215abdcfc3173.json` |
| GDELT 429 и текст ограничения | `data/audit/471cc66258f9edd8.json`, `*.bin` |
| Корейский RSS, 29 записей | `data/audit/e147bb962e06854c.json`, `*.bin` |
| Устаревший URL политики — soft 404 | `data/audit/40039a114bd1253c.json`, `*.bin` |
| Корейские robots и документы через коннектор | таблица `fetches` в `data/dri.sqlite3`; raw-файлы и observations в `data/corpus.jsonl` |

Web-представления использованы для поиска документации и ссылок, не импортированы
в корпус как оригинальные HTTP-ответы. Ошибки предыдущих запусков сохранены;
они не скрыты успешным запуском.

## Историческое покрытие и следующий технический шаг

2015: два корейских документа подтверждены и сохранены. 2016–2025: массовый
корейский архив не проверен; японский тематический индекс содержит ссылки, но
прямое получение не подтверждено. 2026: видны свежие записи индексов/RSS, а год
ещё не завершён. Для всех годов доля пропусков неизвестна, числовой coverage
не рассчитывался.

Для полного исследования нужны отдельный реестр URL по годам/языкам/типам,
проверка каждого URL, фиксация удалённых и закрытых документов, сравнение
корейских и английских версий, WARP-ограничений и вложений. Число результатов
по ключевым словам не является доказательством полноты: встречаются ROK,
Republic of Korea, South Korea, Korea, Japan, японские и корейские написания.

Разблокирование второго официального источника требует доступного разрешённого
канала: например, предоставленного пользователем HTML или подтверждённого
официального архива с разрешённым доступом. Затем необходимо проверить живую
структуру японского HTML и заменить экспериментальные селекторы. До этого
статус пилота из двух источников остаётся **incomplete / blocked by source access**.

Дополнительно проверен архивный адрес, прямо опубликованный в общем индексе МИД:
[NDL WARP, снимок 2025-01-06](https://warp.ndl.go.jp/web/20250106191245/www.mofa.go.jp/press/release/index.html).
Web-инструмент получил HTTP 403; robots.txt WARP и информационная страница
не прочитаны. Правила массового доступа WARP, API и возможность получения
конкретных снимков 2015 года не подтверждены. Запросов к архивным документам
и попыток обхода не делалось. Это результат web-проверки, исходное тело
HTTP-ответа в локальном пакете отсутствует.
































<!-- DOMESTIC_20261101 -->
## Новые государственные каналы: проверка 1 ноября 2026

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

<!-- DOMESTIC_20261101_END -->

<!-- ASSEMBLY_API_20261101 -->
## Национальное собрание РК: конкретные API, 1 ноября 2026

Проверка только парламентского канала. Исходное и конечное состояние: 1442 документа / 1034 заявления / 1034 цитаты, схема 4. Подтверждённые JSON-спецификации и sample-ответы сохранены в source_checks существующей базы; тела защищённых/немаркированных PDF не сохранены.

| Набор | ID / метод | Обязательные фильтры | Содержание ответа |
|---|---|---|---|
| [본회의 회의록](https://open.assembly.go.kr/portal/data/service/selectAPIServicePage.do/OO1X9P001017YF13038?infId=OO1X9P001017YF13038&infSeq=2) | `OO1X9P001017YF13038` / `nzbyfwhwaoanttzje` | `DAE_NUM, CONF_DATE` | пункты повестки, дата, орган, CONF_ID, CONFER_NUM, PDF_LINK_URL, CONF_LINK_URL; поля текста речи и говорящего отсутствуют |
| [위원회 회의록](https://open.assembly.go.kr/portal/data/service/selectAPIServicePage.do/OR137O001023MZ19321?infId=OR137O001023MZ19321&infSeq=2) | `OR137O001023MZ19321` / `ncwgseseafwbuheph` | `DAE_NUM, CONF_DATE` | пункты повестки, дата, орган, CONF_ID, CONFER_NUM, PDF_LINK_URL, CONF_LINK_URL; поля текста речи и говорящего отсутствуют |
| [회의록별 상세정보](https://open.assembly.go.kr/portal/data/service/selectAPIServicePage.do/OOWY4R001216HX11520?infId=OOWY4R001216HX11520&infSeq=2) | `OOWY4R001216HX11520` / `VCONFDETAIL` | `CONF_ID` | метаданные заседания, DOWN_URL; поля текста речи и говорящего отсутствуют |

### Параметры и ограничения

Базовый адрес: `https://open.assembly.go.kr/portal/openapi/{method}`. JSON-спецификация карточки загружается штатным публичным запросом `https://open.assembly.go.kr/portal/data/openapi/selectOpenApiMeta.do?infId={ID}&infSeq=2`. Это интерфейс документации; он не является методом выгрузки выступлений.

Общие параметры карточки: `KEY` (выданный ключ, по умолчанию sample), `Type=xml|json` (по умолчанию xml), `pIndex` (по умолчанию 1), `pSize` (по умолчанию 100). В карточке они помечены обязательными, но sample работает без KEY. Для sample карточка фиксирует pIndex=1 и pSize=5; живые запросы вернули по 5 строк. Общий guide говорит о 10 записях — для этих методов использовано более строгое ограничение карточки, 5. Sample-пагинация и повышение лимита не применялись.

Спецификации указывают apiTrf=200000; код ERROR-337 относится к суточной квоте, ERROR-336 — к пределу 1000 записей на запрос. Это опубликованные параметры, а не проверенная нагрузочным тестом гарантия квоты любого будущего ключа. Локальный интервал остаётся не менее 5,5 секунды.

Пленарный метод: DAE_NUM и CONF_DATE обязательны; TITLE, CLASS_NAME, SUB_NUM, SUB_NAME — необязательные фильтры. Комитетский: DAE_NUM и CONF_DATE обязательны; TITLE, CLASS_NAME, COMM_NAME, SUB_NAME, DEPT_CD необязательны. CONF_DATE проверен как год и год-месяц. VCONFDETAIL: CONF_ID обязателен. CONF_ID сохранять строкой: встречаются ведущие нули и префикс N. Не путать CONF_ID с CONFER_NUM — URL PDF использует номер протокола, не всегда CONF_ID.

### Исторические проверки и воспроизводимые запросы

| Запрос без KEY | Результат | Строк в выборке / всего строк повестки | Уникальных заседаний в выборке |
|---|---|---:|---:|
| [GET](https://open.assembly.go.kr/portal/openapi/nzbyfwhwaoanttzje?Type=json&pIndex=1&pSize=5&DAE_NUM=19&CONF_DATE=2015) `nzbyfwhwaoanttzje` / `{'term': 19, 'period': '2015'}` | INFO-000 | 5 / 1134 | 1 |
| [GET](https://open.assembly.go.kr/portal/openapi/ncwgseseafwbuheph?Type=json&pIndex=1&pSize=5&DAE_NUM=20&CONF_DATE=2019) `ncwgseseafwbuheph` / `{'term': 20, 'period': '2019'}` | INFO-000 | 5 / 29709 | 1 |
| [GET](https://open.assembly.go.kr/portal/openapi/nzbyfwhwaoanttzje?Type=json&pIndex=1&pSize=5&DAE_NUM=21&CONF_DATE=2023) `nzbyfwhwaoanttzje` / `{'term': 21, 'period': '2023'}` | INFO-000 | 5 / 1312 | 1 |
| [GET](https://open.assembly.go.kr/portal/openapi/ncwgseseafwbuheph?Type=json&pIndex=1&pSize=5&DAE_NUM=22&CONF_DATE=2026) `ncwgseseafwbuheph` / `{'term': 22, 'period': '2026'}` | INFO-000 | 5 / 13663 | 3 |
| [GET](https://open.assembly.go.kr/portal/openapi/ncwgseseafwbuheph?Type=json&pIndex=1&pSize=5&DAE_NUM=20&CONF_DATE=2019&COMM_NAME=%EC%99%B8%EA%B5%90%ED%86%B5%EC%9D%BC%EC%9C%84%EC%9B%90%ED%9A%8C) `ncwgseseafwbuheph` / `{'term': 20, 'period': '2019', 'committee': '외교통일위원회'}` | INFO-000 | 5 / 388 | 4 |
| [GET](https://open.assembly.go.kr/portal/openapi/ncwgseseafwbuheph?Type=json&pIndex=1&pSize=5&DAE_NUM=20&CONF_DATE=2019-07&COMM_NAME=%EC%99%B8%EA%B5%90%ED%86%B5%EC%9D%BC%EC%9C%84%EC%9B%90%ED%9A%8C) `ncwgseseafwbuheph` / `{'term': 20, 'period': '2019-07', 'committee': '외교통일위원회'}` | INFO-000 | 5 / 132 | 3 |
| [GET](https://open.assembly.go.kr/portal/openapi/VCONFDETAIL?Type=json&pIndex=1&pSize=5&CONF_ID=054151) `VCONFDETAIL` / `{'conf_id': '054151'}` | INFO-000 | 1 / 1 | 0 |

Подтверждены записи за 2015, 2019, 2023, 2026. Это наблюдаемый исторический диапазон, не доказательство полноты каждого года, каждого комитета или отсутствия пропусков. Даты открытия карточек (2019/2024) не являются началом архива. Полный период 2015–2026 не объявляется исчерпанным. Отбор по годам и комитету не зависит от конфликтных слов.

Строка списка — пункт повестки, не отдельная речь и не обязательно отдельное заседание. Повторяющиеся CONF_ID группируются; ни одна из этих строк не создаёт Document, Statement или Quote.

### Тексты PDF и права

Прямой PDF из ответа за 2015 год: [протокол 40229](https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=40229). Проверен HTTP 200, application/pdf, сигнатура %PDF, размер 2787328 байт, 237 страниц; текст первой страницы извлекается pypdf. Проверка выполнена в памяти; файл не сохранён. Протокол содержит много говорящих и не импортировался как одно заявление.

На карточке «위원회 회의록» найден маркер `/images/copyright01.gif`, alt «공공누리 - 공공저작물 자유이용허락 : 출처표시» (KOGL1). [Политика портала](https://open.assembly.go.kr/portal/policy/copyRightPage.do) требует проверять маркер конкретного материала. В [исходном архиве](https://record.assembly.go.kr/assembly/) окно «저작권 정책» (#pop_layer3) также требует KOGL1, а для немаркированных материалов — предварительного согласования. Лицензия набора метаданных не объявлена автоматически лицензией всех внешних PDF и всех реплик свидетелей. Индивидуальное разрешение проверенного PDF не установлено; оригинальные выступления не сохранены. Контакт из опубликованной политики архива: webmaster@assembly.go.kr, 02-6788-3055; сообщения не отправлялись.

### Как получить ключ для этих наборов

1. Открыть [официальное руководство](https://open.assembly.go.kr/portal/openapi/openApiDevPage.do), выбрать подходящую карточку выше и «명세서 다운로드». Текущая динамическая спецификация уже подтверждена и сохранена в source_checks.
2. [Зарегистрировать учётную запись National Assembly](https://member.assembly.go.kr/member/join/joinSelectPage.do), если её нет, затем [войти](https://open.assembly.go.kr/portal/user/loginPage.do). Регистрация и проверка личности выполняются пользователем; авторизация не обходилась.
3. Открыть [인증키 발급](https://open.assembly.go.kr/portal/openapi/openApiActKeyIssPage.do) либо кнопку [인증키 신청](https://open.assembly.go.kr/portal/openapi/openApiActKeyPage.do?tabIdx=1) из карточки. Нужные наборы: 본회의 회의록 (OO1X9P001017YF13038), 위원회 회의록 (OR137O001023MZ19321), вспомогательный 회의록별 상세정보 (OOWY4R001216HX11520). Структура закрытой формы, сроки одобрения и необходимость отдельного ключа на каждый набор не подтверждены — это не выдумано.
4. В запросе заменить sample на выданный KEY, задать Type=json, pIndex, pSize, DAE_NUM и CONF_DATE; для комитета при необходимости COMM_NAME или DEPT_CD. Для деталей использовать CONF_ID, реально возвращённый списком. Не отправлять ключ в чат и не записывать в репозиторий/URL-журналы. Текущий проверочный коннектор намеренно не принимает секретный ключ.
5. Ключ снимает ограничение sample для выборки метаданных в пределах выданных прав. Он **не добавляет поле полного текста речи**: дальнейшая цепочка — уникальный протокол → официальный PDF → подтверждение прав → проверка порядка колонок и границ говорящих → отдельные выступления с исходными идентификаторами. Такая текстовая цепочка ещё не реализована и не выдаётся за готовый сборщик.

### Команды

`python scripts/check_assembly.py` — показать конечный план без сети. `python scripts/check_assembly.py --execute` — проверить семь sample-запросов, используя уже сохранённые успешные ответы; повтор не загружает их снова. `python scripts/check_assembly.py --report` — офлайн обновить этот раздел и существующие README / QUALITY_REPORT / CHANGES. `python scripts/run_tests.py` — существующий набор тестов.
<!-- ASSEMBLY_API_20261101_END -->







<!-- MEDIA_AUDIT_START -->
## СМИ: ограниченный аудит 2026-10-30

Это проверка осуществимости, а не завершённый аудит десятилетнего архива. Исходные десять изданий оставлены без замены. Ноль найденных статей при отказе инструмента не доказывает отсутствие публикаций. Нет подтверждённого открытого API новостных статей у этих десяти СМИ. Точные серверные лимиты не установлены; локальная пауза 5,5 с не объявляется лимитом издателя. RSS не является историческим архивом или лицензией на полный текст.

| СМИ / страна издателя | Доступ / API, RSS, поиск | Историческое покрытие | Отобрано | Цитат сохранено | Новых заявлений | Ограничения / доказательства |
|---|---|---|---:|---:|---:|---|
| Yonhap / ROK | Библиография; повторное использование требует лицензии. RSS в официальном меню; HTML поиск; публичный API не подтверждён | Статья 2017 проверена; прежние записи 2019/2023/2025. Полнота 2015–2026 неизвестна | 1 | 0 | 0 | Прямые слова министра Kang наблюдались, не импортированы; URL/дата доступны, персональный автор неизвестен. [доказательство 1](https://en.yna.co.kr/view/AEN20200320005600315); [доказательство 2](https://en.yna.co.kr/view/AEN20171227005553315) |
| KBS / ROK | Библиография; проектный RSS отключён после robots Disallow. Официальный RSS прочитан web-инструментом, но прямой проектный клиент остановлен robots; HTML архив/поиск; публичный API статей не подтверждён | Выборочно 2015 (тематический материал), 2019/2023/2025; текущий RSS 2026. Непрерывность неизвестна | 4 | 0 | 0 | Прямая проба проекта 2026-10-30: robots Disallow для feed; запрос ленты НЕ выполнен. Ошибка записана в errors/fetches; обхода нет. RSS author KBS WORLD Radio — издатель, не персональный автор. Часто косвенная речь; цитаты не восстанавливать. [доказательство 1](https://world.kbs.co.kr/service/about_rss.htm?lang=e); [доказательство 2](https://world.kbs.co.kr/rss/rss_news.htm?id=Po&lang=e) |
| The Korea Herald / ROK | Официальный RSS: обнаружение метаданных; тексты требуют разрешения. RSS /rss/newsAll проверен напрямую проектным клиентом: 50 items, 1 кандидат Japan в заголовке; статьи не загружались; публичный API не подтверждён | Выборочно 2019/2025/2026; отдельная статья 2019 web 403; непрерывность неизвестна | 4 | 0 | 0 | Прямые слова Lee в 2025 наблюдались, byline Son Ji-hyoung; статья 2026 кредитует Yonhap. Запрет повторного использования без письменного разрешения; тексты/цитаты отключены. [доказательство 1](https://www.koreaherald.com/rss); [доказательство 2](https://members.heraldcorp.com/html/custom/copyright.php?lang=en) |
| Korea JoongAng Daily / ROK | Библиографическое обнаружение; статьи автоматически не собирать. HTML статьи/поиск; API/RSS не подтверждены | Выборочно 2015/2018/2023/2025; 2026 не проверен | 4 | 0 | 0 | Редакционная статья 2025 помечена generative AI translation + staff editing: не официальный перевод речи. Права на хранение цитат и полный архив не установлены. [доказательство 1](https://koreajoongangdaily.joins.com/news/2025-06-19/opinion/editorials/Korea-Japan-leaders-meet-ahead-of-60th-anniversary-of-diplomatic-ties/2333269) |
| The Korea Times / ROK | Библиография; RSS объявлен, загрузка не подтверждена. Официальная RSS страница публикует feed.koreatimes.co.kr; XML недоступен web-инструменту; API не подтверждён | Выборочно 2019/2023; полнота 2015–2026 не проверена | 2 | 0 | 0 | Повторное использование требует разрешения; сторонний news API не является официальным API газеты. Даты доступны, непроверенные авторы NULL. [доказательство 1](https://www.koreatimes.co.kr/rss); [доказательство 2](https://w3.koreatimes.co.kr/www2/common/copyrightpolicy_2022.asp) |
| Kyodo / Kyodo News+ / JPN | Ручная проверка / договорный канал. english.kyodonews.net: robots denial web-инструмента; публичный API/RSS не подтверждены | Конкретные статьи 2015–2026 в этом сеансе не проверены | 0 | 0 | 0 | 0 отобранных статей. Отказ инструмента не является наблюдением HTTP 403 сервера. Условия других подразделений Kyodo не переносятся на News+. [доказательство 1](https://english.kyodonews.net) |
| NHK World / JPN | Ручная проверка. nhk.jp: robots denial инструмента; новостной API/RSS текущего хоста не подтверждены | Доступность исторических статей 2015–2026 не установлена | 0 | 0 | 0 | School API не является API политических новостей. 0 статей: поля автора, даты и цитат не проверены; архив не объявляется отсутствующим. [доказательство 1](https://www.nhk.jp) |
| The Japan Times / JPN | Библиография; хранение текста требует разрешения. RSS упомянут официальной навигацией, рабочий endpoint не проверен; теги/поиск/Digital Archives; публичный API не подтверждён | Найдены URL 2016; проверены метаданные 2019/2023/2025. Часть страниц web 402; полнота 2015–2026 неизвестна | 4 | 0 | 0 | Прямые высказывания наблюдались, авторы двух статей установлены. Republishing требует разрешения; wire content имеет отдельные права. Новых цитат не сохранено. [доказательство 1](https://www.japantimes.co.jp/republishing/); [доказательство 2](https://www.japantimes.co.jp/about-us/sitemap/) |
| The Asahi Shimbun / JPN | Библиография открытых подразделений; платный Cross-Search отдельно. AJW: robots denial инструмента; Cross-Search документирован; открытый API/RSS не подтверждены | Cross-Search: английская БД с 2001, AJW с 2011, не все статьи; открытые GLOBE+/Tsuginojidai 2019/2023 | 2 | 0 | 0 | Подписка не разрешает выгрузку корпуса. GLOBE+ 2019 — Dong-A Ilbo: перевод/перепечатка, не слова редакции Asahi. Нельзя объявлять проверенным полный AJW. [доказательство 1](https://xsearch.asahi.com/help/eng/englishdb_naiyou01.html); [доказательство 2](https://xsearch.asahi.com/exp/jpn/library/rule.html); [доказательство 3](https://support.asahi.com/hc/ja/articles/1500002440362) |
| The Yomiuri Shimbun / The Japan News / JPN | Ручная проверка / договорный архив. yomiuri.co.jp и japannews.yomiuri.co.jp: robots denial инструмента; API/RSS не подтверждены | Конкретные исторические статьи 2015–2026 не проверены | 0 | 0 | 0 | 0 статей. Права/автор/цитаты/поиск архива требуют проверки с законным доступом; никакого обхода. [доказательство 1](https://www.yomiuri.co.jp); [доказательство 2](https://japannews.yomiuri.co.jp) |

### Поля и языковые версии

- **Yonhap**: ko/en; en не считается официальным переводом речи. Прямые слова министра Kang наблюдались, не импортированы; URL/дата доступны, персональный автор неизвестен.
- **KBS**: ko + World en/другие; редакционные версии. Прямая проба проекта 2026-10-30: robots Disallow для feed; запрос ленты НЕ выполнен. Ошибка записана в errors/fetches; обхода нет. RSS author KBS WORLD Radio — издатель, не персональный автор. Часто косвенная речь; цитаты не восстанавливать.
- **The Korea Herald**: en; есть ссылка на ko, эквивалентность статей не проверена. Прямые слова Lee в 2025 наблюдались, byline Son Ji-hyoung; статья 2026 кредитует Yonhap. Запрет повторного использования без письменного разрешения; тексты/цитаты отключены.
- **Korea JoongAng Daily**: en; отдельные переводы JoongAng Ilbo ko. Редакционная статья 2025 помечена generative AI translation + staff editing: не официальный перевод речи. Права на хранение цитат и полный архив не установлены.
- **The Korea Times**: en; оригинальный язык речи неизвестен. Повторное использование требует разрешения; сторонний news API не является официальным API газеты. Даты доступны, непроверенные авторы NULL.
- **Kyodo / Kyodo News+**: ja/en; эквивалентность не проверена. 0 отобранных статей. Отказ инструмента не является наблюдением HTTP 403 сервера. Условия других подразделений Kyodo не переносятся на News+.
- **NHK World**: ja/World en; версии не сопоставлены. School API не является API политических новостей. 0 статей: поля автора, даты и цитат не проверены; архив не объявляется отсутствующим.
- **The Japan Times**: en; журналистская версия слов политиков. Прямые высказывания наблюдались, авторы двух статей установлены. Republishing требует разрешения; wire content имеет отдельные права. Новых цитат не сохранено.
- **The Asahi Shimbun**: ja/AJW en; часть колонок ko/zh; соответствие версий не универсально. Подписка не разрешает выгрузку корпуса. GLOBE+ 2019 — Dong-A Ilbo: перевод/перепечатка, не слова редакции Asahi. Нельзя объявлять проверенным полный AJW.
- **The Yomiuri Shimbun / The Japan News**: ja/The Japan News en; эквивалентность не установлена. 0 статей. Права/автор/цитаты/поиск архива требуют проверки с законным доступом; никакого обхода.

### Проверенные запросы и происхождение

- `GET https://www.koreaherald.com/rss` → опубликованная ссылка `https://www.koreaherald.com/rss/newsAll`; XML прочитан web-инструментом. `GET https://world.kbs.co.kr/service/about_rss.htm?lang=e` → опубликованная ссылка `https://world.kbs.co.kr/rss/rss_news.htm?id=Po&lang=e`; лента прочитана web-инструментом.
- `GET https://feed.koreatimes.co.kr/k/foreignaffairs.xml` → web-инструмент не смог получить ответ; endpoint не включён. Ссылка опубликована на официальной RSS-странице, но успешная загрузка не заявляется.
- `GET https://www.koreaherald.com/article/10560185` → доступен; первая публикация 2025-08-23, обновление 2025-08-24. `GET https://www.koreaherald.com/article/2136020` → web 403; повторные попытки не выполнялись.
- Поисковые запросы: `site:world.kbs.co.kr Japan Korea summit 2023 2019`, `site:koreajoongangdaily.joins.com Japan Korea summit 2023 2015`, `site:japantimes.co.jp/news/2025/ "Ishiba" "Lee" summit`, `site:japantimes.co.jp/news/2019/ "South Korea" "export"`. Это запросы web-поиска, не выдуманные API издателей.

Все импортируемые записи с датой, URL и основанием даты находятся в `data/media_manifest.json`. Сохраняется библиография, а не исходный HTML статьи. Прямая RSS-проба проекта: KBS остановлен robots Disallow до запроса feed; канал отключён. Korea Herald: robots разрешил feed, получены 50 элементов, один заголовок-кандидат с Japan сохранён в discovery_results, статус unreviewed. Ни одна статья по ленте не загружалась; кандидат не входит в 21 импортированный документ. Ненаблюдавшийся персональный автор оставлен NULL; язык публикации не подставляется как язык оригинала речи. Страна издателя не определяет гражданство цитируемого политика.

В поиске есть кооперация/нормализация и спорные темы у обеих стран издателей. Это целевая подборка, не сбалансированная выборка политической риторики. Подтверждённых новых депутатских высказываний нет; парламентский пробел сохранён. Тональность статей не кодировалась, веса не назначались. Наблюдавшиеся цитаты и пересказы не превращены в новые события. Права для повторного использования цитат не установлены; автоматическое извлечение цитат выключено. Все новые документы остаются в очереди проверки.
<!-- MEDIA_AUDIT_END -->

<!-- EXPANSION_START -->
## Расширение корпуса: новые подтверждения и ограничения

Прежние аудиты десяти СМИ, 50 заявлений и 164 пар не повторялись. Новые пробы касались права на собственные тексты МИД, архива стенограмм РК и документированных архивов GDELT.

- [Политика МИД РК](https://www.mofa.go.kr/www/wpge/m_4190/contents.do) получена напрямую через клиент: для собственных произведений МИД по умолчанию действует KOGL Type 1; специальные условия материала имеют приоритет. Новый сбор сохраняет только собственную прозу пресс-релиза с указанием МИД, даты, заголовка и URL; вложения, фото и чужие материалы не включаются. Отдельные ограничения/сторонняя атрибуция оставляют материал фрагментом. Это условное правило, не разрешение на всё содержимое домена.
- [Архив парламента РК](https://record.assembly.go.kr/assembly/mnts/minutes/search.do?schwrd=%EC%A7%80%EB%B0%A9) и реально обнаруженная страница [XML viewer 55170](https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id=55170&type=summary) доступны напрямую (web-инструмент давал ошибку). HTML сам по себе не подтвердил надёжную привязку всех реплик, полный экспорт и условия корпусного хранения. Массовый импорт стенограмм РК не включён; платные API/ключи не использовались.
- [NDL API](https://kokkai.ndl.go.jp/api.html), раздел 4: права отдельных выступающих сохраняются; новый сбор допускает только полное короткое предложение до 90 символов, буквальное соответствие источнику и оригинальные speechID. Выборка с `any=日韓`, без фильтра министерской должности, включает разные роли; страницы по 20 API-записей сортируются по новой дате. Не каждый ответ содержит подходящую короткую цитату. Это не репрезентативная частота и не лицензия на полные речи.
- [GDELT raw data](https://gdeltproject.org/data.html), [официальное описание файлов](https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/), [Events/Mentions codebook](https://data.gdeltproject.org/documentation/GDELT-Event_Codebook-V2.0.pdf). Успешно проверены интервалы 2015-12-28 12:00, 2019-08-02 00:00, 2020-06-15 12:00, 2025-08-23 12:00 UTC. Они не покрывают все дни и годы. Отсутствие пары в одном файле не означает отсутствие событий за год. Оригинальные ZIP и хэши сохранены в существующем data/raw; статьи по SOURCEURL/MentionIdentifier не загружались.
- GKG за 2015-12-28 12:00: первый запрос остановлен локальным пределом 4 МБ, не серверным запретом. Один повтор с отдельным пределом 16 МБ получил архив 7 049 874 байта. Общий лимит HTML остался 4 МБ; распаковка ограничена 64 МБ. Совместные географические упоминания KS/JA хранятся отдельно от событий KOR/JPN. Полные тексты СМИ из GKG не извлекаются.

Для раздельного GDELT-хранения выполнена аддитивная миграция 3→4. Резервная копия: `data/backups/pre-schema-004.sqlite3`; новые таблицы gdelt_events/gdelt_mentions/gdelt_gkg. Основная база прежняя; новая параллельная рабочая база не создавалась. Статистика типов не суммируется в показатель качества.
<!-- EXPANSION_END -->

<!-- ASSEMBLY_PDF_20261101 -->
## Парламентские PDF: переход к внутреннему извлечению

Использованы сохранённые публичные ссылки из ранее подтверждённых методов; API не переаудировался. По явному запросу пользователя полные тексты теперь сохраняются для внутреннего исследования, без утверждения права публикации. Проверены 6 PDF; внутренние сырые файлы имеют SHA-256 и URL, протоколы связаны с CONF_ID и CONFER_NUM. Период отбора остаётся 2015-01-01–2026-10-31. Парсер читает текстовый слой; OCR не используется. Политика доступа прежняя: robots/TLS, минимум 5,5 секунды, размер до 4 МБ, остановка хоста на 401/403/429. Разрешение скачивания и внутреннего хранения не выдаётся за разрешение публичной перепубликации. Полные тексты и PDF-пути исключены из JSONL и существующей таблицы просмотра. Подробная статистика, ограничения сегментации и идентичности — в docs/QUALITY_REPORT.md.
<!-- ASSEMBLY_PDF_20261101_END -->

<!-- DRI_V01_START -->
## Источники в аналитике DRI v0.1

Новых обращений к корпусным источникам, их повторного аудита и сбора нет. Существующие ограничения публикации сохраняются: аналитические JSONL содержат идентификаторы, позиции, хэши и счётчики, без исходных текстов или списка слов, восстанавливающего внутренний документ. GDELT и библиография отделены от речевого расчёта. Ни новостной пересказ, ни полный многоголосый протокол не превращаются в самостоятельное заявление. Технические зависимости проверены по первичным описаниям: [Kiwi](https://pypi.org/project/kiwipiepy/0.22.2/), [Janome/IPADIC](https://janome.mocobeta.dev/en/), [Matplotlib](https://pypi.org/project/matplotlib/3.10.7/). Морфологические модели используются локально для сегментации, а не для прогнозирования или LLM-разметки. Установлены только в .venv проекта, версии и словарные файлы фиксированы в manifest/lock.
<!-- DRI_V01_END -->
