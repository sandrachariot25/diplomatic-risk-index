# Качество, дедупликация и покрытие DRI

Сформировано: 2026-11-01T11:46:13.102463+00:00. Основная БД: `data/dri.sqlite3`.

Документы: **1444**; уникальные записи заявлений: **1050**; цитаты: **1070**.
Ручную проверку прошли: **0**. Цель 100–200: **не достигнута**.
Пилот не является полным историческим корпусом. Нули означают отсутствие собранных записей, а не отсутствие дипломатических событий.

Целостность SQLite: `ok`; ошибок внешних ключей: 0; ошибок raw-хэшей: 0.
Отсутствует дата выступления: 93; дата публикации: 957; личное имя: 92; язык оригинала: 90.
Неизвестные поля оставлены NULL. Дата публикации не объявляется датой выступления. Должность — наблюдаемая на дату источника, без подстановки по имени.

## Покрытие по годам, государствам и типам источников

В ячейке **документы / уникальные заявления**. Год документа — публикация, а при её отсутствии — явно известная дата события; год заявления — произнесение, при неизвестной дате — публикация (поля остаются раздельными).
Страна документа определяется по связанному заявлению, а без атрибуции — по явно указанной области country_scope или стране издателя; это не доказательство выступления политика этой страны.
Одно заявление с первичными и вторичными источниками входит в оба столбца: их суммы нельзя считать общим числом событий.

| Год | ROK первичные | ROK вторичные | JPN первичные | JPN вторичные |
|---|---:|---:|---:|---:|
| 2015 | 23 / 10 | 1 / 0 | 66 / 66 | 0 / 0 |
| 2016 | 73 / 8 | 0 / 0 | 60 / 60 | 0 / 0 |
| 2017 | 68 / 12 | 1 / 0 | 73 / 73 | 0 / 0 |
| 2018 | 49 / 9 | 0 / 0 | 56 / 56 | 0 / 0 |
| 2019 | 65 / 17 | 5 / 0 | 72 / 72 | 2 / 0 |
| 2020 | 39 / 10 | 0 / 0 | 42 / 42 | 0 / 0 |
| 2021 | 31 / 8 | 0 / 0 | 47 / 47 | 0 / 0 |
| 2022 | 11 / 8 | 0 / 0 | 104 / 104 | 0 / 0 |
| 2023 | 19 / 6 | 7 / 0 | 167 / 167 | 2 / 0 |
| 2024 | 33 / 7 | 0 / 0 | 107 / 107 | 0 / 0 |
| 2025 | 43 / 9 | 5 / 0 | 85 / 85 | 2 / 0 |
| 2026 | 25 / 7 | 1 / 0 | 60 / 60 | 0 / 0 |

## Источники и языки документов

| Источник | Тип | Язык публикации | Документы |
|---|---|---|---:|
| ap | secondary | en | 2 |
| asahi | secondary | ja | 2 |
| assembly_kr | primary | ko | 2 |
| japan_times | secondary | en | 4 |
| joongang | secondary | en | 4 |
| kbs | secondary | en | 4 |
| kokkai_jp | primary | ja | 939 |
| korea_government_kr | primary | ko | 5 |
| korea_herald | secondary | en | 4 |
| korea_times | secondary | en | 2 |
| mofa_kr | primary | en | 472 |
| yonhap | secondary | en | 4 |

## Темы и статус заявлений

| Тема | Статус | Число |
|---|---|---:|
| historical_disputes | needs_review | 92 |
| historical_disputes | needs_review_nonpolitical_witness | 2 |
| historical_disputes | source_text_verified | 6 |
| territorial_disputes | needs_review | 37 |
| trade_economy | needs_review | 52 |
| trade_economy | source_verified | 1 |
| diplomatic_contacts | needs_review | 403 |
| diplomatic_contacts | source_text_verified | 10 |
| diplomatic_contacts | source_verified | 3 |
| security | needs_review | 352 |
| regional_cooperation | needs_review | 11 |
| regional_cooperation | source_verified | 1 |
| normalization_deescalation | needs_review | 34 |
| unclassified | needs_review | 46 |

Тематические метки получены по явным словам в заголовке/сохранённом фрагменте, это предварительная разметка. Отдельная нормализация/деэскалация остаётся пробелом этой выборки: две узкие проверки Kokkai не дали новых подходящих реплик после фильтрации. Нулевое число не означает отсутствие таких заявлений в истории.

## Запуски

| Запуск | Статус | Обнаружено | Обработано | Документов добавлено | Заявлений добавлено | Дубли | Возможные совпадения | Ошибки доступа | Прочие ошибки |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy-statement-backfill | completed | 2 | 2 | 0 | 2 | 2 | 0 | 0 | 0 |
| kokkai-pilot-2015 | completed | 6 | 6 | 6 | 6 | 0 | 0 | 0 | 0 |
| kokkai-pilot-2016-2026 | completed | 65 | 65 | 65 | 65 | 0 | 0 | 0 | 0 |
| secondary-metadata-catalog | completed | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| korea-discovery-recovered-from-logs | interrupted_recovered | 490 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| official-pilot-2015-2026 | completed | 93 | 93 | 93 | 88 | 0 | 162 | 0 | 0 |
| kokkai-normalization-verification | completed | 71 | 71 | 0 | 0 | 213 | 0 | 0 | 0 |
| offline-idempotence-verification | completed | 173 | 173 | 0 | 0 | 499 | 0 | 0 | 0 |
| kokkai-theme-normalization | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| kokkai-theme-regional | completed | 2 | 2 | 2 | 2 | 0 | 2 | 0 | 0 |
| kokkai-theme-normalization-2018 | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| offline-audit-50-v1 | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| media-bibliography-2026-10-30-preservation | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| media-bibliography-2026-10-30 | completed | 21 | 21 | 21 | 0 | 0 | 0 | 0 | 0 |
| media-bibliography-2026-10-30-repeat | completed | 21 | 21 | 0 | 0 | 21 | 0 | 0 | 0 |
| media-bibliography-2026-10-30-validated | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-baseline | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-02cea2c5413bb2f4 | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-02cea2c5413bb2f4-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-e84e01739dd600c0 | completed | 20 | 19 | 18 | 0 | 1 | 0 | 0 | 0 |
| expansion-2015-2026-queue-e84e01739dd600c0-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-f2e842409467e0ca | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-f2e842409467e0ca-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-ddb3df8d88bdb4e5 | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| expansion-gdelt-archives-4775dfab8f77e0db | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-gdelt-archives-4775dfab8f77e0db-validation | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-ddb3df8d88bdb4e5-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-521e1fd5256d0933 | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-521e1fd5256d0933-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-c6521a0577b8475a | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-gdelt-archives-e8f7e9f09a38433d | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-gdelt-archives-e8f7e9f09a38433d-validation | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-c6521a0577b8475a-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-4c306ee3c00da32b | completed | 20 | 19 | 19 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-4c306ee3c00da32b-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-69a7e38f3ffb1a6a | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-69a7e38f3ffb1a6a-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-df44101d45c48173 | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-df44101d45c48173-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-5763c1730276a3ec | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-5763c1730276a3ec-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-2688fefdd953b1e8 | completed | 20 | 19 | 19 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-1 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-21 | completed | 14 | 14 | 14 | 14 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-41 | completed | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-2688fefdd953b1e8-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-4723ab0ec8c1c6f8 | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-61 | completed | 12 | 12 | 12 | 12 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-81 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2015-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-1 | completed | 9 | 9 | 9 | 9 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-21 | completed | 16 | 16 | 16 | 16 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-41 | completed | 6 | 6 | 6 | 6 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-61 | completed | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-81 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2016-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-1 | completed | 14 | 14 | 14 | 14 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2017-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-21 | completed | 15 | 15 | 15 | 15 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-41 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-61 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-81 | completed | 16 | 16 | 16 | 16 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-4723ab0ec8c1c6f8-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-b939dde2e18225b6 | completed | 20 | 19 | 19 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2017-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-1 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-21 | completed | 12 | 12 | 12 | 12 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2018-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-41 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-61 | completed | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2018-start-81 | completed | 12 | 12 | 12 | 12 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2018-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-1 | completed | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-21 | completed | 9 | 9 | 9 | 9 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-41 | completed | 14 | 14 | 14 | 14 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2019-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-61 | completed | 17 | 17 | 17 | 17 | 0 | 12 | 0 | 0 |
| expansion-kokkai-2019-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2019-start-81 | completed | 13 | 13 | 13 | 13 | 0 | 4 | 0 | 0 |
| expansion-kokkai-2019-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2020-start-1 | completed | 14 | 14 | 14 | 14 | 0 | 10 | 0 | 0 |
| expansion-kokkai-2020-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2020-start-21 | completed | 9 | 9 | 9 | 9 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-b939dde2e18225b6-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-ae2fcfd7a417fd8f | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2020-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2020-start-41 | completed | 9 | 9 | 9 | 9 | 0 | 2 | 0 | 0 |
| expansion-2015-2026-queue-ae2fcfd7a417fd8f-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-final-offline-validation | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-851b796036872105 | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| continuation-2026-11-01-baseline | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2020-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2020-start-61 | completed | 4 | 4 | 4 | 4 | 0 | 12 | 0 | 0 |
| expansion-kokkai-2020-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-1 | completed | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-21 | completed | 5 | 5 | 5 | 5 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-41 | completed | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-61 | completed | 16 | 16 | 16 | 16 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2021-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2021-start-81 | completed | 7 | 7 | 7 | 7 | 0 | 12 | 0 | 0 |
| expansion-kokkai-2021-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-1 | completed | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-21 | completed | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-851b796036872105-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-10b6c5b9ee13777d | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-41 | completed | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-61 | completed | 12 | 12 | 12 | 12 | 0 | 18 | 0 | 0 |
| expansion-kokkai-2022-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-81 | completed | 12 | 12 | 12 | 12 | 0 | 14 | 0 | 0 |
| expansion-kokkai-2022-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-1 | completed | 9 | 9 | 9 | 9 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2023-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-21 | completed | 14 | 14 | 14 | 14 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2023-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-41 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-61 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-81 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-1 | completed | 6 | 6 | 6 | 6 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2024-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-21 | completed | 12 | 12 | 12 | 12 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2024-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-41 | completed | 15 | 15 | 15 | 15 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-10b6c5b9ee13777d-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-b64825735dfa3556 | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-61 | completed | 13 | 13 | 13 | 13 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2024-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-81 | completed | 9 | 9 | 9 | 9 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-101 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-101-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-121 | completed | 9 | 9 | 9 | 9 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-121-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-141 | completed | 12 | 12 | 12 | 12 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2024-start-141-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2024-start-161 | completed | 13 | 13 | 13 | 13 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2024-start-161-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-1 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-21 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-41 | completed | 14 | 14 | 14 | 14 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-61 | completed | 13 | 13 | 13 | 13 | 0 | 2 | 0 | 0 |
| expansion-2015-2026-queue-b64825735dfa3556-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-56fffa5c0c3c151b | completed | 20 | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-81 | completed | 7 | 7 | 7 | 7 | 0 | 4 | 0 | 0 |
| expansion-kokkai-2025-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-1 | completed | 10 | 10 | 10 | 10 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-1-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-21 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-21-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-41 | completed | 12 | 12 | 12 | 12 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2026-start-41-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-61 | completed | 12 | 12 | 12 | 12 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-61-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2026-start-81 | completed | 9 | 9 | 9 | 9 | 0 | 22 | 0 | 0 |
| expansion-kokkai-2026-start-81-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-56fffa5c0c3c151b-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-bdad69962034292c | completed | 20 | 18 | 18 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-101 | completed | 11 | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-101-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-121 | completed | 15 | 15 | 15 | 15 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2022-start-121-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-141 | completed | 14 | 14 | 14 | 14 | 0 | 6 | 0 | 0 |
| expansion-kokkai-2022-start-141-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2022-start-161 | completed | 5 | 5 | 5 | 5 | 0 | 14 | 0 | 0 |
| expansion-kokkai-2022-start-161-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-101 | completed | 14 | 14 | 14 | 14 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-101-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-121 | completed | 6 | 6 | 6 | 6 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-121-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-141 | completed | 13 | 13 | 13 | 13 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-141-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-161 | completed | 15 | 15 | 15 | 15 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-161-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-181 | completed | 12 | 12 | 12 | 12 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-181-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-101 | completed | 13 | 13 | 13 | 13 | 0 | 4 | 0 | 0 |
| expansion-kokkai-2025-start-101-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2025-start-121 | completed | 10 | 10 | 10 | 10 | 0 | 4 | 0 | 0 |
| expansion-kokkai-2025-start-121-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-bdad69962034292c-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-3e59ebb59c90340e | completed | 17 | 16 | 16 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-201 | completed | 14 | 14 | 14 | 14 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-201-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-221 | completed | 13 | 13 | 13 | 13 | 0 | 4 | 0 | 0 |
| expansion-kokkai-2023-start-221-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-241 | completed | 13 | 13 | 13 | 13 | 0 | 10 | 0 | 0 |
| expansion-kokkai-2023-start-241-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-kokkai-2023-start-261 | completed | 8 | 8 | 8 | 8 | 0 | 2 | 0 | 0 |
| expansion-kokkai-2023-start-261-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| expansion-2015-2026-queue-3e59ebb59c90340e-checkpoint | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| domestic-20261101 | completed | 4 | 4 | 4 | 4 | 0 | 0 | 0 | 0 |
| domestic-20261101-earlier | completed | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| assembly-api-20261101 | completed | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| assembly-pdf-pilot-20261101-v3 | completed | 3 | 3 | 2 | 16 | 0 | 0 | 0 | 0 |
| assembly-pdf-pilot-20261101-v4 | completed | 3 | 3 | 0 | 0 | 54 | 0 | 0 | 0 |
| assembly-pdf-pilot-20261101-v4-recent | completed | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |

## Правила интерпретации

- Документ — публикация; заявление — отдельный подтверждаемый эпизод выступления/институционального комментария; цитата — дословный сохранённый фрагмент опубликованной версии.
- Новая публикация об известном заявлении добавляется в statement_sources, а не создаёт новый сигнал, если идентичность выступления подтверждена явным event_key.
- Сходство и даже точный текст в другую дату/другом выступлении дают possible_duplicate, сохраняя обе записи. Межъязыковое объединение только по явным доказательствам общего выступления; официальный перевод связывается отдельно.
- Институциональные комментарии МИД допустимы с NULL личным именем; они остаются needs_review. Журналистский пересказ сам по себе не превращается в прямую цитату политика.
- Надёжность источника — описательная категория из config/sources.json. Весов, индексов, вероятностей и LLM нет.
- Два исходных полных текста оставлены без изменения как legacy_unreviewed. Новые тексты СМИ не сохраняются; для новых корейских документов оставлены только короткие исследовательские фрагменты. Число 25 слов не является универсальным юридическим разрешением.

Результаты автотестов: `docs/TEST_RESULTS.txt`. Таблица ручной проверки: `docs/REVIEW_TABLE.html`.

## Офлайн-аудит: стратифицированная выборка 50

Этот раздел описывает прежний офлайн-аудит исходных 173 документов и 163 заявлений; новые библиографические записи СМИ в него не входят. Институциональные признаки описательные: значимость парламентской, партийной или внешнеполитической риторики не ранжируется.

**Ключевое ограничение прежнего сбора:** 73 японские записи — выступления представителей исполнительной власти на парламентской площадке. Это не выборка независимых депутатских, партийных или оппозиционных речей. Фильтр `speakerPosition=大臣` включал также чиновников `大臣官房`. Орган выступающего и место выступления теперь разделены. В будущем фильтр должности необязателен; текущий корпус этим не расширялся.

Выборка: **50** записей, **25 ROK + 25 JPN**. Сначала взята одна запись из каждой пары год–страна (24 страты), затем добраны редкие темы, типы институтов и роли при сохранении баланса стран. Порядок воспроизводим по отпечатку event_key/ID. Это целевая стратифицированная проверка, не случайная репрезентативная оценка частоты ошибок в генеральной совокупности.
При неизвестной дате речи год страты определяется по публикации; дата речи остаётся NULL. Все 50 заявлений имеют первичные источники: в пяти записях СМИ нет выделенных заявлений, поэтому вторичная страта заявлений отсутствует.

Оценены только сохранённые фрагменты и контекст записи. 50 заметок — разбор агентом, **не независимая человеческая верификация и не сверка полного оригинала**. Остальные 113 оценены консервативными правилами с тем же ограничением. Исходный verification_status не повышен.

| Год | В выборке ROK | В выборке JPN |
|---|---:|---:|
| 2015 | 2 | 3 |
| 2016 | 3 | 1 |
| 2017 | 3 | 1 |
| 2018 | 3 | 1 |
| 2019 | 2 | 3 |
| 2020 | 2 | 2 |
| 2021 | 1 | 3 |
| 2022 | 2 | 2 |
| 2023 | 3 | 1 |
| 2024 | 1 | 3 |
| 2025 | 2 | 2 |
| 2026 | 1 | 3 |

### Релевантность: оценка фрагмента, не исключение записи

Адресат/направление в исходной базе — прежняя аннотация. Категории ниже не доказывают, что каждое упоминание Кореи было адресованным ей политическим сигналом. Парламентский контекст не является основанием считать запись нерелевантной. Даже incidental_reference и third_country_only сохранены, не исключены из будущей проверки.

| Категория | В выборке 50 | Во всём корпусе 163 |
|---|---:|---:|
| Прямое требование/протест другой стороне (`direct_address`) | 11 | 35 |
| Официальная двусторонняя коммуникация без установленного прямого обращения (`official_bilateral`) | 14 | 55 |
| Внутриполитическая речь о двусторонних отношениях (`domestic_bilateral`) | 7 | 34 |
| Региональная безопасность и явная координация сторон (`regional_security`) | 1 | 4 |
| Региональное сотрудничество вне доказанной военной тематики (`regional_cooperation`) | 4 | 4 |
| В сохранённом фрагменте — третьи страны без явной двусторонней связи (`third_country_only`) | 3 | 5 |
| Случайное упоминание / сравнение, связь с политикой не показана (`incidental_reference`) | 5 | 5 |
| Контекста недостаточно (`indeterminate`) | 5 | 21 |

Примеры проблем: ID 62 называет бейсбольные команды; ID 70 обсуждает неизвестные выступающему корейские guidelines; ID 42 в сохранённой части отвечает о Северных территориях, хотя Корея есть в перечне вопросов. ID 136 обрывается на expresses, ID 125 — на that the; политическая позиция не восстанавливалась по догадке. ID 154/74 требуют уточнения темы от security к территориальному спору; ID 47 использует название соглашения с economic, но обсуждает исторические претензии. Предложения исправлений хранятся отдельно, прежние темы/цитаты не перезаписаны.

### Представленность институтов: автор позиции и площадка

| Тип | Заявления по органу выступающего | Заявления на такой площадке | Документы по органу |
|---|---:|---:|---:|
| parliament | 175 | 955 | 163 |
| foreign_ministry | 402 | 0 | 783 |
| government | 176 | 0 | 176 |
| head_of_state_administration | 5 | 0 | 5 |
| political_party | 0 | 0 | 0 |
| other | 2 | 0 | 2 |
| unknown | 290 | 95 | 316 |

Площадка неизвестна для 90 официальных публикаций МИД; не подставлена «пресс-конференция». Ноль parliament в столбце автора означает пробел текущей выборки рядовых депутатов/комитетских представителей, а не низкую важность парламента. Две речи в разных палатах одного премьера не превращают его в двух разных политических акторов. Пять несвязанных публикаций МИД учтены по издателю; пять библиографических записей СМИ — unknown по органу автора позиции. Если один документ в будущем содержит несколько выступающих из разных институтов, он может входить более чем в одну группу документов.

| Категория выступающего | Заявления |
|---|---:|
| cabinet_member | 303 |
| executive_official | 80 |
| head_of_government | 86 |
| institutional_spokesperson | 90 |
| legislator | 14 |
| nonpolitical_witness | 2 |
| parliamentary_group_member_role_unspecified | 161 |
| unknown | 314 |

### Даты, имена, политическая принадлежность и направленность

- Дата произнесения установлена у 957/1050 (91.1%); публикация не заменяет её.
- Личное имя установлено у 958/1050 (91.2%). Безымянные институциональные заявления сохранены.
- Статус правящая партия/оппозиция на дату речи: 0/1050. Нельзя выводить его из имени политика, министерской должности или нынешнего состава правительства.
- В прежних 163 записях партийная принадлежность не была установлена: старое speakerGroup не сохранялось. Новые записи NDL сохраняют сообщённую парламентскую группу на дату речи; это не подстановка статуса власти/оппозиции и не переаудит старых записей.
- Проверенная тональность: positive 0, negative 0, neutral 0; unknown 163. Unknown не означает нейтральность. Явные слова protest/congratulates сами по себе не являются проверенной оценкой всей речи.

### Завершённая проверка исходных 164 предполагаемых совпадений (не повторялась)

Это **82 пары заявлений + 82 пары цитат**, не 164 дополнительных заявления. Проверены идентификаторы, даты, контекст, язык, буквальное совпадение и связи источников. Все исходные пары сохраняют статус possible_duplicate; слияний и удалений нет.

| Структурный результат | Пары |
|---|---:|
| different_parliamentary_speech_ids_keep_separate | 2 |
| different_publications_speech_identity_unconfirmed | 162 |

162 пары относятся к разным публикациям, но дата произнесения неизвестна: нельзя объявлять их ни доказанным повтором одной речи, ни доказанными разными речами только по дате публикации. Две пары — заявления/цитаты ID 162 и 163: одинаковый фрагмент речи премьера в разных палатах 2024-10-04, разные speechID и контексты; сохраняются отдельно.
Подтверждённые перепечатки одной цитаты несколькими СМИ, повтор одного speechID и официально связанные языковые версии среди этих пар не обнаружены. Это ограничение имеющихся связей и фрагментов: по одной короткой цитате нельзя доказать, что переводов или перепечаток нигде нет.

### Готовность к будущей проверке последовательности сигналов

Представление `signal_timeline` хранит раздельно statement_date, published_date, first_observed_by_collector_at, тип органа, площадку, роль, принадлежность/статус на дату, контекст, scope позиции и результаты аудита. Пока только подготовлены поля: временные лаги, прогнозная значимость, причинность и индекс не рассчитывались.
Парламентская риторика не получает меньший вес. Но текущий отбор исполнительных выступающих, отсутствие независимых депутатов/партийных речей, неизвестные даты 90 высказываний, неизвестная партийность, короткие незавершённые цитаты, смещение японской годовой выборки к концу года и нерешённые возможные дубли мешают проверке гипотезы. Нужны как эпизоды обострения, так и контрольные периоды без него; текущая выборка их не устанавливает.
Недостаточно представлены 2015 год РОК (4 записи) и отдельные годы с 5–6 записями; формального баланса достаточно для аудита, недостаточно для ряда ежедневной риторики. Отсутствие записей не означает отсутствие дипломатической активности.
163 — технически уникальные записи по идентификаторам, а не доказанные 163 независимых дипломатических сигнала. Окончательная канонизация выступлений и оценка соответствия адресату остаются предметом проверки.

Оригинальные доменные записи сохранены: `True`. Независимой ручной верификации требуют **1050** записей; проверка 50 фрагментов не переводит их автоматически в verified. Все 164 пары доступны в основной таблице проверки.

<!-- MEDIA_AUDIT_START -->
## Библиографический пилот СМИ

Ниже зафиксирован результат предшествующего пилота СМИ; текущий объём корпуса указан в начале отчёта и разделе расширения.
Исходные документы, заявления, цитаты и связи сохранены по хэшам строк каждого доменного набора. Это проверка сохранности перед текущим импортом; прежняя выборка 50 не пересматривалась. Схема базы не менялась.

| Сущность | До | После | Прирост |
|---|---:|---:|---:|
| documents | 173 | 194 | 21 |
| duplicate_candidates | 164 | 164 | 0 |
| quote_sources | 163 | 163 | 0 |
| quotes | 163 | 163 | 0 |
| sources | 20 | 22 | 2 |
| statement_sources | 163 | 163 | 0 |
| statements | 163 | 163 | 0 |

Набор: 21 публикация; ROK 15, JPN 6. Новых прямых цитат и заявлений: 0. Предел 100 — потолок, не целевое число. Полное покрытие 2015–2026 и баланс стран не достигнуты.

Повторный **фактический** вызов ingestion для всего набора: `{"documents": 194, "duplicate_candidates": 164, "quote_sources": 163, "quotes": 163, "sources": 22, "statement_sources": 163, "statements": 163}` → `{"documents": 194, "duplicate_candidates": 164, "quote_sources": 163, "quotes": 163, "sources": 22, "statement_sources": 163, "statements": 163}`. Уникальные сущности и связи не выросли. Сетевых запросов при импорте: 0. Совпадения не объединялись и не удалялись.
<!-- MEDIA_AUDIT_END -->

<!-- EXPANSION_START -->
## Расширение к контрольной отметке 2 000: состав и полнота текста

Единица ниже — уникальный документ источника. Полный текст отчёта о встрече пригоден как кандидат для частот слов/тем публикаций, но не становится политическим заявлением, событием или независимым дипломатическим сигналом. Репрезентативность и корректность направления требуют проверки; полноценный частотный анализ политической риторики пока не обеспечен.

| Показатель | До этапа | После | Прирост |
|---|---:|---:|---:|
| documents | 194 | 1444 | 1250 |
| statements | 163 | 1050 | 887 |
| quotes | 163 | 1070 | 907 |
| discovery_results | 491 | 496 | 5 |

| Раздельный результат | Новых |
|---|---:|
| Полные опубликованные тексты | 348 |
| Ограниченные фрагменты документов | 902 |
| Дословные цитаты, подтверждённые по источнику (source_text_verified/verified) | 902 |
| Все новые записи цитат (включая needs_review) | 907 |
| Новые технически уникальные записи заявлений | 887 |
| Машинные записи Events GDELT | 22 |
| Медийные упоминания GDELT Mentions | 28 |
| GKG совместные упоминания стран | 60 |
| Только метаданные | 0 |
| Кандидаты для частот текста документов, не частот высказываний | 348 |
| Из записей заявлений: политические кандидаты, ещё needs_review | 885 |
| Из записей заявлений: явно неполитические эксперты, исключены из политических частот | 2 |
| Проверенные новые наблюдения для частот политической риторики | 0 |

Цель 2 000 не достигнута. Простые URL, discovery_results, библиография, фрагменты и GDELT не добавляются к количеству полных текстов. В этот показатель не включены старые legacy-тексты с нерешёнными правами и прежние короткие выдержки. Слова cooperation/protest и тема не заменяют верифицированную тональность; тональность не кодировалась.
source_text_verified подтверждает буквальное соответствие цитаты API и его атрибуции; статус заявления остаётся needs_review. Это не независимая проверка политического смысла, направленности и полноты выступления.
Контейнеры цитат уже входят в число фрагментных документов; документы, связанные заявления и цитаты — пересекающиеся сущности. Их нельзя складывать как независимые наблюдения. Неполитические эксперты сохранены с отдельной категорией, не удалены и не приписаны правительству.

### Новые документы: каждый год, государство издателя и тип источника

| Год | РК primary: полные / фрагменты / metadata | РК secondary | Япония primary | Япония secondary | GDELT events / mentions / GKG |
|---|---:|---:|---:|---:|---:|
| 2015 | 19 / 0 / 0 | 0 / 0 / 0 | 0 / 60 / 0 | 0 / 0 / 0 | 16 / 22 / 60 |
| 2016 | 60 / 5 / 0 | 0 / 0 / 0 | 0 / 54 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2017 | 47 / 9 / 0 | 0 / 0 / 0 | 0 / 67 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2018 | 26 / 14 / 0 | 0 / 0 / 0 | 0 / 50 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2019 | 56 / 2 / 0 | 0 / 0 / 0 | 0 / 66 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2020 | 29 / 1 / 0 | 0 / 0 / 0 | 0 / 36 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2021 | 23 / 0 / 0 | 0 / 0 / 0 | 0 / 41 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2022 | 1 / 0 / 0 | 0 / 0 / 0 | 0 / 98 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2023 | 10 / 1 / 0 | 0 / 0 / 0 | 0 / 162 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2024 | 23 / 2 / 0 | 0 / 0 / 0 | 0 / 99 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2025 | 35 / 1 / 0 | 0 / 0 / 0 | 0 / 79 / 0 | 0 / 0 / 0 | 6 / 6 / 0 |
| 2026 | 19 / 1 / 0 | 0 / 0 / 0 | 0 / 54 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

GDELT учитывается по году события (Events) и по времени регистрации (Mentions/GKG); дата регистрации не объявляется датой публикации. Коды KOR/JPN — атрибуты акторов машинного извлечения; PRK исключён. В GKG KS/JA — географические совместные упоминания, не направленное взаимодействие. Несколько GlobalEventID могут описывать один реальный эпизод: автоматического объединения или объявления независимости не было.

| Год | Actor1 → Actor2 | Events | Mentions связанных событий |
|---|---|---:|---:|
| 2015 | ROK → JPN | 10 | 16 |
| 2015 | JPN → ROK | 6 | 6 |
| 2016 | ROK → JPN | 0 | 0 |
| 2016 | JPN → ROK | 0 | 0 |
| 2017 | ROK → JPN | 0 | 0 |
| 2017 | JPN → ROK | 0 | 0 |
| 2018 | ROK → JPN | 0 | 0 |
| 2018 | JPN → ROK | 0 | 0 |
| 2019 | ROK → JPN | 0 | 0 |
| 2019 | JPN → ROK | 0 | 0 |
| 2020 | ROK → JPN | 0 | 0 |
| 2020 | JPN → ROK | 0 | 0 |
| 2021 | ROK → JPN | 0 | 0 |
| 2021 | JPN → ROK | 0 | 0 |
| 2022 | ROK → JPN | 0 | 0 |
| 2022 | JPN → ROK | 0 | 0 |
| 2023 | ROK → JPN | 0 | 0 |
| 2023 | JPN → ROK | 0 | 0 |
| 2024 | ROK → JPN | 0 | 0 |
| 2024 | JPN → ROK | 0 | 0 |
| 2025 | ROK → JPN | 6 | 6 |
| 2025 | JPN → ROK | 0 | 0 |
| 2026 | ROK → JPN | 0 | 0 |
| 2026 | JPN → ROK | 0 | 0 |

### Направления и тематика

Страна издателя РК и Japan как тема не доказывают, что все слова принадлежат корейскому политику или обращены непосредственно Японии. Актор/адресат для новых отчётов не домысливаются; гражданство участников из имени не выводится. Отбор требует явной РК и Японии; КНДР сама по себе не удовлетворяет фильтру.

| Тема по текстовым признакам, не проверенная тональность | Документы |
|---|---:|
| security | 413 |
| diplomatic_contacts | 399 |
| historical_disputes | 211 |
| trade_economy | 101 |
| normalization_deescalation | 48 |
| regional_cooperation | 45 |
| territorial_disputes | 20 |
| unclassified | 13 |

### Заполненность исходных полей новых документов

| Поле | Не установлено |
|---|---:|
| published_date | 870 |
| event_date | 380 |
| author | 381 |
| institution | 0 |
| observation_addressee | 2 |
| language | 0 |
| rights_evidence | 0 |

NULL даты события не заменяется датой публикации. Персональный автор пресс-релиза и участники не восстанавливаются по должности. Для документов МИД установлен издатель/институт; личные участники остаются в исходном тексте до отдельной атрибуции. Англоязычные материалы МИД являются опубликованной институциональной версией, а не доказательством языка произнесённой речи.

### Контрольные точки

У каждой партии свой collection_run и список discovery ID. Обработанные URL проверяются по document_aliases до сети; повторное ingestion выполняется в памяти с тем же исходным текстом и хэшем, без повторной загрузки. Исключения за периодом/темой и сетевые отказы сохранены в discovery_results и collection_items; ошибки — в errors. Автоматического повторения отказов нет. После прерывания продолжается зафиксированная партия.

| Партия МИД РК | Новых документов | Проверен повтор | Пропуски технически обязательных полей этой партии |
|---|---:|---:|---:|
| 18 | 20 | 20 | 0 |
| 20 | 18 | 19 | 0 |
| 22 | 18 | 18 | 0 |
| 24 | 18 | 18 | 0 |
| 28 | 18 | 18 | 0 |
| 30 | 20 | 20 | 0 |
| 34 | 19 | 19 | 0 |
| 36 | 18 | 18 | 0 |
| 38 | 20 | 20 | 0 |
| 40 | 20 | 20 | 0 |
| 42 | 19 | 19 | 0 |
| 49 | 20 | 20 | 0 |
| 75 | 19 | 19 | 0 |
| 101 | 18 | 18 | 0 |
| 106 | 18 | 18 | 0 |
| 125 | 20 | 20 | 0 |
| 149 | 20 | 20 | 0 |
| 171 | 20 | 20 | 0 |
| 186 | 18 | 18 | 0 |
| 210 | 16 | 16 | 0 |

У новых японских цитат отдельно сохранены годовые страницы и nextRecordPosition в collection_runs. Финальная офлайн-проверка повторяет только документы текущего расширения со всеми связанными заявлениями и цитатами. Правило технической даты уточнено: достаточно документированной даты события ИЛИ публикации; дата публикации не домысливается. Распределения контрольной точки пересчитаны по её партии, чтобы параллельный писатель другого источника не попадал в её счётчики.

### Подтверждённые ограничения текущего запуска

- В предшествующем запуске МИД РК и NDL были остановлены после тайм-аутов транспорта 180 с. Это не HTTP 403/429 и не доказательство отсутствия документов. Результаты продолжения 1 ноября приведены отдельно ниже.
- Остались ранее обнаруженные URL и следующие страницы NDL. Принципиальная недостижимость 2 000 не доказана; текущий запуск остановлен с сохранёнными позициями, а число качественных наблюдений не дополнено искусственно.
- Полные речи NDL не сохраняются; короткая цитата не заменяет полный контекст и не разрешает частоты слов всей речи. Полные тексты МИД пригодны лишь для частот этого документального подкорпуса после проверки релевантности; они не отражают частоту самостоятельных политических заявлений.
- Исторические выборки не репрезентативны. Поисковая очередь МИД и порядок API создают смещения по годам; актуальный охват японских записей приведён в таблице по годам. Нулевые ячейки не означают отсутствие дипломатической активности.
<!-- EXPANSION_END -->


<!-- DOMESTIC_20261101 -->
## Государственные и внутриполитические источники — 1 ноября 2026

Исходное состояние проверено: 1437 документов / 1029 записей заявлений / 1029 цитат / 491 находка; GDELT 22 Events + 28 Mentions + 60 GKG; схема 4.

Текущее состояние: `{"documents": 1442, "statements": 1034, "quotes": 1034, "discovery_results": 496, "gdelt_events": 22, "gdelt_mentions": 28, "gdelt_gkg": 60}`.

Добавлено: 5 полных текстов, 5 уникальных записей заявлений, 5 подтверждённых фрагментов-цитат. Коротких документов, документов только с метаданными, GDELT и медийных упоминаний добавлено 0.

Источник всех новых текстов: korea_government_kr, Республика Корея, primary, президентская администрация. Япония: 0 новых документов / заявлений / цитат.

Две президентские речи, два брифинга пресс-секретарей и один институциональный брифинг 2020 года учитываются раздельно. Брифинг — письменное заявление его автора/института, а не прямая речь президента; reported speech не превращён в цитату президента.

Достоверная дата события ИЛИ публикации: 5/5; персональный автор: 3/5. У двух речей известна дата выступления, дата публикации не подставлялась; у брифингов дата публикации, устное произнесение не утверждается.

Все новые тексты: оригинал ko, KOGL Type 4, только согласованное ограниченное некоммерческое исследовательское использование, без изменений. Сохранены текст и атрибуция; фотографии, вложения и HTML с чужими медиа не архивировались. Коммерческое использование не разрешено.

Для будущих частот внутри ограниченного исследовательского подкорпуса доступны 5 полных текстов; политическая разметка требует проверки. Есть сотрудничество и критический брифинг о въездных ограничениях Японии; выборка не репрезентативна и не сбалансирована по тональности. Новых партийных/парламентских текстов нет; все типы риторики этим пилотом не покрыты.

### Новые записи по годам и типу (документы / заявления / цитаты)
| Год | РК, primary, речи | РК, primary, брифинги | Япония, primary | РК / Япония, secondary |
|---|---:|---:|---:|---:|
| 2015 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2016 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2017 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2018 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2019 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2020 | 0 / 0 / 0 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2021 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2022 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2023 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2024 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2025 | 1 / 1 / 1 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 |
| 2026 | 1 / 1 / 1 | 1 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 |

### Контроль каждой партии
| Документ | Тип | Дата события / публикации | Автор | Тема | Повторный импорт |
|---|---|---|---|---|---|
| 1438 | official_speech | 2026-01-13 / None | 이재명 | diplomatic_contacts | 0 новых сущностей |
| 1439 | official_speech | 2025-08-23 / None | не установлен | regional_cooperation | 0 новых сущностей |
| 1440 | official_written_briefing | None / 2026-10-23 | 김성완 | trade_economy | 0 новых сущностей |
| 1441 | official_written_briefing | None / 2025-09-30 | 강유정 | diplomatic_contacts | 0 новых сущностей |
| 1442 | official_written_briefing | None / 2020-03-08 | не установлен | diplomatic_contacts | 0 новых сущностей |

SQLite integrity=ok; FK errors=0; raw hash errors=0. Схема 4, миграции не выполнялись.
Импорт атомарен с checkpoint на документ. После каждой записи проверен повторный ingest: 0 новых документов/заявлений/цитат. Сходные речи разных дат остаются разными событиями, возможные совпадения сохраняются для проверки. Старые 164 пары и прежние выборочные аудиты не пересматривались.
Тесты: см. существующий docs/TEST_RESULTS.txt. Продолжение выполненной партии --resume не вызывает повторной загрузки.
Этап дал ограниченный пилот: полный парламентский канал и МИД Японии не подключены; историческая полнота 2015–2026 не достигнута. Новые URL не засчитываются как тексты.
<!-- DOMESTIC_20261101_END -->

<!-- ASSEMBLY_API_20261101 -->
## Проверка парламентского API РК — 1 ноября 2026

Состояние корпуса: `{'documents': 1442, 'statements': 1034, 'quotes': 1034}`; прирост документов/заявлений/цитат **0 / 0 / 0**. Подтверждены 7 разрешённых sample-запросов и 13 уникальных идентификаторов заседаний в списках (это метаданные, не речи). Годы живых проверок: 2015, 2019, 2023, 2026. Новых пригодных для частотного анализа текстовых наблюдений: 0. Повторные строки повестки группируются по CONF_ID, ошибочные ответы не импортируются. Исходные данные корпуса не изменялись; схема 4, миграции не требовались. Работающий PDF подтверждён, но индивидуальные права и безопасная сегментация говорящих остаются условиями текстового импорта. SQLite integrity=ok; FK errors=0. Тесты — docs/TEST_RESULTS.txt. Полная инструкция ключа и спецификации — docs/SOURCE_AUDIT.md.
<!-- ASSEMBLY_API_20261101_END -->

<!-- ASSEMBLY_PDF_20261101 -->
## Извлечение парламентских PDF РК — 1 ноября 2026

Исходно: 1442 документов / 1034 заявлений / 1034 цитат, схема 4. Сейчас: 1444 / 1050 / 1070.

Обработано 6 уникальных публичных PDF, 368 физических страниц. Сохранено 2 полных извлечённых контекстов протокола (без колонтитулов), 27 проверенных полных реплик, 16 записей заявлений по автору и эпизоду и 36 дословных цитатных блоков. Эти числа не складываются в единый показатель качества.

Найдено 921 маркерных блоков до полного отсева. Из них 9 не прошли формальное распознавание автора/границы и не импортированы. Короткие/процедурные блоки: 511; служебные доклады: 3; без явного японского якоря: 302.

Автоматических японских кандидатов: 96. Подтверждённая тематическая релевантность: 27 проверенных реплик. Остальные кандидаты не объявлены релевантными и не импортированы. Наличие японского слова само по себе не является политическим событием.

| Год | PDF | Маркерные блоки | Японские кандидаты | Проверенные полные реплики | Новые документы | Заявления | Цитатные блоки |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 1 | 116 | 8 | 7 | 1 | 6 | 14 |
| 2016 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2017 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2018 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2019 | 1 | 713 | 88 | 20 | 1 | 10 | 22 |
| 2020 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2021 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2022 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2023 | 1 | 68 | 0 | 0 | 0 | 0 | 0 |
| 2024 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2025 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2026 | 3 | 24 | 0 | 0 | 0 | 0 | 0 |

Все новые тексты: Республика Корея, primary, парламентские протоколы; Япония и secondary — 0 новых записей. Место заседания отделено от органа автора: в корпусе есть депутаты и министр иностранных дел, отвечающий парламенту. Непосредственные адресаты — участники заседания; Япония — предмет высказывания, что явно указано в addressee.

### Контроль качества

Целевая проверка агентом по PDF: 27 реплик; совпадение имени, даты, текста и границ — 27/27 в этой выборке. Включены 20 реплик внутри колонок 2019 года и 7 реплик 2015 года, включая переходы страниц/колонок. Это целевая, а не случайная выборка; 100% на ней не означает 100% точности парсера на остальных страницах. Независимой человеческой верификации не было.

Индивидуальные проверки и SHA-256 текста/страниц: внутренний data/assembly_pdf_review.json. Исходные PDF и их хэши — data/raw и observations; внутренние изображения data/assembly_layout.png и data/assembly_review_01.png … 06.png. Полные извлечения и технические результаты — source_checks в единственной базе. Изображения не являются публичным интерфейсом.

Порядок чтения: левая колонка → правая колонка → следующая страница. Колонтитулы исключены по проверенной геометрии A4. По завершении заседания (산회) приложения больше не сегментируются как речи. Неразобранные имена/роли и незакрытые границы из импорта исключены. OCR и автоматическая языковая правка не применялись. Неисправленные дефекты исходного текстового слоя возможны вне проверенных реплик.

Краткие ответы, технические распоряжения и случайные упоминания не считаются полноценными наблюдениями автоматически. Скобочные ремарки и анонимные выкрики сохранены в контексте, но удалённые куски не склеиваются в фиктивную цитату: цитатные блоки остаются непрерывными фрагментами исходного текста.

Несколько реплик одного говорящего в одном эпизоде парламентского вопроса–ответа не создают новые события. Ключ: CONF_ID + начало эпизода владения словом + говорящий + роль. Повторный выход того же депутата после другого выступающего — отдельный эпизод. Разные протоколы/даты не объединяются. Это консервативная единица парламентского выступления, а не атомарная семантическая претензия.

Есть критика соглашения/торговых мер, разъяснения правительства, поддержка соглашения и предложения прямого диалога и механизмов урегулирования. Полные ответы, включая связь с КНДР/региональной безопасностью, сохраняются; исключительно северокорейские реплики не включены. Полнота и баланс тональностей за весь период не утверждаются.

Для будущих частот доступны 27 проверенных реплик в их полном контексте; для частоты событий — 16 записей эпизодов/авторов. Вопросы–ответы и отбор коротких реплик создают смещение; применять эти числа как частоту всей политической риторики нельзя.

Повторный импорт: 0 новых документов / заявлений / цитат. Последующие запуски продолжают processed-checkpoints и не загружают PDF повторно. SQLite integrity=ok; FK errors=0; raw hash errors=0; схема 4, миграций нет.

### Внутреннее хранение и публикация

Полные протоколы, реплики и исходные PDF предназначены только для запрошенного внутреннего исследования; публикационная лицензия не присвоена. В единственной data/corpus.jsonl у внутренних документов text пуст, пути к исходникам скрыты; в существующем HTML-отчёте цитаты скрыты. Те же ограничения применены к ранее помеченным KOGL4 документам. Оригинальные данные в SQLite и data/raw сохранены. Два полных протокола — контекст, а не два политических заявления.

Сбор ограничен публичной выборкой. API-ключ не обходился, общий аудит не повторялся, МИД Японии не запрашивался. Следующий шаг — проверка оставшихся тематических кандидатов по той же процедуре; автоматического масштабного импорта нет.
<!-- ASSEMBLY_PDF_20261101_END -->





<!-- DRI_V01_START -->
## DRI v0.1 — экспериментальная частота конфликтных выражений

Это описательная лексическая метрика, не вероятность войны, не прогноз и не проверенный классификатор политических намерений. Единого значения DRI и шкалы 0–100 нет: отсутствует сопоставимое двустороннее покрытие.

Из 1050 заявлений в компоненты вошло 1017; исключено 33: `{'prior_relevance_uncertain_or_nonbilateral': 31, 'known_nonpolitical_witness': 2}`. Полных речей/самостоятельных официальных заявлений: **13**; фрагментарных диагностических единиц: **1004**. Каждая единица — уникальное событие/автор/дата; повторные источники не увеличивают число сигналов.

Документы без самостоятельной привязки к заявлению: 408; библиография без текста: 26. GDELT отдельно: `{'gdelt_events': 22, 'gdelt_mentions': 28, 'gdelt_gkg': 60}`. Ни пересказы встреч, ни GDELT автоматически в речевые сигналы не преобразованы. Все 1050 исходных записей остаются в базе; аналитика открывает SQLite в режиме read-only.

### Формула и единица подсчёта

`F[g,t] = 1000 × sum(counted_expressions[u]) / sum(analyzer_tokens[u])`, где t — календарный месяц, g — страна × опубликованный язык × primary/secondary × конкретный источник × полнота текста × статус оригинала/перевода. Это отношение сумм, не среднее частот коротких и длинных текстов. Числовых весов должностям и источникам нет.

Полный текст самостоятельной речи заменяет вложенную цитату, а не складывается с ней. Протокол не берётся целиком за одну речь. Для парламентских эпизодов используются только проверенные реплики; полнота подтверждается покрытием всех реплик автора в его эпизоде. В 2015 году это шесть полных выступлений, в 2019 — десять частичных эпизодов. Цитатные интервалы одного источника объединяются при доказанном перекрытии; разные реплики и разные даты не склеиваются.

Прежние possible_duplicate не переаудировались и не являются основанием склеивать похожие речи разных дат. Неопределённость сохранена в поле possible_duplicate_candidates каждой аналитической единицы; автоматическая агрегация опирается только на явную идентичность события, автора и даты.

Длина документа не доказывает полноту. Для двух старых комментариев МИД полнота теперь подтверждена точным повторным разбором сохранённого HTML, его SHA-256, датой, заголовком и атрибуцией: config/dri_v01_completeness.json. Полные тела заменили 25-словные цитаты только во внутреннем расчёте; исходные записи и ограничения публикации не изменены, разрешение на распространение не предполагается. Журналистская интерпретация не добавляется к словам политика; для вторичного источника требуется подтверждённая дословная атрибуция, а официальный первичный источник имеет приоритет как доказательство, без политического веса.

Дата речи приоритетна. Для самостоятельного официального письменного заявления допустима его дата публикации с отдельной пометкой, без выдумывания даты устного выступления. Published language подтверждается текстом источника/цитаты; неизвестный исходный язык английской версии не объявляется английским оригиналом.

Английский: Unicode-границы слов, casefold и конечная карта только явных словоформ. Корейский: Kiwi/CoNg, морфемы с частицами и окончаниями в знаменателе; space_tolerance=1 допускает один типографский разрыв, но не восстанавливает пропущенные символы PDF. Японский: Janome/IPADIC, леммы и морфемы без пунктуации. Поиск использует последовательности содержательных лемм, а не подстроки; английские слова, корейские и японские морфемы не взаимозаменяемы.

Позиции char_start/char_end относятся к подготовленному фрагменту (NFC и нормализованные пробелы), а не к байтам PDF. source_ref указывает исходный документ/цитату или реплику и диапазон в её исходном тексте; fragment_provenance и token_ledger_sha256 позволяют воспроизвести токены через --explain без публикации полного текста.

Словарь `config/dri_v01_lexicon.json`: 48 выражений в семи заданных категориях, с языком, правилами и синтетическими примерами ошибок. Выражения не подбирались по датам кризисов; веса не оценивались. Перекрывающиеся варианты дают одно, самое длинное, совпадение.

Контекстные правила воздерживаются от подсчёта при цитировании, сообщении чужой позиции, отрицании рядом, гипотезе/вопросе, конкурирующем третьем государстве или отсутствии явной второй стороны в том же предложении. Именные экспортные ограничения требуют явной отрицательной оценки; одно упоминание войны, санкций или КНДР не является признаком угрозы. Отрицание, встроенное в словарное выражение, не отменяет его самого. Это консервативные локальные правила; разрешение местоимений, сложной вложенной речи, иронии и полной области отрицания не реализовано. Ложные отрицания и ложные срабатывания остаются.

### Объём и временной фон

Порог объёма месяца: 5 единиц и 500 токенов одного компонента. Это заранее заданный технический фильтр, не доказанная статистическая достаточность. Наблюдаемая сырая частота сохраняется и ниже порога, но dri_component там пуст. Месяц без текстов: frequency/count пусты, а не 0. Наблюдаемый ноль означает лишь отсутствие учтённых словарных выражений.

Прохождение порога не выравнивает точность месяцев с разным объёмом и не делает зависимые выступления независимыми. Доверительные интервалы, распределительная модель редких счётчиков и значимость аномалий не оценивались. Все недостаточные компонент-месяцы перечислены в CSV: фильтр status=insufficient_volume; отсутствие текстов отдельно status=no_data.

`robust_deviation = (F - median(past)) / (1.4826 × MAD(past))`. Только предыдущие поддержанные объёмом месяцы за 60 календарных месяцев, минимум 12 наблюдаемых месяцев и 4 ненулевых. При нулевом MAD или недостаточном фоне значение пусто. Будущее и текущий месяц в фон не входят. Порог 3.5 — диагностическая метка, не p-value и не обученный кризисный порог; статистическая применимость должна проверяться отдельно. [NIST: modified Z-score и ограничения его интерпретации](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).

Получено 9 раздельных компонентов. Состояния компонент-месяцев: `{'no_data': 1102, 'insufficient_volume': 158, 'supported': 18}`; поддержанных месяцев основных полных компонентов: 1. Фон: `{'current_month_unsupported': 1260, 'insufficient_history': 18}`. Текущих данных недостаточно для робастных аномалий: в таблице пустые значения, а не искусственные нули.

### Выборка по годам

| Год | РК полные | РК диагностические | Япония полные | Япония диагностические |
|---|---:|---:|---:|---:|
| 2015 | 8 | 2 | 0 | 63 |
| 2016 | 0 | 8 | 0 | 57 |
| 2017 | 0 | 12 | 0 | 69 |
| 2018 | 0 | 9 | 0 | 54 |
| 2019 | 0 | 16 | 0 | 69 |
| 2020 | 1 | 9 | 0 | 41 |
| 2021 | 0 | 8 | 0 | 43 |
| 2022 | 0 | 8 | 0 | 104 |
| 2023 | 0 | 6 | 0 | 166 |
| 2024 | 0 | 7 | 0 | 103 |
| 2025 | 2 | 7 | 0 | 82 |
| 2026 | 2 | 5 | 0 | 56 |

### Длина текстов и сопоставимость

| Страна / язык | Источник / форма | N | Мин. токенов | Медиана | Макс. |
|---|---|---:|---:|---:|---:|
| JPN / ja | kokkai_jp / legacy_excerpt | 43 | 39 | 48 | 57 |
| JPN / ja | kokkai_jp / sentence_excerpt | 864 | 7 | 33.0 | 57 |
| ROK / en | mofa_kr / complete_official_statement | 2 | 142 | 184.0 | 226 |
| ROK / en | mofa_kr / short_quote_fragment | 87 | 5 | 25 | 27 |
| ROK / ko | assembly_kr / complete_speech | 6 | 831 | 925.5 | 1150 |
| ROK / ko | assembly_kr / selected_turns_partial_floor | 10 | 68 | 205.5 | 619 |
| ROK / ko | korea_government_kr / complete_official_statement | 3 | 342 | 1104 | 1315 |
| ROK / ko | korea_government_kr / complete_speech | 2 | 207 | 707.5 | 1208 |

Исключение коротких японских фрагментов удаляет 907 единиц и оставляет 0 японских единиц. Эффект на единый DRI неопределён, потому что сам общий показатель не идентифицирован. Усреднять эти ряды с МИД РК запрещено текущей методикой.

Способ обнаружения создаёт систематические смещения: запрос 日韓, прежний фильтр 大臣, выбор одного короткого законченного предложения, старые обрезанные фрагменты и первые 25 слов комментариев МИД. Поэтому частота отражает сохранённую выборку, а не частоту риторики всего государства; тип источника, язык и полнота смешаны с механизмом отбора. Большое число полных отчётов МИД о встречах не решает нехватку самостоятельных выступлений.

Используется современный ретроспективный срез корпуса, а не архив версий, доступных исследователю в каждом историческом месяце. Отсутствие будущих значений в формуле фона не означает, что весь корпус был доступен тогда в реальном времени. Для будущего прогнозного backtest нужны временные срезы доступности и учёт дат поздней публикации/исправлений. Такая проверка здесь не выполнялась.

### Небольшой ручной аудит выражений

Проверено агентом 24 совпадений/кандидатов по сохранённым текстам, без повторения прежнего аудита 50 заявлений. Это целевая проверка с отдельными языками и решениями, не случайная независимая валидация. Полные контексты не публикуются. Записи проверки: config/dri_v01_review.json; признаки и позиции: data/dri_v01_matches.jsonl.

| Unit | Язык | Решение правила | Ручная оценка | Замечание |
|---:|---|---|---|---|
| 99 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 143 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 146 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 1044 | ko | suppressed / counterpart_not_explicit_in_sentence | conservative_abstention_context_loss | Вторая сторона восстанавливается из более широкого контекста, но не названа в предложении; межфразовая анафора не реализована. |
| 1048 | ko | suppressed / counterpart_not_explicit_in_sentence | correct_target_exclusion | Выражение сожаления относится к отказу внутренней партии созвать комитет, а не к Японии. |
| 90 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 126 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 87 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 93 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 1034 | ko | suppressed / measure_description_without_explicit_negative_evaluation | missed_explicit_negative_evaluation | В том же предложении есть собственная отрицательная оценка действий Японии, но её не охватывают фиксированные контекстные маркеры. Ошибка полноты правила; после аудита словарь не подгонялся. |
| 76 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 85 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 145 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 80 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 144 | en | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 1039 | ko | suppressed / competing_third_country_context | possible_missed_bilateral_feature | Японские торговые меры различимы, но упоминания России/Китая приводят к отказу; локальное правило слишком грубо для смешанного предложения. |
| 1042 | ko | suppressed / measure_description_without_explicit_negative_evaluation | reasonable_descriptive_abstention | Описаны меры Японии и общественный бойкот; собственный акт осуждения говорящим из одного предложения не установлен. |
| 507 | ja | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |
| 24 | ja | counted / explicit lexical attribution | supported_feature_fragmentary_context | Лексическое обвинение адресовано РК; старый фрагмент обрезан, полнота контекста не подтверждена. |
| 135 | en | suppressed / counterpart_not_explicit_in_sentence | reasonable_truncation_abstention | Сохранённое начало заявления содержит выражение, но обрезано до названия адресата; предмет из полного текста не подставлялся. |
| 1048 | ko | suppressed / competing_third_country_context | ambiguous_reported_ownership | Политик ссылается на международные оценки японских действий; принадлежность позиции не разрешается надёжно простым правилом третьих стран. |
| 34 | ja | counted / explicit lexical attribution | supported_feature_fragmentary_context | Лексическое обвинение адресовано РК; старый фрагмент обрезан, полнота контекста не подтверждена. |
| 26 | ja | counted / explicit lexical attribution | supported_feature_fragmentary_context | Лексическое обвинение адресовано РК; старый фрагмент обрезан, полнота контекста не подтверждена. |
| 412 | ja | counted / explicit lexical attribution | supported_lexical_feature | Собственная явная отрицательная оценка/протест к другой стороне в сохранённом тексте; смысл всей речи этим не верифицирован. |

Аудит обнаружил как минимум один пропуск собственной явной отрицательной оценки из-за ограниченного списка контекстных маркеров и несколько слишком консервативных отказов в смешанных/анафорических предложениях. Словарь после просмотра этих случаев не подгонялся. В текущем расчёте корейские компоненты имеют словарный ноль, хотя в их текстах присутствует критическая риторика; это подтверждённое ограничение измерения. Обобщённая точность и полнота классификации не установлены.

Автоматические тесты проверяют программные свойства, а не точность политической классификации. Предиктивная/историческая валидация по событиям не проводилась; будущие исходы не использовались.

### Артефакты и воспроизведение

data/dri_v01_monthly.csv — месячная таблица с пропусками и диагностикой; data/dri_v01_units.jsonl — включение/исключение каждой записи и источники; data/dri_v01_matches.jsonl — найденные выражения, решения и позиции без исходных текстов; data/dri_v01_manifest.json — хэши, версии, параметры, показатели покрытия. docs/DRI_v01.png — динамика компонентов; docs/DRI_v01_diagnostics.png — объём, длина, покрытие и зависимость от фрагментов.

Повтор: `.venv\Scripts\python.exe scripts/calculate_dri.py --verify-reproducibility`. Для внутренней проверки токенов/совпадений одной записи: `.venv\Scripts\python.exe scripts/calculate_dri.py --explain ID`. Она выводит текстовые токены в терминал; не использовать вывод как публичную выгрузку. Зависимости: requirements-analytics.lock; словари/модели токенизации хэшированы. База не меняется; новых таблиц, LLM и массового сбора нет.
<!-- DRI_V01_END -->

<!-- DRI_V01_COMPLETENESS_START -->
## Диагностика полноты аналитического корпуса DRI v0.1

Офлайн-проверка сохранённой базы и конвейера; внешние источники, аудит 50 заявлений и 164 пар дублей не переаудировались. Единица — датированное самостоятельное выступление/институциональное заявление. Полный отчёт о встрече не равен полной речи. Длина текста не использовалась как доказательство полноты.

База: 1444 документов, 1050 заявлений, 1070 цитат; схема 4. Текст есть в 1418 документах; 26 — только метаданные. Полнота опубликованного тела/протокола подтверждена в 350 документах: 348 сохранёнными признаками и 2 точным воспроизведением исходного HTML. Это не 350 самостоятельных речей.

| Тип сохранённого документа | Документы | Связаны с заявлениями | Представлены в аналитике | Не представлены |
|---|---:|---:|---:|---:|
| full_activity_report | 341 | 0 | 0 | 341 |
| full_protocol | 2 | 2 | 2 | 0 |
| full_standalone_statement | 7 | 7 | 7 | 0 |
| metadata_only | 26 | 0 | 0 | 26 |
| retained_fragment_or_unconfirmed | 1068 | 1027 | 994 | 74 |

Полных документов связано с заявлениями **9** (7 самостоятельных официальных текстов и 2 протокола); все 9 используются. Полных документов вне выборки **341**, все — official_activity_report без statement_sources. Два протокола порождают 16 единиц автора/эпизода: 6 полных и 10 частичных, а не две «речи». Так получаются 13 полных аналитических единиц из 9 документов.

340/341 полных отчётов проходят сохранённый тематический экран упоминаний РК и Японии (включая сотрудничество и многостороннюю безопасность). Их связь с тематикой не означает, что они являются дословной речью или что критика в пересказе принадлежит автору публикации. analysis_status=text_frequency_candidate_not_statement_frequency явно сохраняет это различие; verification_status=needs_review. Полная семантическая релевантность всех 341 документов независимо не проверялась; этот экран не выдаётся за такую проверку.

Оставшийся документ 200 проверен отдельно: он касается японского промышленного наследия, принудительного труда корейцев и позиции корейского правительства. Упоминание Korean government не попало в узкий экран названий РК. Документ тематически относится к паре, но совмещает изложение решения ЮНЕСКО и правительственной позиции; это не стенограмма одного выступления. Ошибка экрана диагностики не затрагивает включение речевых единиц или расчёт DRI.

Проверены исключения из классификации отчётов: документы 316 (изложение позиций двух правительств) и 350 (пересказ поздравительных слов, не стенограмма). Документ 197 содержит Address в смысле решения экологических проблем. Полного самостоятельного заявления в этих подозрительных по названию случаях не обнаружено. Среди 341 названий нет пропущенного явно обозначенного spokesperson commentary/statement. Для частот официальной повествовательной прозы эти тексты доступны, но добавление их отдельного компонента изменило бы текущую единицу анализа и здесь не выполняется.

Ещё 5 непривязанных старых документов МИД (93, 99, 100, 111, 115) — только начала совместных заявлений/вводные слова; не полные тексты. 36 остальных отчётов МИД сохранены как restricted_excerpt. 26 библиографических записей СМИ не содержат текста. Поэтому 408 непривязанных документов = 341 + 36 + 5 + 26; отсутствие связи объяснимо их типом, а не потерей готовых речей.

### Подтверждённое исправление полноты

Документы 1 и 2 / заявления 2 и 1: самостоятельные комментарии пресс-секретаря МИД от 2015-08-15. Их оригинальные HTML сохранены в observations. SHA-256 исходников и точное равенство bo_con, заголовка и даты проверяются при каждом расчёте. config/dri_v01_completeness.json хранит закрыто проверяемую аттестацию полноты, без текста. Раньше отсутствие новых metadata-полей оставляло по 25 слов; теперь полные тела заменяют цитаты, не добавляясь к ним. База, цитаты, ссылки и исходные metadata не переписаны. Статус unofficial_translation сохранён; это полнота опубликованного перевода, не доказательство полноты корейского оригинала. Только внутренний расчёт: разрешение на публичное распространение не установлено.

Дополнительно обоснованно включены **2 полных текста** существующих единиц; новых событий/документов не добавлено. Других пригодных для автоматического повышения до полной речи текстов не подтверждено.

### Единица анализа и связи

Проверки связей: `{"assembly_turns_assigned_to_multiple_units": 0, "documents_with_multiple_statements": 2, "duplicate_official_document_ids": 0, "foreign_key_errors": 0, "integrity": "ok", "quote_links": 1070, "quote_sources_without_statement_source": 0, "repeated_exact_event_author_date_identities": 0, "statement_links": 1050, "statements_with_multiple_documents": 0, "statements_without_document": 0, "statements_without_quote": 0, "units_merging_distinct_speakers_dates_or_events": 0}`.

NDL: один speechID — одна запись, 864 включённых законченных коротких предложения и 43 старых обрезанных фрагмента. Это не 907 полных речей. Идентификаторы не повторяются; сохранён только отрывок исходного speechID, поэтому самостоятельность исходной речи подтверждается идентификатором, а её полнота — нет. Разные speechID не склеивались по сходству. Без исходного полного заседания невозможно доказать, что два отдельных ответа одного человека не относятся к одной более широкой дискуссии; принимается API-единица, а не число упоминаний.

Assembly: 27 проверенных реплик объединены в 16 эпизодов автора с учётом прерываний. Реплика не присвоена двум единицам. Полнота 6 эпизодов подтверждена покрытием всех реплик данного автора в эпизоде; 10 неполных не повышены до полных. Остальные непроверенные реплики в сохранённых протоколах существуют, но не являются уже качественно проверенными речами. Их импорт потребовал бы нового отбора и проверки, здесь не выполнялся.

МИД: самостоятельный комментарий/заявление — единица учреждения, без выдуманного личного автора; полный activity report с пересказами разных участников — документ, а не одно их выступление. Правительство: 2 полные речи и 3 самостоятельных письменных брифинга. Журналистский пересказ не вошёл; документов СМИ с проверенным речевым текстом нет. Прежние 31 неопределённое/небилатеральное заявление и 2 неполитических свидетеля остаются исключены; отдельный аудит этих решений не повторялся.

### Покрытие девяти компонентов после исправления

Все источники primary. Оригинальность/перевод остаются отдельными стратами. Нулевая единица — текст без учтённого выражения; нулевой месяц — месяц с текстами и нулём выражений. Пропущенные месяцы в доли нулей не входят.

| Страна / язык / источник / форма / версия | Единиц | Полные / фрагменты | Месяцев с текстом / с порогом | Токены | Выражения | Нулевых единиц | Нулевых наблюдаемых месяцев | Причина недостаточного объёма: оба / только N / только токены |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| JPN / ja / kokkai_jp / legacy_excerpt / original | 43 | 0 / 43 | 15 / 0 | 2085 | 3 | 40/43 (93.0%) | 13/15 (86.7%) | 14 / 0 / 1 |
| JPN / ja / kokkai_jp / sentence_excerpt / original | 864 | 0 / 864 | 82 / 16 | 28158 | 2 | 862/864 (99.8%) | 80/82 (97.6%) | 23 / 0 / 43 |
| ROK / en / mofa_kr / complete_official_statement / unofficial_translation | 2 | 2 / 0 | 1 / 0 | 368 | 0 | 2/2 (100.0%) | 1/1 (100.0%) | 1 / 0 / 0 |
| ROK / en / mofa_kr / short_quote_fragment / published_original_unknown | 59 | 0 / 59 | 49 / 0 | 1176 | 24 | 36/59 (61.0%) | 28/49 (57.1%) | 49 / 0 / 0 |
| ROK / en / mofa_kr / short_quote_fragment / unofficial_translation | 28 | 0 / 28 | 22 / 0 | 627 | 7 | 21/28 (75.0%) | 15/22 (68.2%) | 22 / 0 / 0 |
| ROK / ko / assembly_kr / complete_speech / original | 6 | 6 / 0 | 1 / 1 | 5704 | 0 | 6/6 (100.0%) | 1/1 (100.0%) | 0 / 0 / 0 |
| ROK / ko / assembly_kr / selected_turns_partial_floor / original | 10 | 0 / 10 | 1 / 1 | 2690 | 0 | 10/10 (100.0%) | 1/1 (100.0%) | 0 / 0 / 0 |
| ROK / ko / korea_government_kr / complete_official_statement / original | 3 | 3 / 0 | 3 / 0 | 2761 | 0 | 3/3 (100.0%) | 3/3 (100.0%) | 1 / 2 / 0 |
| ROK / ko / korea_government_kr / complete_speech / original | 2 | 2 / 0 | 2 / 0 | 1415 | 0 | 2/2 (100.0%) | 2/2 (100.0%) | 1 / 1 / 0 |

Из 9 × 142 = 1278 компонент-месяцев: {'no_data': 1102, 'insufficient_volume': 158, 'supported': 18}. У 158 наблюдаемых месяцев порог не пройден: {'both': 111, 'tokens_only': 44, 'units_only': 3}. Требуются одновременно ≥5 единиц и ≥500 токенов внутри одной страты/месяца. Пять полных правительственных текстов распределены по разным месяцам и типам, два новых полных комментария находятся в одном месяце и не достигают N=5. У фрагментов N может быть достаточным, но 25 слов/короткие предложения дают меньше 500 токенов. Объединять языки, полноту или разные месяцы ради порога нельзя. Из 18 поддержанных месяцев только 1 основан на полных речах, 17 — диагностические фрагменты. Для исторического фона по-прежнему нет 12 предшествующих поддержанных месяцев: стандартизованные отклонения не вычислены.

### Ошибки контекста: использован прежний аудит 24 кандидатов

Исходная таблица и её SHA не изменены; повторного чтения/разметки тех же кандидатов не было. Распределение прежних заключений: `{'supported_lexical_feature': 14, 'conservative_abstention_context_loss': 1, 'correct_target_exclusion': 1, 'missed_explicit_negative_evaluation': 1, 'possible_missed_bilateral_feature': 1, 'reasonable_descriptive_abstention': 1, 'supported_feature_fragmentary_context': 3, 'reasonable_truncation_abstention': 1, 'ambiguous_reported_ownership': 1}`.

| Класс | Что подтверждено прежним аудитом | Минимальное дальнейшее исправление |
|---|---|---|
| Отрицательная оценка / нейтральное употребление | 1034: 1 подтверждённый пропуск собственной отрицательной оценки из-за фиксированного контекстного списка; 1042: обоснованное воздержание на описании мер | Разрешение собственной оценки в пределах клаузы с отдельными тестами; не считать любое торговое ограничение осуждением |
| Адресат / анафора | 1044: потеря межфразового адресата; 1048: правильно исключено сожаление о действиях внутренней партии | Ограниченное связывание соседних предложений только с однозначным адресатом; неоднозначное оставить нерешённым |
| Чужая позиция / третьи страны | 1039: возможный пропуск при России/Китае; 1048: неясное авторство международной оценки | Привязка субъекта и объекта в клаузе вместо запрета всего смешанного предложения; не снимать защиту целиком |
| Усечение / сегментация | 135: отказ из-за обрыва до адресата; 24, 26, 34: выражение поддержано, контекст неполон | Использовать полный текст только при сохранённом и проверенном происхождении; не дописывать утраченный контекст |
| Отрицание | Ошибки отрицания именно в 24 случаях не подтверждены | Сохранить действующие защиты и тесты; не объявлять их доказанной точностью |
| Перевод | Ошибки перевода в 24 случаях не проверены и не доказаны | Сохранять версии раздельно; не заявлять эквивалентность оригиналу |
| Поддержанные признаки | 14 поддержанных + 3 с неполным контекстом | Это не оценка общей precision/recall и не валидация намерения |

Предложения контекстных исправлений не внедрены в этом пересчёте: они меняют измерительное правило и требуют отдельной проверки на новых примерах. Словарь/контекстные правила/пороги не изменены; повторный аудит 24 случаев не проводился. Исправлена только доказанная потеря полноты двух сохранённых документов.

### До / после и воспроизводимость

| Показатель | До | После |
|---|---:|---:|
| Включённых единиц | 1017 | 1017 |
| Полных | 11 | 13 |
| Фрагментарных | 1006 | 1004 |
| Токены | 44666 | 44984 |
| Выражения | 36 | 36 |
| Поддержанные компонент-месяцы | 18 | 18 |
| Поддержанные месяцы полных текстов | 1 | 1 |

До: result_sha256=b1fd7d21c98b898167b66a197352f435393db34204e2a7bc83d57398176ee115. После: result_sha256=e28a31819774009f76c4b2bd659177211eec6ea4f0781ccae38f7e0a8e01e375. Два повторных расчёта идентичны: True. Ядро базы: 7d693db0dd6f705d2bf8e24be733afdb2a487e197ddefa73a2c111f352349f87; совпадение с исходным снимком: True. SHA-256 файла основной базы не изменился: True. Автоматические тесты из единственного docs/TEST_RESULTS.txt: 124 tests: OK.

Вывод: найдено локальное упущение подготовки данных (2 полных текста), оно исправлено. Главный барьер сопоставимого DRI остаётся в составе и сохранности исходного речевого материала: полных японских речей нет, большинство речевых записей ранее усечено, полные отчёты МИД являются другим типом текста. Дополнительно измерение ограничено известными контекстными пропусками, поэтому словарный ноль не означает отсутствие критики. Технических подтверждений потери ещё сотен готовых полных речей не найдено.

Повтор диагностики: `.venv\Scripts\python.exe scripts/diagnose_dri.py --verify-reproducibility`; расчёт: `.venv\Scripts\python.exe scripts/calculate_dri.py --verify-reproducibility`; тесты: `.venv\Scripts\python.exe scripts/run_tests.py`. Сети, установок, новых баз и публичных текстовых выгрузок нет.
<!-- DRI_V01_COMPLETENESS_END -->

<!-- DRI_V02_START -->
## DRI v0.2 — контекстная оценка высказываний

Экспериментальные воспроизводимые эвристики EN/KO/JA. Это не экспертная разметка, не вероятность кризиса и не историческая валидация. v0.1, база и исходные тексты сохранены. Внешних моделей, сети, новых зависимостей и массового сбора нет.

Из 1017 доступных единиц автоматически классифицировано 108 (10.6%); требуют проверки 909 (89.4%). Ранее исключённые 33 записей остаются исключены. Направленности: `{'undetermined': 909, 'neutral': 10, 'cooperative': 64, 'confrontational': 34}`. Интенсивности классифицированных: `{'0': 74, '2': 27, '1': 6, '3': 1}`.

Полнота доступных единиц: 13 полных / 1004 фрагментарных; из них классифицированы 1 полных / 107 фрагментарных. Это сохранённые признаки, новая диагностика полноты не проводилась.

### Единица и правила

Одна датированная единица автора/эпизода с прежними statement_ids, источниками и атрибуцией. Цитатные блоки не являются независимыми голосами. Даты/выступления не объединяются по сходству. Короткая законченная реплика может получить интенсивность 3, длинная речь — 0; длина не входит в формулу. Из неполного текста вывод ограничен сохранённым материалом, а не смыслом всей речи.

Правила в config/dri_v02_rules.json задают предикат и аргументную рамку, а не наличие изолированного слова. Общие ограничения проверяют адресата, чужого говорящего, цитату, отрицание возле предиката, вопрос/условность, историю и третью сторону. Кооперация РК–Япония по вопросу КНДР не отбрасывается только из-за упоминания третьей страны. Анафора ограничена одним соседним предложением внутри одного атрибутированного фрагмента. Границы предложений определяются до удаления CJK-пробелов PDF; позиции переводятся обратно в подготовленный текст. Непарная кавычка делает неопределённым только затронутый интервал, не все предшествующие предложения.

Нейтральность требует собственной явной фактической дипломатической рамки. Отсутствие совпадения даёт undetermined/needs_review с intensity=null. При конкурирующих собственных кооперативных и конфронтационных позициях также needs_review. Направленности не следует трактовать как исчерпывающую оценку всей внешней политики.

Шкала: 0 — нет выраженной конфронтации в подтверждённой нейтральной/кооперативной позиции; 1 — критическая оценка/обеспокоенность; 2 — протест/обвинение/требование; 3 — выраженный призыв к санкциям/прекращению сотрудничества/ограничительным мерам. Одно высказывание получает максимальную интенсивность среди поддержанных собственных рамок, а не сумму совпадений. Возможность обнаружить больше рамок в длинном тексте остаётся смещением полноты, хотя длина не является весом.

confidence=bounded_rule_support_not_calibrated означает только выполнение формальных проверок. Это не вероятность правильности. Известные границы: ограниченное покрытие предикатов/словоформ, риторические вопросы, вложенная речь, сложная анафора, смешанная позиция и усечённый контекст. Простые рамки не заменяют семантический анализ эксперта.

### Формула и покрытие

`M[t] = sum(intensity[u] для rule_supported) / N_classified[t]`, исходная шкала 0–3. Каждая уникальная единица имеет один голос; источники/институты/длина не имеют весов. Кооперативные и нейтральные классифицированные единицы имеют 0; неопределённые не входят в знаменатель и не заменяются нулём.

dri_v02 = observed_intensity_0_3 определён при хотя бы одном классифицированном высказывании, включая месяцы с малым объёмом. Надёжность не кодируется самим баллом: coverage_supported и measurement_status отдельно проверяют операционное покрытие (≥5 классифицированных и ≥50% доступных классифицировано). Для pooled_sample дополнительно требуется присутствие обеих стран среди классифицированных. Это диагностические пороги, не доказательство надёжности/точности. Пустой месяц и месяц без классификации имеют null. Сглаживания и шкалы 0–100 нет.

Публикуются отдельные ряды РК, Японии и условный pooled_sample. Последний — среднее наблюдаемой выборки, подверженное её составу, а не равнопредставленный двусторонний дипломатический индекс. Страна, язык, институт и источник показаны отдельно. Даже прохождение порога не исправляет смещённый отбор.

Одинаковая разметочная шкала задана для трёх языков, но её межъязыковая сопоставимость и эквивалентность переводов экспертно не подтверждены. Различия стран могут отражать различия правил, сохранённых текстов и их тематического отбора.

Арифметические границы при неопределённых: lower=sum(I_known)/N_available, upper=(sum(I_known)+3*N_unknown)/N_available. Это возможный диапазон при неизвестных оценках, а не подстановка нулей и не доверительный интервал; ошибки самих эвристических меток он не учитывает.

Месяцев с числовой наблюдаемой оценкой: `{'pooled_sample': 56, 'ROK': 29, 'JPN': 36}`; с операционным покрытием: `{'pooled_sample': 0, 'ROK': 0, 'JPN': 0}`. Все 142 месяца 2015-01…2026-10 сохранены для каждого ряда.

| Источник / страна / язык | Доступны | Классифицированы | needs_review | Конфронтационные | Кооперативные | Нейтральные |
|---|---:|---:|---:|---:|---:|---:|
| assembly_kr / ROK / ko | 16 | 2 | 14 | 2 | 0 | 0 |
| kokkai_jp / JPN / ja | 907 | 76 | 831 | 2 | 64 | 10 |
| korea_government_kr / ROK / ko | 5 | 1 | 4 | 1 | 0 | 0 |
| mofa_kr / ROK / en | 89 | 29 | 60 | 29 | 0 | 0 |

Причины проверки: `{'no_sufficient_owned_context_frame': 897, 'mixed_owned_positions': 2, 'no_explicit_owned_subject_for_performative': 1, 'reported_ownership_needs_review': 6, 'hypothetical_or_question': 2, 'unresolved_counterpart': 1}`.

### Зависимость от состава и отбора

В sensitivity каждой месячной строки повторяется та же формула после исключения каждого источника, типов институтов parliament/foreign_ministry/government/head_of_state_administration/unknown, а также historical_disputes, territorial_disputes и security по сохранённым меткам отбора. Новых индексов и весов при этом не вводится. Малый остаток/полное исчезновение классифицированных показаны явно. Метки theme — прежние эвристики, не независимая экспертная тематика; institution_type взят из statement_metadata, неизвестные не угаданы по месту заседания.

| Исключение в pooled_sample | Месяцев с оставшейся оценкой | Максимальный абсолютный сдвиг на шкале 0–3 | Месяцев, где оценка исчезла |
|---|---:|---:|---:|
| without_source:kokkai_jp | 29 | 1.500 | 27 |
| without_source:mofa_kr | 38 | 0.667 | 18 |
| without_source:assembly_kr | 55 | 0.000 | 1 |
| without_institution_type:parliament | 56 | 0.500 | 0 |
| without_institution_type:foreign_ministry | 25 | 0.667 | 31 |
| without_selection_theme:historical_disputes | 56 | 0.000 | 0 |
| without_selection_theme:territorial_disputes | 50 | 0.667 | 6 |
| without_selection_theme:security | 35 | 1.500 | 21 |

Сдвиги относятся к малым условным подвыборкам и не являются статистически подтверждёнными эффектами источника. Совместное исключение тем не устраняет смещение обнаружения: отсутствующих в базе нейтральных высказываний такой анализ не восстанавливает.

907 из 1017 доступных единиц — японские парламентские фрагменты (89,2%). Комментарии МИД обнаруживались по институциональным заголовкам и часто конфликтной тематике; NDL — по 日韓 и прежним ограничениям ролей, с сохранением одного короткого предложения. Поэтому доля сигналов относится только к этому корпусу и к классифицируемой его части, а не ко всей дипломатической коммуникации. Правила тоже могут легче распознавать явный протест, чем нейтральную/кооперативную позицию: пропуск нельзя считать нейтральностью.

### Отчёты МИД как контекст

Результат проверки связей: `{'full_activity_reports': 341, 'reports_with_same_publication_link': 0, 'reports_with_date_theme_candidate_link': 11, 'units_with_possible_context': 18, 'reports_added_as_signals': 0, 'context_body_used_for_automatic_scoring': False}`. Общие дата/тема — лишь possible_context, не подтверждённое тождество события. Такие связи сохранены для проверки и не добавляют текст, оценку или сигнал. Без подтверждённого события пересказ не подставляется в усечённую цитату. 341 отчёт не преобразован в новые заявления.

### Внутренняя экспертная выборка

Сформировано 32 единиц в data/dri_v02_review.json: стратификация по источнику, форме/полноте текста и предложенной направленности, затем дополнение отсутствующих лет; детерминированный SHA-порядок. Включены четыре источника, EN/KO/JA, полные/короткие тексты, разные годы и неопределённые случаи. Полные президентские речи и письменные брифинги образуют разные страты. Страты нейтральных/кооперативных заполняются только при наличии таких предложенных оценок; это обогащённая проверочная выборка, не оценка распространённости.

Файл содержит внутренние окна исходного текста, смещения, предложенные оценки и пустые expert_* поля для независимого специалиста. Не включать файл в публичные выгрузки. Повторный запуск сохраняет введённые экспертные поля при том же снимке/правилах; при смене снимка с заполненной разметкой останавливается. Независимой разметки пока нет; precision, recall, accuracy и межэкспертное согласие не вычисляются.

### Сравнение v0.1 / v0.2

data/dri_v02_comparison.csv сопоставляет месяцы внутри прежних девяти страт: частоту выражений/1000 токенов и среднюю контекстную интенсивность 0–3 с разными знаменателями. Их числовая разность и корреляция не интерпретируются как улучшение. v0.1 остался побайтово неизменным. Исходные 24 ручные проверки v0.1 не повторялись и не служили экспертными метками v0.2.

Глобальный запрет упоминания третьей стороны в v0.1 заменён локальной проверкой адресата предиката. Собственная отрицательная оценка может распознаваться без названия торговой меры, а нейтральное описание мер не получает высокий балл автоматически. v0.1 не давал семантической направленности; v0.2 также не трактует словарный ноль как нейтральность. Часть проблем анафоры, отрицания и чужой речи остаётся нерешённой. Эти программные изменения не доказывают превосходства классификации.

В 4 наблюдаемых компонент-месяцах v0.1 имел словарный ноль, а v0.2 нашёл хотя бы одну поддержанную конфронтационную рамку. Это различие измерений, не доказанная коррекция всех ошибок.

В сопоставлении прежних страт: порог v0.1 проходит 18 компонент-месяцев; критерии покрытия v0.2 — 0; оба — 0. Новая доля классифицируемости и прежний порог токенов измеряют разные ограничения, эти числа не являются сравнением точности.

| Год | РК: доступно / классифицировано / конфронтационных | Япония: доступно / классифицировано / конфронтационных |
|---|---|---|
| 2015 | 10 / 0 / 0 | 63 / 3 / 0 |
| 2016 | 8 / 2 / 2 | 57 / 0 / 0 |
| 2017 | 12 / 3 / 3 | 69 / 5 / 0 |
| 2018 | 9 / 0 / 0 | 54 / 1 / 0 |
| 2019 | 16 / 4 / 4 | 69 / 4 / 1 |
| 2020 | 10 / 1 / 1 | 41 / 1 / 0 |
| 2021 | 8 / 2 / 2 | 43 / 5 / 0 |
| 2022 | 8 / 1 / 1 | 104 / 14 / 0 |
| 2023 | 6 / 4 / 4 | 166 / 21 / 0 |
| 2024 | 7 / 5 / 5 | 103 / 9 / 1 |
| 2025 | 9 / 6 / 6 | 82 / 5 / 0 |
| 2026 | 7 / 4 / 4 | 56 / 8 / 0 |

### Воспроизведение и файлы

Результат SHA-256: 51ee97769e62b82a952500190378146e57db88d179d9ae20b555be8331024dae; повторный расчёт: True. В manifest зафиксированы код, правила, параметры, входной снимок и хэши артефактов.

Результаты автоматических проверок — в единственном docs/TEST_RESULTS.txt; его SHA-256 зафиксирован в manifest. Тесты проверяют программное поведение, а не экспертную точность политических меток.

Команда: `.venv\Scripts\python.exe scripts/calculate_dri_v02.py --verify-reproducibility`. Тесты: `.venv\Scripts\python.exe scripts/run_tests.py`. Публично безопасные аналитические метаданные: data/dri_v02_units.jsonl, data/dri_v02_monthly.csv, data/dri_v02_comparison.csv, data/dri_v02_manifest.json; график docs/DRI_v02.png. Внутренний файл с текстами — только data/dri_v02_review.json.
<!-- DRI_V02_END -->

<!-- EXPERT_REFERENCE_START -->
## Набор независимой экспертной разметки

Подготовлены 144 уникальных единицы: исходные 32 сохранены по ID и дополнены 112 без повторов. Набор DRI-EXPERT-800abfd1904890b8; фиксированное зерно 20261101; инструкция DRI-annotation-1.0, SHA-256 d106b5777031f3d4448caee55cc4e5d0400c7d92f91747acbf8deac6b8e2ccbd.

Единственная таблица для заполнения — data/dri_expert_review.xlsx. Три листа: Разметка (одна строка на высказывание), Инструкция и Тексты (только продолжения длинных исходников по тому же ID). Все экспертные поля пусты. В книгу не включены предложения модели, причины правил, страты отбора или скрытые прогнозы. Автоматические оценки отдельно в прежнем data/dri_v02_units.jsonl, неизменённом на этом этапе.

Сохранён весь доступный оригинальный языковой материал выбранных единиц; длинный текст разбит на последовательные части без смыслового отбора и подсветки. Усечённые цитаты не достраиваются до полных речей. Язык en — опубликованная английская версия, а не доказательство языка исходного выступления; тип перевода сохранён. Машинный перевод не применён. Все тексты в XLSX предназначены для внутреннего исследования.

Отбор: закреплены исходные 32 ID, все 21 корейская единица, все сохранённые исторические флаги и кандидаты интенсивности 1. Затем ограничения по редким категориям/контекстам/годам и квоты EN=40, JA=83, KO=21; недостающие места заполнены случайным порядком с фиксированным зерном. Порядок исходной базы не влияет на результат. Это обогащённая диагностическая выборка, не случайная репрезентативная оценка распространённости риторики. Названия автоматических категорий ниже описывают прежние прогнозы, не эталонные экспертные ответы.

| Язык | Единицы |
|---|---:|
| en | 40 |
| ja | 83 |
| ko | 21 |

| Год | Единицы |
|---|---:|
| 2015 | 12 |
| 2016 | 9 |
| 2017 | 15 |
| 2018 | 10 |
| 2019 | 17 |
| 2020 | 11 |
| 2021 | 9 |
| 2022 | 9 |
| 2023 | 16 |
| 2024 | 15 |
| 2025 | 9 |
| 2026 | 12 |

| Источник | Единицы |
|---|---:|
| assembly_kr | 16 |
| kokkai_jp | 83 |
| korea_government_kr | 5 |
| mofa_kr | 40 |

| Тип института | Единицы |
|---|---:|
| foreign_ministry | 83 |
| government | 19 |
| head_of_state_administration | 5 |
| parliament | 24 |
| unknown | 13 |

| Прежняя автоматическая категория | Единицы |
|---|---:|
| confrontational | 24 |
| cooperative | 24 |
| neutral | 10 |
| undetermined | 86 |

| Полнота | Единицы |
|---|---:|
| complete_official_statement | 5 |
| complete_speech | 8 |
| legacy_excerpt | 5 |
| selected_turns_partial_floor | 10 |
| sentence_excerpt | 78 |
| short_quote_fragment | 38 |

Контекстные флаги старого классификатора (пересекаются): `{'historical': 7, 'hypothetical': 8, 'negation': 15, 'quotation_present': 15, 'reported_position_present': 12, 'third_country_present': 8, 'unbalanced_quotation_context': 4}`. Кандидаты косвенной критики/умеренной оценки (прежняя интенсивность 1): 6. Без какого-либо кандидата словаря v0.1, включая подавленные совпадения: 120. Флаги — средства отбора, а не подтверждённые экспертные свойства.

### Воспроизведение и импорт

Подготовка/проверка: `.venv\Scripts\python.exe scripts/prepare_expert_review.py --data-only`. Создание XLSX (если ещё не существует): `.venv\Scripts\python.exe scripts/prepare_expert_review.py`. Повтор не перезаписывает существующую книгу. Для явного пересоздания незаполненной книги есть --rebuild-blank; при любых заполненных экспертных ячейках перезапись запрещена.

Проверка заполненного файла без записи: `.venv\Scripts\python.exe scripts/import_expert_review.py --file data/dri_expert_review.xlsx --reviewer expert_01`. Сохранение: та же команда с `--execute`. Эксперт работает только с XLSX; команду выполняет исследователь. Разрешён частичный прогресс при сохранении всех строк и неизменных исходников. Полностью пустые строки оценки пропускаются; частично заполненные строки или недопустимые сочетания отклоняют весь импорт.

data/dri_expert_annotations.json — единственный внутренний машинный реестр выборки и будущих экспертных аннотаций, не вторая SQLite-база и не дополнительная таблица для заполнения. Он хранит ID, хэши, протокол и пока пустой annotations; исходных текстов в нём нет. Импорт читает единую основную SQLite в режиме read-only, связывает метки с unit_id и statement_ids, проверяет источник и полный показанный контекст. Правила/версия инструкции, типы значений, соответствие направленности и интенсивности, дубли и все исходные поля проверяются до атомарной записи.

Идентичный повтор пропускается без изменения времени и числа аннотаций. Другой эксперт имеет независимую запись. Противоречащий ответ того же эксперта для той же версии инструкции отклоняется, а не молча перезаписывается. Версия и SHA инструкции, хэш текста и ID аннотации сохраняются. Изменение авто-прогноза не перезаписывает экспертный ответ; механизм не запускает обучение, оценку качества или индекс. Для последующего присоединения меток к корпусу предусмотрена dri.expert_review.expert_labels().

Схема и содержимое основной базы, исходные тексты, результаты v0.1/v0.2 и прежние 32 записи не изменены. Текущий этап не создаёт экспертных ответов. Не рассчитываются accuracy, precision, recall или согласие экспертов. Тесты — docs/TEST_RESULTS.txt.
<!-- EXPERT_REFERENCE_END -->

<!-- LLM_PILOT_START -->
## Контекстная разметка сеансом Codex — завершено, 2026-11-02

Размечены **1 017 / 1 017 аналитических единиц (100%)**. В продолжении добавлены **477**, первоначальные **540 сохранены побайтово без изменений**. Последний ID — 1050; необработанных допустимых ID нет. 33 исключённые исходным конвейером единицы не возвращались. Добавления сохранялись последовательными партиями 60, 100, 100, 100, 96, 5, 16. Все 21 корейскоязычная единица прочитаны на оригинальном языке.

Версия `DRI-LLM-pilot-1`, метод `codex_contextual_model`. Смысловые оценки, русские пересказы и объяснения созданы непосредственно моделью в сеансе. Python только читает, проверяет, сохраняет и агрегирует результаты. Старые словарные/контекстные категории не заменяли новую оценку: из реестра v0.2 использовались только идентификаторы и хэши. Точная серверная модель неизвестна: `model_id: null`. Это **модельная разметка, не независимый экспертный эталон**.

`unit_id`, `statement_ids`, `input_text_sha256` проверены для всех записей. Исходное определение единицы и тексты не изменены, похожие выступления не объединялись. Полнота исходного материала: 8 `complete_speech`, 5 `complete_official_statement`, 10 `selected_turns_partial_floor`, 864 `sentence_excerpt`, 87 `short_quote_fragment`, 43 `legacy_excerpt`. Итого 13 полных и 1004 частичных единицы по сохранённым признакам, а не по длине. Завершённость разметки не означает полноту выступлений или исторического покрытия.

Для парламентских текстов соседние реплики служат контекстом адресата и авторства. Оценка частичной единицы ограничена её сохранёнными фрагментами: весь протокол не приписывается одному автору, невыбранные реплики не превращаются в дополнительные сигналы. Например, 1035 — вопрос о GSOMIA, не собственный призыв к разрыву; 1037 — собственное предложение предупредить о сильных ответных мерах, интенсивность 3; 1039/1042 — критика своего министра, не обвинение Японии; 1043 — взаимная деэскалация; 1049 — поддержка соглашения, а его отрицательные характеристики цитируются и отвергаются. Для 1036 оценивается сохранённое требование отмены японских мер, без переноса позиции из других ответов министра.

### Состав разметки
| Группа | Конфронтация | Сотрудничество | Смешанные | Нейтральные | Нерелевантные | Неопределённые | Всего |
|---|---:|---:|---:|---:|---:|---:|---:|
| ROK | 59 | 12 | 4 | 3 | 0 | 32 | 110 |
| JPN | 45 | 319 | 2 | 315 | 183 | 43 | 907 |
| Всего | 104 | 331 | 6 | 318 | 183 | 75 | 1017 |

| Группа | Конфронтация | Сотрудничество | Смешанные | Нейтральные | Нерелевантные | Неопределённые | Всего |
|---|---:|---:|---:|---:|---:|---:|---:|
| en | 53 | 3 | 1 | 0 | 0 | 32 | 89 |
| ja | 45 | 319 | 2 | 315 | 183 | 43 | 907 |
| ko | 6 | 9 | 3 | 3 | 0 | 0 | 21 |

| Группа | Конфронтация | Сотрудничество | Смешанные | Нейтральные | Нерелевантные | Неопределённые | Всего |
|---|---:|---:|---:|---:|---:|---:|---:|
| foreign_ministry | 79 | 162 | 1 | 89 | 10 | 46 | 387 |
| government | 6 | 74 | 2 | 47 | 27 | 4 | 160 |
| head_of_state_administration | 1 | 4 | 0 | 0 | 0 | 0 | 5 |
| parliament | 8 | 21 | 3 | 68 | 67 | 8 | 175 |
| unknown | 10 | 70 | 0 | 114 | 79 | 17 | 290 |

Неопределённых **75 (7,37%)**, нерелевантных **183 (17,99%)**. В средней участвуют **759** определённых содержательных единиц, из них **110** конфликтных, включая смешанные. Республика Корея: 110 размеченных / 78 в средней; Япония: 907 / 681. Каналы публикации и институт говорящего различаются: выступление министра в парламенте не получает автоматически тип «парламент». Категория `unknown` не заполнялась предположениями. Институциональные веса отсутствуют.

### Покрытие и единый экспериментальный показатель

Разметка присутствует в **118 месяцах**, содержательные определённые наблюдения — в **106** (ROK — 54, JPN — 82; множества пересекаются). CSV содержит 144 календарных месяца; ноябрь–декабрь 2026 вне периода исходной выборки до 31.10.2026. Внутри периода 24 месяца без исходных единиц; ещё 12 имеют только неопределённые/нерелевантные записи.

Единственный общий экспериментальный DRI — прежняя арифметическая средняя интенсивности 0–3 среди `confrontational`, `cooperative`, `mixed`, `neutral` месяца. Метод не менялся. Для mixed используется конфликтная интенсивность, сотрудничество сохраняется отдельно. `uncertain` и `irrelevant` исключены из знаменателя; отсутствие данных не заменяется нулём. Доли неопределённых и нерелевантных делятся на число размеченных. `conflict_including_mixed` — вспомогательное количество, не отдельный индекс.

`data/dri_llm_monthly.csv` содержит месячные исходные/размеченные/оцениваемые количества, категории и состав институтов. `country_results` содержит раздельные количества, категории и описательные средние по ROK/JPN; это разложение общего ряда, не новые модели. На обновлённом `docs/DRI_llm_pilot.png` показан один общий ряд и отдельные объёмы двух стран. График визуально проверен.

`low_volume` означает **1–4 определённых содержательных единицы за месяц**. Это описательная отметка малой выборки, не эмпирически валидированный порог и не фильтр: такие месяцы остаются в ряду. Аналогичные флаги сохранены для каждой страны. Месяцы без определённых наблюдений имеют пустую среднюю, а не этот флаг.
Малый объём — **51 месяцев**: 2015-04, 2015-05, 2015-06, 2015-07, 2015-09, 2015-10, 2016-01, 2016-02, 2016-05, 2016-08, 2016-11, 2016-12, 2017-01, 2017-02, 2017-03, 2017-04, 2017-08, 2017-09, 2018-07, 2018-10, 2019-03, 2019-06, 2019-08, 2020-04, 2020-07, 2020-09, 2020-10, 2020-12, 2021-05, 2021-07, 2021-10, 2021-12, 2022-01, 2022-04, 2022-06, 2023-02, 2023-07, 2023-10, 2024-01, 2024-07, 2024-10, 2024-11, 2025-07, 2025-08, 2025-09, 2025-12, 2026-01, 2026-02, 2026-07, 2026-08, 2026-10.

| Год | ROK: единиц / в средней | JPN: единиц / в средней | Месяцев с содержательными наблюдениями |
|---|---:|---:|---:|
| 2015 | 10 / 9 | 63 / 35 | 9 |
| 2016 | 8 / 8 | 57 / 38 | 10 |
| 2017 | 12 / 12 | 69 / 51 | 10 |
| 2018 | 9 / 1 | 54 / 42 | 4 |
| 2019 | 16 / 12 | 69 / 50 | 8 |
| 2020 | 10 / 4 | 41 / 29 | 9 |
| 2021 | 8 / 4 | 43 / 34 | 8 |
| 2022 | 8 / 3 | 104 / 79 | 9 |
| 2023 | 6 / 5 | 166 / 143 | 10 |
| 2024 | 7 / 6 | 103 / 74 | 10 |
| 2025 | 9 / 8 | 82 / 59 | 10 |
| 2026 | 7 / 6 | 56 / 47 | 9 |

### Проверки и воспроизводимость

Пройдены проверки: все 1017 уникальных ID точно совпадают с допустимой выборкой; все связи и хэши совпадают; первоначальные 540 строк сохранены побайтово; неправильные хэши, связи, категория и булева интенсивность отклоняются; повторный импорт **всех 1017** не изменяет JSONL; повторная агрегация даёт идентичные CSV и PNG; 144 месяца и суммы знаменателей согласованы, страновые количества сходятся с общими; пропуски не превращены в нули; флаги малого объёма проверены. CSV не содержит исходных текстов, резюме или объяснений. SQLite integrity_check=ok, foreign_key_check без ошибок. Это целевые технические проверки, не повторный запуск всех исторических тестов проекта и не оценка точности смысловых меток.

Все 12 защищённых файлов (SQLite, v0.1/v0.2, экспертный реестр и XLSX) совпадают с исходными SHA256. SQLite остаётся **1444 документа / 1050 заявлений / 1070 цитат, схема 4**. Исходные 540 строк имеют SHA256 `85625a625be616c6505832678e68e3b6644a4c9c0d16a3152ffb8ff6c30cf905`.

Команда повторного расчёта из корня проекта:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts/annotate_llm_pilot.py aggregate
```

Воспроизводимость относится к агрегированию фиксированных меток, не к обещанию идентичной новой оценки моделью. JSONL остаётся внутренним исследовательским файлом и исключён из обычного git-добавления. Новых зависимостей, внешних API, миграций, баз и экспертных ответов не создавалось.

Изменены только файлы этого этапа: `data/dri_llm_annotations.jsonl`, `data/dri_llm_monthly.csv`, `docs/DRI_llm_pilot.png`, `scripts/annotate_llm_pilot.py`, данный `docs/QUALITY_REPORT.md`.

SHA256 артефактов:
- `data/dri.sqlite3`: `e8e02da5cae21a6f578450bbb58a95a245739211fdecfb8375e43460721b9a42`.
- `data/dri_llm_annotations.jsonl`: `d87d8e86daa1b0a670e9acfbc737121762b55d2a1d631076a59d26079b5b0a0b`.
- `data/dri_llm_monthly.csv`: `10948b58e6c22e640b156a88b65e9b942f5ca465d6ba76551f14a456849491e1`.
- `docs/DRI_llm_pilot.png`: `3104f41c588fbcc41541153c823cf0a1d1ba0cb69ef9a9d2e715db8a776dd370`.

**Итог:** доступная аналитическая выборка полностью размечена и технически готова к отдельному ретроспективному сопоставлению. Историческая проверка не начиналась. Ряд пока экспериментальный и невалидированный: преобладают японские единицы и фрагменты, корейские исходники неоднородно отобраны, есть месяцы с единичными наблюдениями и неизвестной институциональной атрибуцией. Завершение разметки не устраняет эти смещения и не подтверждает прогностическую значимость. На этом этап завершён.
<!-- LLM_PILOT_END -->

<!-- HISTORICAL_EXPERIMENT_START -->
## Первый исторический эксперимент — 2026-11-02

Формула, данные и все 1017 оценок зафиксированы SHA256 в `data/dri_historical_manifest.json`. SQLite, JSONL, исходный месячный CSV, v0.1/v0.2 и экспертные файлы не менялись. Используется прежняя средняя интенсивности 0–3 без весов; ни словари, ни оценки не пересматривались. Скрипт — `scripts/historical_experiment.py`, таблица — `data/dri_historical_check.csv`, график — `docs/DRI_historical_check.png`.

### Исторические ориентиры

Даты подтверждены внешними первоисточниками независимо от значений DRI. Источники сторон подтверждают их действия, но не являются нейтральными оценками конфликта. Направления ниже — гипотезы для описательного сопоставления.

| Даты | Эпизод | Ожидание | Первоисточники |
|---|---|---|---|
| 2015-12-28 | Comfort women agreement | снижение | [источник 1](https://2009-2017.state.gov/secretary/remarks/2015/12/250874.htm) |
| 2016-11-23 | GSOMIA signing | снижение | [источник 1](https://www.defense.gov/News/Releases/Release/Article/1012704/statement-by-secretary-of-defense-ash-carter-on-signing-of-the-japan-rok-genera/) |
| 2018-10-30 | Forced labor judgment | рост | [источник 1](https://www.scourt.go.kr/eng/supreme/decisions/NewDecisionsView.work?mode=6&pageIndex=1&searchWord=&seq=400) |
| 2019-07-01 | Export controls announcement | рост | [источник 1](https://www.meti.go.jp/policy/external_economy/export_control_korea/index-en.html) |
| 2019-08-22 | GSOMIA termination announced | рост | [источник 1](https://www.korea.kr/briefing/presidentView.do?newsId=148863963) |
| 2023-03-06; 2023-03-16 | Compensation plan and summit | снижение | [источник 1](https://www.mofa.go.kr/us-ko/brd/m_4487/view.do?seq=1347533); [источник 2](https://japan.kantei.go.jp/101_kishida/diplomatic/202303/_00009.html) |

01.07.2019 — объявление мер, не вступление их в силу 04.07. Прямой материал METI вернул 403; повторных запросов и обхода не было. Дата подтверждена официальной индексной страницей. 22.08.2019 — объявление о прекращении GSOMIA, а не фактическое прекращение. Две даты марта 2023 образуют один эпизод.

### Процедура

До вычисления сравнений определены календарные окна −3…−1, месяц события, +1…+3. Контроль — все остальные месяцы до 31.10.2026: 106 из 142; объединение окон — 36 месяцев. Контроль не подбирался по графику. Окна июля и августа 2019 пересекаются и статистически зависимы.

Месяц с 1–4 определёнными содержательными наблюдениями недостаточен. Пропуск — месяц без таких наблюдений, а не оценка доли всей исторически существовавшей риторики. Для сравнения трёхмесячной фазы требуются ≥5 единиц в каждом из трёх месяцев. Это консервативное правило полноты, не подогнанный порог величины сигнала. Средние фаз равновзвешивают прежние месячные DRI, не создавая нового индекса.

Строки `episode_phase`: предшествующая фаза сравнивается со средней 38 достаточно наполненных контрольных месяцев (0,199698); событие и последующая фаза — с предшествующей фазой. Ни у одного эпизода нет полной предшествующей фазы, поэтому все 18 фазовых сравнений имеют статус «оценить невозможно». Частичные средние сохранены отдельно, без вывода о надёжности.

Строки `episode_month`: все 42 наблюдения окон, разности с непосредственно предыдущим месяцем только при ≥5 единицах в обоих. Для первого месяца окна предыдущий может лежать за его границей; правило одинаково для всех. Это локальное описание, не замена полному фазовому выводу. Строки `control_month`: все 106 контрольных месяцев; изменение рассчитывается только для последовательных календарных пар, оба месяца которых вне окон и достаточно наполнены. Используется знак разности без оптимизации порога эффекта. Это ретроспективный описательный протокол, не пререгистрация.

### Результаты

| Эпизод | Достаточно наполненных месяцев до / в / после | Наблюдаемый результат |
|---|---|---|
| 28.12.2015 | 1/3; 1/1; 1/3 | Ноябрь→декабрь 0→1,167 (n=9→6): одновременное изменение противоположно ожидаемому снижению |
| 23.11.2016 | 2/3; 0/1; 0/3 | Сентябрь→октябрь 0→0; в ноябре n=4. Опережающее изменение не обнаружено, реакцию оценить невозможно |
| 30.10.2018 | 0/3; 0/1; 2/3 | Ноябрь→декабрь 0,353→1,167 (n=34→6): запаздывающий рост в +2 месяце; в октябре n=2 |
| 01.07.2019 | 1/3; 1/1; 1/3 | Июль 0,900 (n=10), июнь n=4: уровень в месяц объявления повышен, надёжно определить изменение невозможно |
| 22.08.2019 | 2/3; 0/1; 2/3 | Октябрь→ноябрь 0,353→0,364 (n=17→11): малый запаздывающий рост +0,011 без утверждения значимости; август n=1 |
| 06/16.03.2023 | 2/3; 1/1; 3/3 | До события декабрь→январь 0,286→0,600 против ожидания; март→апрель 0,120→0,095, апрель→май 0,095→0: последующее снижение; февраль n=1 |

По локальным месячным сравнениям: **до события 0 эпизодов** с изменением ожидаемого знака (сопоставимые пары есть у 2: без изменения либо противоположное направление); **в месяц события 0** (сопоставим только декабрь 2015, знак противоположный); **после события 3** (2018, август 2019, март 2023, ожидаемый знак хотя бы в одной доступной паре). Остальные случаи недостаточны. Эти числа не являются долями успешных прогнозов. Полное трёхмесячное опережение оценить невозможно для всех 6 эпизодов. Июльская риторика перед августом 2019 совпадает с другим выбранным событием и не доказывает независимого опережения.

Вне окон: 106 контрольных месяцев, 38 достаточно наполненных; **20 сопоставимых соседних пар — 10 ростов, 7 снижений, 3 без изменения**. Для остальных 86 месячных строк сравнение недоступно. Все месяцы сохранены, включая пропуски. Изменения вне окон — несопоставленные колебания, а не доказанные ложные тревоги: семь ориентиров не составляют полного календаря отношений, формального правила тревоги нет. Коэффициенты и пороги сигнала под историю не подбирались.

### Все месяцы окон

`n` — определённые содержательные единицы; DRI здесь показывается и при малом n, с явной отметкой недостаточности. В CSV дополнительно приведены все размеченные количества, страновые доли пропусков и контрольные месяцы. Страновые количества показывают направление источника, не создают новые индексы.

| Эпизод | Месяц | DRI | n | ROK n | JPN n | Пропуск | Малый объём |
|---|---|---:|---:|---:|---:|---:|---|
| 2015_agreement | 2015-09 | 0.000 | 3 | 0 | 3 | 0 | да |
| 2015_agreement | 2015-10 | 1.000 | 1 | 1 | 0 | 0 | да |
| 2015_agreement | 2015-11 | 0.000 | 9 | 0 | 9 | 0 | нет |
| 2015_agreement | 2015-12 | 1.167 | 6 | 6 | 0 | 0 | нет |
| 2015_agreement | 2016-01 | 1.000 | 1 | 1 | 0 | 0 | да |
| 2015_agreement | 2016-02 | 2.000 | 1 | 1 | 0 | 0 | да |
| 2015_agreement | 2016-03 | 0.125 | 8 | 1 | 7 | 0 | нет |
| 2016_gsomia | 2016-08 | 1.500 | 2 | 2 | 0 | 0 | да |
| 2016_gsomia | 2016-09 | 0.000 | 7 | 0 | 7 | 0 | нет |
| 2016_gsomia | 2016-10 | 0.000 | 6 | 0 | 6 | 0 | нет |
| 2016_gsomia | 2016-11 | 0.000 | 4 | 0 | 4 | 0 | да |
| 2016_gsomia | 2016-12 | 0.250 | 4 | 1 | 3 | 0 | да |
| 2016_gsomia | 2017-01 | 1.000 | 2 | 2 | 0 | 0 | да |
| 2016_gsomia | 2017-02 | 1.500 | 2 | 2 | 0 | 0 | да |
| 2018_judgment | 2018-07 | 1.000 | 1 | 1 | 0 | 0 | да |
| 2018_judgment | 2018-08 | — | 0 | 0 | 0 | 1 | нет |
| 2018_judgment | 2018-09 | — | 0 | 0 | 0 | 1 | нет |
| 2018_judgment | 2018-10 | 0.500 | 2 | 0 | 2 | 0 | да |
| 2018_judgment | 2018-11 | 0.353 | 34 | 0 | 34 | 0 | нет |
| 2018_judgment | 2018-12 | 1.167 | 6 | 0 | 6 | 0 | нет |
| 2018_judgment | 2019-01 | — | 0 | 0 | 0 | 1 | нет |
| 2019_exports | 2019-04 | — | 0 | 0 | 0 | 1 | нет |
| 2019_exports | 2019-05 | 0.000 | 7 | 0 | 7 | 0 | нет |
| 2019_exports | 2019-06 | 0.000 | 4 | 0 | 4 | 0 | да |
| 2019_exports | 2019-07 | 0.900 | 10 | 10 | 0 | 0 | нет |
| 2019_exports | 2019-08 | 2.000 | 1 | 1 | 0 | 0 | да |
| 2019_exports | 2019-09 | — | 0 | 0 | 0 | 1 | нет |
| 2019_exports | 2019-10 | 0.353 | 17 | 0 | 17 | 0 | нет |
| 2019_gsomia | 2019-05 | 0.000 | 7 | 0 | 7 | 0 | нет |
| 2019_gsomia | 2019-06 | 0.000 | 4 | 0 | 4 | 0 | да |
| 2019_gsomia | 2019-07 | 0.900 | 10 | 10 | 0 | 0 | нет |
| 2019_gsomia | 2019-08 | 2.000 | 1 | 1 | 0 | 0 | да |
| 2019_gsomia | 2019-09 | — | 0 | 0 | 0 | 1 | нет |
| 2019_gsomia | 2019-10 | 0.353 | 17 | 0 | 17 | 0 | нет |
| 2019_gsomia | 2019-11 | 0.364 | 11 | 0 | 11 | 0 | нет |
| 2023_rapprochement | 2022-12 | 0.286 | 7 | 1 | 6 | 0 | нет |
| 2023_rapprochement | 2023-01 | 0.600 | 5 | 2 | 3 | 0 | нет |
| 2023_rapprochement | 2023-02 | 0.000 | 1 | 0 | 1 | 0 | да |
| 2023_rapprochement | 2023-03 | 0.120 | 75 | 1 | 74 | 0 | нет |
| 2023_rapprochement | 2023-04 | 0.095 | 21 | 1 | 20 | 0 | нет |
| 2023_rapprochement | 2023-05 | 0.000 | 19 | 0 | 19 | 0 | нет |
| 2023_rapprochement | 2023-06 | 0.000 | 8 | 0 | 8 | 0 | нет |

### Проверки и воспроизводимость

Повторный запуск дал идентичные CSV, PNG и manifest. Проверены 6 эпизодов, 18 фаз, 42 месячные строки, 106 контролей без пересечения с окнами, суммы стран, диапазоны долей пропусков, запрет сравнения малонаполненных месяцев и неполных фаз. Все исходные SHA256 совпали после расчёта. График визуально проверен. Зависимости не устанавливались; внешние запросы только подтверждали исторические даты, сбор корпуса не выполнялся.

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts/historical_experiment.py
```

Смысловые метки сделаны ретроспективно моделью; её потенциальное знание истории и отбор корпуса исключают трактовку как независимого прогнозного теста. Преобладают японские источники; месячная агрегация не устанавливает порядок высказывания и события внутри месяца. Официальные соглашения могут сопровождаться протестной внутриполитической риторикой, поэтому ожидание снижения не гарантируется самим фактом соглашения.

**Вывод:** надёжное опережение не установлено; наблюдаются отдельные запаздывающие изменения, противоположная реакция декабря 2015 и колебания вне окон. Главный предел — недостаточное и неоднородное покрытие предшествующих месяцев. Историческое совпадение не доказывает прогностическую способность.
<!-- HISTORICAL_EXPERIMENT_END -->

## Независимый календарь дипломатических действий

Срез охватывает даты оценки с 1 января 2015 года по 5 ноября 2026 года. В нём 30 подтверждённых действий, 26 различных URL в поле первоисточника и 58 разных URL с учётом дополнительных подтверждений. Действия отбирались по документам и сообщениям о событиях. Значения DRI и оценки риторики не использовались при отборе.

| Год | Эскалация | Сотрудничество | Нейтральное действие | Всего |
|---|---:|---:|---:|---:|
| 2015 | 1 | 1 | 0 | 2 |
| 2016 | 0 | 1 | 0 | 1 |
| 2017 | 1 | 1 | 0 | 2 |
| 2018 | 2 | 0 | 0 | 2 |
| 2019 | 4 | 1 | 0 | 5 |
| 2020 | 2 | 0 | 1 | 3 |
| 2021 | 1 | 0 | 0 | 1 |
| 2022 | 0 | 1 | 0 | 1 |
| 2023 | 0 | 5 | 0 | 5 |
| 2024 | 0 | 2 | 0 | 2 |
| 2025 | 1 | 1 | 0 | 2 |
| 2026 по 5 ноября | 2 | 2 | 0 | 4 |
| Всего | 14 | 15 | 1 | 30 |

### Правила `DRI-event-action-1`

Включается действие Республики Корея или Японии с наблюдаемым двусторонним результатом. Для эскалации это принятая ограничительная мера, формальное обращение в ВТО, дипломатический отзыв или формальное уведомление об изменении режима соглашения. Судебное решение включается при документированном дипломатическом последствии, например официальном представлении через посольство. Для сотрудничества учитываются подписанные документы, согласованные механизмы и фактическое восстановление сообщения или дипломатического взаимодействия. Общая санитарная мера Японии в марте 2020 года имеет нейтральную метку, а отдельно принятое адресное ответное решение Сеула имеет метку эскалации.

Заявления о намерениях, пересказы и обычные переговоры не создают самостоятельных событий. Объявление принятой меры и её вступление в силу образуют одну запись, если второе лишь выполняет первое. Дата действия соответствует стадии, указанной в описании. Для GSOMIA в августе 2019 года действие датировано 23 августа по отправленному уведомлению, первое подтверждённое сообщение датировано 22 августа. Последующее приостановление уведомления и его окончательный отзыв являются отдельными изменениями состояния соглашения. Дата первого публичного сообщения означает самую раннюю подтверждённую дату среди проверенных материалов.

Код KOR GDELT соответствует Республике Корея. Включаются строки с явными кодами KOR и JPN по двум акторам. Строки с КНДР исключены. Данные GDELT 1.0 и 2.0 имеют отдельные пространства идентификаторов. CAMEO в выгрузке относится к связанному машинному упоминанию и сохраняется в исходном виде. Класс действия определяется по проверенным документам.

### Воспроизводимость

Реестр проверенных действий находится в `config/dri_event_actions.jsonl`. В основной SQLite схема 5 добавляет `diplomatic_actions`, `diplomatic_event_candidates` и таблицу связей. Резервная копия перед миграцией находится в `data/backups/pre-schema-005.sqlite3`. Сравнение с ней подтвердило сохранность содержимого всех прежних таблиц, кроме добавленной записи журнала миграций. Для прежнего пилота проверка неизменности теперь использует хэши входного корпуса и разметки, чтобы обновление событийных таблиц не блокировало его чтение.

Обработаны 12 дневных архивов [GDELT Event Database 1.0](https://data.gdeltproject.org/events/index.html), по одному на год. Дни выбраны около документированных действий для пилотного поиска подтверждений. На диске сохранена только фильтрованная выборка с исходными идентификаторами, адресами архивов и SHA256. Получено 2 654 уникальные строки GDELT 1.0. Ещё 22 существующие записи GDELT 2.0 включены в очередь кандидатов. В ней 2 676 строк. Связаны с подтверждёнными действиями два архивных упоминания по проверенным статьям Reuters/NDTV и Kyodo/The Japan Times. У остальных кандидатов нет проверенной связи с действием. Неоднозначные совпадения по дате и числу публикаций остаются в очереди.

Один идентификатор события соответствует одному проверенному ключу действия. Точный повтор объединяет подтверждения. Противоречивый повтор отклоняется, а соседние или похожие действия не объединяются автоматически. В текущем реестре 30 разных ключей. На проверочном дубле 31 строка дала те же 30 событий. Повторный расчёт сохранил SQLite и три выгрузки побайтово. Проверены календарные границы, иностранные ключи, структура локального HTML и соответствие всех идентификаторов и ссылок. Все 178 тестов проекта прошли.

Команда из корня проекта работает с сохранённой выборкой и реестром.

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts/update_event_truth.py
```

Для добавления архивного дня к этой же команде передаётся `--fetch-day YYYY-MM-DD`. Параметр можно повторять. Уже сохранённые дни не скачиваются повторно. ZIP читается в памяти, строки фильтруются потоком. Выгрузки `data/dri_event_truth.csv`, `data/dri_event_calendar.csv` и `docs/DRI_events_timeline.html` формируются из подтверждённых действий.

### Календарь целевой переменной

Для даты оценки `t` интервал равен `[t+1, t+30]`. События дня оценки исключены. Положительная метка требует хотя бы одной подтверждённой эскалации. Отрицательная метка требует отсутствия найденных эскалаций и проверенного покрытия всех 30 дней официальными каналами обеих стран и независимым каналом. Остальные метки пусты в CSV и соответствуют `null`. Параметр `--reviewed-coverage` принимает JSON со списком проверенных интервалов и полями `start`, `end`, `reviewer`, `scope_notes`, `rok_sources`, `jpn_sources`, `independent_sources`. Ссылки в трёх последних полях задаются списками. Признаки будущих событий конвейер не формирует.

Из 4 327 дат оценки **400 имеют метку 1, 0 имеют метку 0, 3 927 имеют метку null**. Из пустых меток 3 920 связаны с недостаточным историческим покрытием, 7 относятся к правому краю среза без известной эскалации и с ещё не истёкшим горизонтом. Недостаточное покрытие встречается во всех 12 годах. Выборочный поиск и единичные дневные архивы не дают ни одного сплошного проверенного 30-дневного окна для отрицательного класса. Календарь пригоден как реестр известных положительных примеров. Для обучения и проверки бинарного прогноза ещё нужны подтверждённые отрицательные окна.

## Прогнозный эксперимент на 30 дней после восстановления исторических дат

При прежнем минимуме в пять единиц Strict воспроизводит исходные **3 из 141** оценённых дат. Retrospective даёт **110 из 141**, то есть на 107 больше, включая девять положительных дат. Это сценарное восстановление на основе уже размеченных текстов. В его оценённых окнах 93,0% содержательных единиц используют прокси-дату. Доля рассчитана по всем вхождениям единиц в окна, поэтому одна единица может учитываться в нескольких срезах.

### Происхождение временных меток

У 92 из 1017 единиц дата публикации содержится в метаданных документа, использованного для разметки. Ещё у 925 есть датированное выступление и подтверждённое получение из официального источника. Это 907 японских парламентских единиц, 16 единиц из корейских протоколов и 2 официальных корейских выступления. У японского API дата относится к заседанию, у корейских протоколов к заседанию, а у двух правительственных страниц метка относится к дню речи. В просмотренных метаданных нет отдельной записи, подтверждающей доступность именно использованного текста или его публичную трансляцию в исторический день. У этих единиц дата публикации по-прежнему неизвестна.

Strict использует дату публикации каждого документа, из которого взят размеченный фрагмент. Если дата отсутствует, первая зафиксированная загрузка из публичного источника задаёт границу доступности. Время получения переведено в UTC+9. Эта граница обозначается `collector_capture_bound` и хранится отдельно от публикаций. Дата получения даёт основание использовать документ с этого момента.

Retrospective сохраняет известную дату публикации. Для недатированных официальных документов трёх указанных источников используется подтверждённая дата речи как `speech_date_proxy`, только когда дата в метаданных документа совпадает с датой высказывания. При отсутствии такого совпадения используется граница по получению. В обоих режимах дата доступности единицы берётся по самой поздней из допустимых дат её фрагментов и связанных дат заявления. Для каждого среза CSV хранит режим, минимум наблюдений, количества единиц по основаниям датировки, долю прокси и самую позднюю дату доступности среди включённых содержательных единиц.

### Неизменные условия эксперимента

Есть 144 месячных даты в 2015–2026 годах, из них 141 с завершённым горизонтом `[t+1, t+30]` и три с пустой меткой из-за правого края календаря. Основной сценарий содержит 13 положительных и 128 предварительно отрицательных дат. Сценарий без судебных решений содержит 8 и 133 соответственно. Метка `0_provisional` означает отсутствие эскалации в текущем реестре. SQLite, исходная разметка и событийные метки сохранены.

Единица должна быть произнесена в последние 90 дней включительно и доступна к дате оценки по выбранному режиму. Формула и порог прежние: средняя интенсивность плюс положительное изменение между двумя 45-дневными половинами, максимум 3 балла, предупреждение от 1. При пустой половине добавка отсутствует. Минимум 1, 3 или 5 меняет только доступность прогноза. Окна с 1–2 и 3–4 единицами помечены отдельно. Хронологический baseline использует сглаженную частоту только завершённых и публично известных к дате прогноза исходов. Его порог предупреждения по-прежнему 0,5.

### Покрытие и предупреждения

«События» в таблице — уникальные зарегистрированные события, попавшие в окно предупреждения. Одно окно может содержать несколько событий. «Без совпадения» означает предупреждение при предварительной отрицательной метке.

| Режим | Минимум | Оценено из 141 | Положительные даты | Исключено | События | Без совпадения | Опережение, дней | Доля прокси |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| Strict | 1 | 102 | 7 | 39 | 7 | 88 | 6, 11, 18, 25, 29, 30, 30 | 0% |
| Strict | 3 | 17 | 0 | 124 | 0 | 17 | — | 0% |
| Strict | 5 | 3 | 0 | 138 | 0 | 3 | — | 0% |
| Retrospective | 1 | 133 | 12 | 8 | 4 | 33 | 2, 11, 23, 30 | 92,3% |
| Retrospective | 3 | 119 | 11 | 22 | 3 | 24 | 2, 11, 23 | 92,8% |
| Retrospective | 5 | 110 | 9 | 31 | 3 | 21 | 2, 11, 23 | 93,0% |

При минимуме 1 в обоих режимах ещё три даты имеют вычислимый балл без завершённого горизонта, поэтому они видны в срезах и отсутствуют в backtest. При минимуме 5 предупреждение от 31.07.2019 приходится за 2 дня до исключения Республики Корея из японского перечня с упрощённым экспортным режимом и за 23 дня до направления уведомления о прекращении GSOMIA. Все 21 единица в этом окне имеют прокси-дату. Предупреждение от 31.08.2019 приходится за 11 дней до запроса консультаций ВТО по DS590. В этом окне 93,3% единиц имеют прокси-дату. Таким образом, три совпавших события приходятся на два прогноза одного кризисного периода.

При исключении судов число оценённых дат не меняется. Число положительных дат при минимумах 1, 3, 5 составляет 3, 0, 0 в Strict и 7, 7, 6 в Retrospective. Число предупреждённых событий составляет соответственно 3, 0, 0 и 3, 3, 3. Число предупреждений без зарегистрированного события составляет 92, 17, 3 и 34, 24, 21.

На 110 общих датах Retrospective с минимумом 5 AP составляет 0,093 у скоринга и 0,078 у baseline. ROC AUC составляет 0,475 и 0,415. Без судебных решений AP составляет 0,075 и 0,062, а ROC AUC 0,470 и 0,505. Эти значения условны относительно реестра. Результат зависит от сценария, а совпадения сосредоточены в 2019 году. Устойчивое преимущество не установлено.

### Причины оставшихся пропусков и проверка

В Strict при минимуме 5 из 138 пропусков 21 не имеет доступной датированной единицы, 18 имеют только нерелевантные или неопределённые единицы, 99 имеют 1–4 содержательные единицы. Все 13 положительных дат Strict имеют от нуля до двух содержательных единиц. В Retrospective из 31 пропуска три относятся к январю–марту 2015 года, где в окнах нет подходящих единиц. Ещё пять имеют только нерелевантные или неопределённые единицы, а 23 имеют 1–4 содержательные. Четыре недоступные положительные даты Retrospective при минимуме 5: 30.04.2015 (4), 31.05.2018 (0), 30.09.2018 (1) и 30.09.2026 (3).

Сверены исходные результаты Strict с минимумом 5, одинаковые целевые метки всех режимов, временные ограничения для речевых единиц, граница зрелости baseline и суммы единиц по происхождению дат. Синтетические граничные проверки подтвердили исключение поздней публикации, будущего выступления и прокси из Strict. Повторный запуск воспроизвёл 864 строки срезов, 968 строк backtest и PNG побайтово. Хэши SQLite и четырёх входных файлов совпали до и после.

Команды из корня проекта:

```powershell
.\.venv\Scripts\python.exe scripts/prediction_backtest.py
.\.venv\Scripts\python.exe scripts/prediction_backtest.py --date 2019-07-31 --mode retrospective --min-units 5
```

Первая команда обновляет обе таблицы и один график. Для воспроизведения старого сравнения в таблицах выбираются `mode=strict` и `min_units=5`. Расчёт одной даты без дополнительных параметров использует тот же режим. График показывает оба режима при минимуме 5, даты событий, объём доступных единиц и долю прокси.

## Независимая событийная проверка: этап 4

Срез: 01.01.2015–05.11.2026. В прежних прогнозах зафиксированы 90-дневное окно риторики, горизонт `(t, t+30]`, порог DRI ≥1,00, минимум 5 единиц и порог исторической базовой частоты ≥0,50. Баллы, предупреждения и baseline взяты из побайтовой копии прежнего `dri_backtest.csv` с проверкой SHA-256; baseline не переобучался на новых результатах. `dri_prediction_snapshots.csv`, речевой корпус, разметка и прогнозная формула сохранены. Старый статический PNG иллюстрирует этап 2; интерактивный Backtest использует актуальный календарь.

**Проверка событий.** Критерий — датированное существенное действие в отношениях двух стран: в частности, введение ограничения, формальный запуск межгосударственной процедуры, конкретный официальный ответ на материальное действие, отмена согласованного участия, значимое оперативное действие или решение суда с установленным двусторонним последствием. Слова без действия, повторы и планируемые меры без подтверждения принятия исключены. Обычный территориальный комментарий, даже если он опубликован официально, сам по себе не эскалация. Для спорных морских и военных фактов фиксируются официально подтверждённые действия или протест, без принятия позиции о юрисдикции и без утверждений о спорном применении радара.

Поиск проведён по годам без фильтра по баллам или предупреждениям: [архив двусторонних отношений МИД Японии](https://www.mofa.go.jp/region/asia-paci/korea/archives.html), [Diplomatic Bluebook](https://www.mofa.go.jp/policy/other/bluebook/index.html), [текущий раздел МИД Японии](https://www.mofa.go.jp/region/asia-paci/korea/), [тематический архив МИД Республики Корея](https://www.mofa.go.kr/www/wpge/m_3459/contents.do), [архив ВТО](https://www.wto.org/english/news_e/archive_e/country_subj_arc_e.htm?country1=KOR&subject1=DISP) и датированные документы компетентных ведомств. В [GDELT Events 1.0](https://data.gdeltproject.org/events/index.html) к 12 прежним дням добавлено 15 февраля каждого года 2015–2026, независимо от наличия предупреждения: 579 новых машинных строк, всего 3 233 в 24 днях. Коды и совпадения названий стран использованы для поиска кандидатов; не подтверждают событие сами по себе. Публикации о КНДР, о прошлых действиях и о возможных будущих мерах не повышали метку. В реестре 53 действия (+23), из них 35 эскалационных (+21), 17 кооперативных и 1 нейтральное. По годам (2015…2026): 2, 4, 2, 5, 8, 5, 2, 2, 9, 5, 4, 5. Идентификаторы прежних действий сохранены. У каждой строки есть тип, дата, источник, обоснование и для эскалаций ключ эпизода.

Это поиск на всём историческом интервале, но не сплошная проверка всех дней по трём независимым каналам. В дневном календаре 869 окон с действием, 3 451 с недостаточным покрытием, 7 с незавершённым горизонтом и 0 с проверенным отсутствием. Набор годовых обзоров и точечных архивов недостаточен для подтверждения отрицательного исхода. Положительный исход подтверждает, что действие было; число положительных окон и событий остаётся нижней границей.

**Эпизоды.** Первое документированное эскалационное действие определяет начало. Последующие действия считаются отдельными проверяемыми фактами, но не новыми успехами в выявлении того же кризиса. Например, DS571 и DS594 — один спор о судостроении; дело о принудительном труде 2018 года, формальные обращения по договору, экспортные меры, GSOMIA и DS590 — одна цепочка до нормализации 2023 года; новая волна судебных решений после плана компенсаций — отдельная. Ответные заявления по одному и тому же действию не создают нового события. В основном варианте расширенные учения Докто в августе 2019 года — отдельный эпизод: у программы учений есть собственная предыстория, корейская сторона не называла Японию единственной целью. Поскольку учения совпали с торговым кризисом и реакцией на него, команда также считает более консервативный вариант с объединением.

| Показатель, минимум 5 единиц | Strict | Retrospective |
|---|---:|---:|
| Оценённых окон из 141 завершённого | 3 | 110 |
| С подтверждённым действием | 0 | 18 (ранее 9) |
| С подтверждённым отсутствием | 0 | 0 |
| Неопределённых среди оценённых | 3 | 92 |
| Предупреждений всего | 3 | 23 |
| Предупреждений с действием | 0 | 3 (ранее 2) |
| Проверенных предупреждений без действия | 0 | 0 |
| Предупреждений с неизвестным исходом | 3 | 20 (ранее 21 без совпадения) |
| Предупреждение до начала эпизода | 0 | 2 |
| Начало пропущено при наличии прогноза | 0 | 7 |
| Начало без доступного прогноза | 15 | 6 |

Новый совпавший прогноз — 29.02.2016, за 15 дней до [открытия спора ВТО DS504](https://www.wto.org/english/news_e/news16_e/ds504rfc_15mar16_e.htm). Отдельно закодированным [учениям Докто](https://en.yna.co.kr/view/AEN20190825000656315) предшествовал сигнал за 25 дней. При объединении учений с торговым кризисом остаётся один обнаруженный эпизод. При исключении судебных решений из целевых действий в Retrospective 12 известных положительных окон и те же 3 предупреждения; 2 начала обнаружены, 6 пропущены при наличии прогноза, 5 без прогноза. В Strict нет прогноза перед началом ни одного из 13 оставшихся эпизодов.

На известных положительных окнах условный recall Retrospective равен 3/18 (16,7%), baseline — 0/18. По известным началам, для которых был прогноз, результат 2/9 против 0/9. При прежнем пороге baseline предупреждений не выдаёт. Precision Retrospective не идентифицируется: совместимые с текущими данными границы 3/23…23/23 (13,0–100%), Strict — 0–100%. Из-за отсутствия проверенных отрицательных окон AP и ROC AUC с новым реестром не интерпретируются. Превосходство над baseline в реальном прогнозировании не установлено.

**Публикации 2019 года.** Обе даты следуют за началом уже идущей цепочки действий (основной вариант — 30.10.2018; даже без судов она началась до обоих прогнозов). Прежние совпадения с отдельными действиями остаются: 31.07 → 02.08 и 23.08 (2 и 23 дня); 31.08 → 11.09 (11 дней). Новое совпадение 31.07 → 25.08 (25 дней) зависит от группировки только в оценке начала эпизода.

| Дата прогноза | Retrospective: балл; прокси / всего | Strict: доступные единицы; балл |
|---|---|---|
| 31.07.2019 | 1,18; 21/21 | 0; нет |
| 31.08.2019 | 1,73; 14/15 | 1; нет |

Четыре интенсивных единицы 1036, 1037, 1038, 1044 (Кан Гён Хва, Чхон Чжон Бэ, Сон Ён Гиль, Ли Су Хёк) происходят из [официального протокола от 30.07](https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=43902). Дата заседания известна; дата первой публикации полной стенограммы не установлена. Реплики [Кан](https://mobile.newsis.com/view/NISX20190730_0000726455) и [Сона](https://mobile.newsis.com/view/NISX20190730_0000726313) частично опубликованы в день заседания; это не доказывает доступность всего текста этих аналитических единиц. Даже если условно засчитать обе целиком, получатся 2 и 3 единицы при требуемых 5. Для Чхона и Ли подтверждения публикации нужного текста к прогнозу нет. У единицы 126 есть [датированная официальная публикация МИД от 28.08](https://overseas.mofa.go.kr/eg-ar/brd/m_11448/view.do?seq=760641), уже включённая в Strict. Подтверждённой реконструкции обоих сигналов без прокси-дат нет; даты в базе не исправлялись.

**Воспроизведение.** `python scripts/update_event_truth.py`, затем `python scripts/validate_dri_events.py`. Вторая команда переносит из прежнего Backtest баллы и baseline без перерасчёта, меняет только оценку исходов, сравнивает два способа группировки августа 2019 года и выполняет точечную проверку дат публикации. `data/dri_backtest.csv` содержит 968 строк прежних прогнозов по двум режимам, двум определениям эскалации и минимумам 1, 3 и 5; пустой `target_30d` — неизвестный исход.

Прошли 185 автоматических тестов. Повторное обновление сохранило хэши SQLite, реестра, календаря, Backtest, HTML-хронологии и архивной выборки GDELT. Старые таблицы корпуса сверены с резервной копией перед схемой 5; проверка внешних ключей SQLite не выявила нарушений. Backtest проверен в браузере в обоих режимах.


## Корейский парламентский корпус v10.3 — три партии, 7 ноября 2026

В единую SQLite добавлены 185 документов-реплик, 185 связанных высказываний и 185 дословных цитат. Это полные выбранные реплики исследовательской транскрипции, а не полные протоколы заседаний. Все 185 записей содержательно прочитаны и размечены моделью текущей сессии: 100 neutral, 35 confrontational, 46 cooperative, 4 mixed. Один доклад специалиста (review_id=7) сохранён как контекст с analysis_eligible=false; 184 единицы допущены к измерению речевого покрытия. Отдельная институциональная принадлежность свидетеля (review_id=16) не установлена и отмечена unknown. Предыдущие 1017 единиц и их оценки не изменены.

По годам 2015–2026 добавлено: 12, 17, 10, 14, 19, 16, 16, 16, 16, 16, 17, 16. В терминах записей с разметкой баланс изменился с JPN 907 / ROK 110 до JPN 907 / ROK 295; без контекстного доклада — ROK 294. Институциональное происхождение новых записей: 139 депутатских, 44 государственных, 1 свидетель с неустановленной принадлежностью, 1 парламентский специалист. Все произнесены в парламентских процедурах; место выступления не подменяет институт автора.

Для 142 месячных дат оценки от января 2015 до октября 2026 включительно сравниваются неизменные старые единицы и новые доступные по сценарной дате выступления. Минимум 5 единиц каждой страны: 3 → 47 окон; хотя бы по одной единице: 87 → 111; односторонние: 47 → 25; пустые: 8 → 6. Это обеспеченность окна текстами, а не число независимых источников или качество прогноза. В машинном отчёте отдельно посчитаны уникальные авторы и заседания новых единиц. Пустые окна остаются на 31.01, 28.02, 31.03.2015, 31.05, 30.06.2018 и 30.09.2022. Полный перечень односторонних окон сохранён в data/kr_hearings_coverage.json.

Источник: Yang, Kyusik. kr-hearings-data v10.3, https://github.com/kyusik-yang/kr-hearings-data, CC BY 4.0. Четыре Parquet-файла созывов 19–22 сохранены внутри существующей data; реплики прочитаны группами, в SQLite поступают только принятые после чтения записи. Отбор кандидатов широкий тематический, но первые ручные партии предпочитают короткие реплики и ранее не представленные месяцы. Поэтому эти партии не являются случайной или репрезентативной выборкой. Длинные выступления и ещё не прочитанные кандидаты остаются для следующих партий. Октябрь 2026 источником не покрыт.

В data/kr_hearings_review.jsonl сохранены оригиналы и метаданные для проверки; config/kr_hearings_semantic_review.tsv содержит собственно смысловые решения; data/kr_hearings_annotations.jsonl связывает оценки с ID базы и SHA-256 текста. Идентичность выступления задаётся номером заседания и реплики. В партиях отобрана максимум одна реплика одного автора из заседания; сходные разные выступления сохраняются действующим механизмом possible_duplicate. Повторный импорт дал 0 новых документов, заявлений и цитат. Дата публикации остаётся NULL, дата релиза не используется как историческая доступность. Первичные ссылки на протоколы сохранены, но новая сверка каждой транскрипции с официальным оригиналом не выполнялась; статус честно указывает исследовательскую транскрипцию и смысловую проверку Codex, не независимую экспертную верификацию.

Старый прогноз читает зафиксированные границы прежних таблиц (config/dri_frozen_row_limits.json). Проверяются прежние хэши аналитического среза и разметки. Событийный реестр, баллы и backtest не пересчитывались. В Streamlit добавлен раскрываемый график покрытия по странам, годам и институтам, явно отделённый от старых прогнозов.

Повторить импорт сохранённой разметки: python scripts/import_hearings.py; обновить покрытие: python scripts/hearings_coverage.py. Продолжение фильтрации: python scripts/read_hearings.py 19 --all-groups (аналогично 20, 21, 22). Уже обработанные непустые группы пропускаются. Новые смысловые решения требуют чтения оригинального текста и явного пополнения TSV; команда не генерирует метки по ключевым словам.

Проверки: выполнено 187 тестов; два UI-теста потребовали адаптации к появлению дополнительного графика. После изменения адресации графиков повторно прошли все 3 UI-теста и 2 теста нового импорта; остальные 182 ранее прошли. Проверены точные хэши текстов, связи цитат, неизвестные даты публикации, уникальность автора внутри заседания, сохранение 1017 старых единиц. PRAGMA foreign_key_check не выявил ошибок. Исходная разметка и prediction_snapshots сохранили прежние SHA-256. Новых кандидатов на дубли действующий механизм не выявил; это не доказательство отсутствия невыявленных смысловых повторов.

## Продолжение выравнивания: четвёртая партия

После трёх партий добавлены ещё 28 прочитанных и размеченных реплик: 14 за 2015 год, 2 за 2018 и 12 за 2022. Общий прирост составляет 213 документов-реплик, заявлений и цитат; 213 оценок, из которых 212 пригодны для анализа риторики и одна относится к контекстному докладу специалиста. Баланс всех размеченных записей: JPN 907 / ROK 323; без контекстного доклада ROK 322.

В 142 исторических окнах ≥5 единиц каждой страны теперь есть в 49 (до расширения 3; после третьей партии 47). Окон хотя бы с одной единицей каждой страны — 114, односторонних — 27, пустых — 1. Рост односторонних окон с 25 до 27 относительно третьей партии объясняется заполнением пяти прежде пустых окон: отсутствие японских единиц не исправляется корейскими репликами. По сравнению с исходным корпусом односторонних окон меньше на 20 (47 → 27). Используются прокси-даты выступлений; историческая публичная доступность новых текстов не подтверждена.

Итоговый прирост по годам 2015–2026: 26, 17, 10, 16, 19, 16, 16, 28, 16, 16, 17, 16. Категории: neutral 115, confrontational 42, cooperative 50, mixed 6. Исходный прогноз и 1017 прежних оценок сохранены; обновлён только отчёт покрытия, который читает существующий Streamlit.

## Двусторонний пересчёт DRI и проверка прогностической ценности

Срез речевого корпуса до 31.10.2026. В расширении 213 размеченных записей Республики Корея, из которых одна ранее отмечена как контекстный доклад специалиста. В расчёт переданы 322 аналитические единицы Республики Корея и 907 Японии. Для каждого окна действуют прежние исключения `uncertain` и `irrelevant` и правила доступности. Новые тексты имеют только прокси-дату выступления, поэтому они входят в Retrospective и не входят в Strict. Оригинальный расчёт сверен по каждой месячной дате с зафиксированными баллами и исходами.

Для общего пула и каждого странового ряда используется прежний балл: средняя интенсивность за 90 дней плюс положительная разница средних двух половин по 45 дней, с ограничением сверху на 3. При пустой половине добавка отсутствует. Нужно не менее пяти единиц в окне. Вариант 50/50 усредняет готовые баллы двух стран при наличии обоих. Порог DRI остался 1,0. Число известных говорящих считается по нормализованным именам внутри страны. Тёзки и варианты написания ограничивают точность оценки уникальных лиц. Повторные реплики по-прежнему входят в среднюю интенсивность, как в исходной формуле, и не увеличивают счётчик говорящих с тем же именем.

Диагностики изменений требуют пяти единиц в каждой сравниваемой группе и наблюдений в обеих половинах. Односторонний рост означает положительное изменение только у одной стороны. Разнонаправленность означает рост у одной и снижение у другой и входит в этот счётчик. В 23 сравнимых Retrospective окнах обе страны выросли одновременно один раз (31.03.2024), односторонний рост наблюдался 13 раз (10 ROK, 3 JPN), разнонаправленность — шесть раз. Для разности изменений парламента и исполнительной власти доступно шесть окон ROK и 12 JPN. МИД включён в исполнительную власть, источники смешанного или неизвестного типа остаются в прочих. Признаки сохранены отдельно и не участвуют в вычислении балла.

| Retrospective, на доступных датах | Дат с прогнозом | Предупреждений | С действием в горизонте | Начал эпизодов обнаружено | Пропущено при наличии прогноза | Без прогноза до начала |
|---|---:|---:|---:|---:|---:|---:|
| Исходный корпус | 110 | 23 | 3 | 2 | 7 | 6 |
| Расширенный общий пул | 123 | 19 | 2 | 1 | 11 | 3 |
| Равный вес стран | 49 | 5 | 0 | 0 | 5 | 10 |
| Baseline на всех завершённых датах | 141 | 2 | 0 | 0 | 15 | 0 |

Все варианты оцениваются на прежнем реестре 53 действий, включая 15 начал эпизодов эскалации, и горизонте `(t, t+30]`. У baseline та же формула исторической частоты со сглаживанием и порогом 0,5. Для новых дат частота рассчитана из того же фиксированного реестра, из окон, завершённых к моменту оценки. Для положительной метки нужна также известная к этому моменту дата первого публичного сообщения хотя бы об одном действии. Две тревоги baseline пришлись на январь и февраль 2015 года, в том числе на старт с априорной частотой 0,5. Сохранённая контрольная таблица прежнего эксперимента остаётся доступна отдельно.

На 110 общих датах исходного и расширенного общего пула обнаружено 2 против 1 начала эпизода, пропущено 7 против 8. Baseline на этих датах не предупреждал. На 49 общих датах всех методов обнаружено одно начало исходным DRI и ноль остальными методами. Действия зарегистрированы в десяти из этих 49 окон. Подтверждённых отрицательных окон нет, поэтому определить precision или превосходство над baseline по точности невозможно. Среди окон с известным действием и доступным баллом условный recall составил 3/18, 2/23 и 0/10 соответственно на собственном покрытии моделей.

Предупреждение до спора ВТО DS504 сохранилось с прежним опережением 15 дней. Вариант 50/50 не имеет балла на этой дате, поскольку в окне нет японских единиц. Предупреждение 31.07.2019 в расширенном пуле исчезло (1,178571 → 0,975), а опережение начала расширенных учений у Докто на 25 дней потеряно. Предупреждение 31.08.2019 о следующем действии в торговом споре сохранилось (11 дней до действия), но этот эпизод уже начался. Общий пул добавил три предупреждения и снял семь. Вариант 50/50 добавил четыре, сохранил одно, снял четыре при доступном балле и не имел балла на 18 прежних датах предупреждения. Даты, исходы и опережение сохранены в вычисленном JSON и показаны в Backtest.

В Strict исходный и расширенный варианты имеют по три одинаковые даты с баллом и предупреждением. Ни одно из них не совпало с зарегистрированным действием. Все 15 начал остались без речевого прогноза и двусторонних дат нет. В Retrospective добавление материалов улучшает покрытие, но в этом историческом эксперименте обнаружение начал ухудшилось. Недостаток подтверждённых дат доступности и отрицательных исходов ограничивает вывод о реальной прогностической ценности.

Прошли 190 тестов, включая интерфейс Streamlit и проверки равного веса стран, границ окна и исключения прокси-дат в Strict. Повторный расчёт подтвердил те же хэши SQLite, разметки, календаря, исходных CSV и вычисленного JSON.


## Перспективный пилот · 8 ноября 2026

Проверены четыре официальных канала. Республика Корея дала четыре новых материала МИД и один парламентский протокол, Япония — одну новую запись NDL и девять просмотренных материалов канцелярии премьера. Из японских правительственных страниц одна содержала подходящий для очереди новый фрагмент. Таким образом, в очереди семь кандидатов. Размечены все семь: четыре кооперативных, два нейтральных и один нерелевантный. Корейский парламентский кандидат касался внутреннего спора о фильме. В нём слово «Япония» оказалось частью названия организации, также обнаружено нарушение порядка колонок PDF. Этот кандидат исключён из расчёта, а фильтр дополнен проверками заголовков страниц и известного ложного совпадения. Другой протокол превысил лимит ответа 4 МБ. Корейский пресс-индекс с поисковыми параметрами вернул петлю перенаправлений, рабочий индекс по опубликованному адресу позволил получить сообщение об обмене молодыми дипломатами от 06.11.2026. Доступность японской парламентской речи подтверждена получением через документированный NDL API, а точная дата первой публикации неизвестна.

Первый выпуск сохранён 08.11.2026 в 20:43:39 МСК. Горизонт 09.11–08.12.2026 включительно. В общем балле 0,00 участвуют семь входов, из них шесть новых. Республика Корея имеет 5 входов и балл 0,00, Япония — 2 входа и недостаточное покрытие для балла. Баланс 50/50 также недоступен. В расчёт вошли правительственные высказывания и сообщения, включая выступление министра в японском парламенте. Собственно депутатского сигнала в первом выпуске нет. Последняя датированная публикация среди новых входов — 6 ноября, актуальная дата подтверждения и выпуска — 8 ноября. Все семь учтённых единиц доступны в строгом режиме. Балл отражает состав этого наблюдаемого окна.

SHA-256 записи `b2a9ddacc715182947cbdcbd4b9a95b07954d181fdbf10a28409cda50076f2b0`. Журнал связывает записи хэшами, проверяет границы горизонта и время доступности входов, блокирует изменение, удаление и замену средствами SQLite. Это локальная проверка с использованием системных часов. Независимая внешняя отметка времени не выпускалась. Повторный импорт и повторный выпуск идемпотентны. Отдельный проход Codex разметил парламентский кандидат как нерелевантный уже после первого выпуска. Запечатанная запись сохранила исходный состав.


## 9 ноября 2026 · три кейса и второй перспективный выпуск

Сбор завершён **2026-11-09 01:14:49.405560 МСК** (UTC 2026-11-08T22:14:49.405560+00:00). После этого новые сетевые материалы для анализа не использовались. Смысловая проверка завершена до выпуска в **01:16:49.605099 МСК**. Исторические документы и оценки не переразмечались.

### Реальное пополнение и ограничения

До этапа: 1664 документа, 1270 заявлений, 1290 цитат, 7 live-оценок. После: **1670 / 1276 / 1296**, 13 live-оценок. Шесть новых записей представляют **четыре разных исходных документа**: два релиза МИД Кореи, одну пресс-конференцию Kantei и один парламентский PDF с тремя извлечёнными фрагментами. Пригодны **3 новые единицы (ROK 2, JPN 1)**; три фрагмента PDF имеют нарушенный порядок колонок и `uncertain`, в расчёт не вошли. Все шесть оценены текущей сессией Codex по оригиналам; платного вызова модели и новой классификации старого корпуса нет.

Получены 7 корейских и 17 японских материалов/страниц за успешные проходы; это показатели сетевой обработки, не 24 новых аналитических документа. Контрольные запросы и результаты сохранены в `source_checks`, идентификаторы — в контексте выпуска. Сначала среда исполнения не разрешала DNS; после штатного разрешённого сетевого запуска сбор состоялся. Это не обход ограничений сайтов.

Сохраняются ограничения: первые 24 ответа на каждый из четырёх запросов NDL; публичные парламентские образцы по пять записей за месяц/каталог и максимум два протокола из ответа, предел ответа 4 МБ; пять страниц корейского архива плюс прежний английский индекс; ограниченные партии Kantei. HTTP 403 японского МИД повторно не обходился. Полнота 90-дневного государственного и парламентского покрытия **не достигнута**. Ни один новый пригодный парламентский фрагмент не добавлен.

### Метод трёх кейсов

`python scripts/research_cases.py` читает защищённые исторические оценки и зафиксированный список live-ID, не пишет SQLite. `data/dri_research_cases.json` содержит единицы, хэши текстов, ссылки, прежние категории, тематические основания с позициями в оригинале, месячные группы и событийные окна. Полные тексты не экспортируются. `data/dri_research_context.json` хранит отсечение, известные события, ограничения и SHA расчётного артефакта; этот контекст включён в запечатанный выпуск.

Пять тем многозначны, выделяются прозрачными выражениями на английском, японском и корейском. Это **лексическая тематическая разметка, не экспертная оценка**. Ненайденная тема не заменяется «другой». Совместное наличие темы и конфликтной категории не доказывает конфликтность именно этой темы в многоаспектной реплике. Прежние смысловые категории и интенсивность не изменяются. Количество реплик показывается отдельно от числа известных говорящих; неизвестные институты остаются `other`.

Для каждого маркера — 90 дней до первого сообщения, дата/интервал первого сообщения, следующие 90 дней (для Садо обрезаны 9 ноября). Мартовские окна пересекаются и относятся к одному эпизоду. Январь 2026 рассматривается с предысторией с 15 октября 2025. Пересчёт прежнего DRI перед каждым событием выполнен отдельно Strict и Retrospective, без изменения формулы или порога.

| Срез до первого сообщения | Retrospective DRI | ROK n | JPN n | Наблюдение |
|---|---:|---:|---:|---|
| 30.06.2019 | 0,00 | 0 | 11 | Нет конфронтационных единиц; 2 кооперативные японские. Корейская сторона отсутствует. |
| 05.03.2023 | 0,5833 | 3 | 9 | В японском правительстве 4 кооперативные из 5 единиц; корейские 3 — конфронтационные, но покрытие мало. |
| 15.03.2023 | 0,2453 | 3 | 50 | Японская кооперация усиливается после уже объявленного плана: это реакция на план, а не независимое предсказание всего эпизода. |
| 12.01.2026 | 0,1538 | 9 | 17 | Кооперативные доли ROK 33,3%, JPN 64,7%; имеются исходные расхождения. |
| 07.09.2026 | 1,4444 | 4 | 5 | Предупреждение на разреженных данных; ни одного упоминания Садо в сохранённых единицах кейса. Нельзя объявлять предсказанием отказа от церемонии. |

В Strict ни один из этих предсобытийных срезов не имеет достаточного n для общего балла. Перед июлем 2019 года Япония: правительство n=5, парламент n=6. После события в фиксированном окне доступны ROK правительство n=5 и парламент n=15, из них 6 конфронтационных/смешанных; отсутствие японского последующего ряда мешает симметричному сравнению. В 2023 после плана правительственная японская кооперация наблюдается рядом с отдельными конфликтными позициями. До января 2026 правительство ROK n=4, парламент n=5, японское правительство n=11, ещё n=6 с неизвестным институтом. Сохранять эти различия принципиально: парламентская площадка не делает выступление министра парламентской позицией.

Садо: официальная страница январского саммита — https://www.kantei.go.jp/jp/104/actions/202601/13korea.html . Отказ Кореи сообщался уже **8 сентября** (https://nwww.newsis.com/view/NISX20260908_0003781575), затем 9 сентября (https://www.ytn.co.kr/_ln/0101_202609091448425895). Это сообщения об официальной позиции, не найденный первичный документ; статус сохранён. Поэтому предсобытийное окно заканчивается 7 сентября. Историческая память и территориальные споры в корпусе не подменяются одной темой Садо. Доказательств специфического раннего сигнала именно по Садо **нет**.

Итог кейсов: сотрудничество и противоречия могут сосуществовать; прежний общий DRI, измеряющий конфронтацию, не является показателем сближения. Кооперативные доли дополняют интерпретацию, но из трёх описательных кейсов нельзя выводить подтверждённую способность предсказывать сотрудничество.

### Перспективный выпуск

Горизонт **10.11–09.12.2026**. DRI **0,00**, предупреждение **нет**, 10 единиц: ROK 7, JPN 3; кооперация 80%, два известных по имени говорящих, у восьми единиц имя отсутствует. Все пригодные единицы правительственные. Два 45-дневных отрезка: 2 и 8 единиц. Средняя интенсивность и её изменение равны нулю — именно они определяют балл. Кооперация и темы являются контекстом, а не новыми членами формулы. Отдельный балл ROK=0, JPN=null; равный вес стран=null. Ноль не означает отсутствие дипломатического риска.

Локальный неизменяемый журнал содержит два выпуска. Новый SHA-256: `2465bcea52b964f8292a980981d985ff3fb0ff41a4d93260f1b37fd2a5b3f1ec`. Прежний SHA от 8 ноября: `b2a9ddacc715182947cbdcbd4b9a95b07954d181fdbf10a28409cda50076f2b0`. Повторный выпуск не заменяет запись. Внешнего независимого удостоверения времени нет; это локальный журнал с проверяемой цепочкой.

Церемония Садо 13 ноября была объявлена 3 ноября: https://nwww.newsis.com/view/NISX20261103_0003852927 . Она занесена как уже известная, не как предсказанная новая эскалация. 30 ноября проводится лишь промежуточное сопоставление новых материальных действий с прежними критериями; окончание горизонта — 9 декабря. Неполное событийное покрытие не считается доказанным отсутствием событий. Событийный реестр не расширялся.

### Проверки и сохранность

201 автоматический тест прошёл. Проверены все три кейса и актуальный экран через Streamlit AppTest; localhost health=ok. После выпуска актуальный экран проверен повторно. Воспроизведение JSON кейсов побайтовое; все шесть хэшей исторических файлов совпали. 1657 документов, 1263 заявления и 1283 цитаты из существующей pre-schema-006 резервной копии совпали с текущими строками полностью. Оценки предыдущего live-импорта не изменены; `foreign_key_check` пуст. Повторный импорт партии добавляет 0 записей. Новые тесты охватывают тематические основания, пустые окна, первую дату сообщения, 90-дневную выборку, отсечение будущих материалов и неизменяемость контекста выпуска.
