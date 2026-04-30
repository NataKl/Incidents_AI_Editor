# AI Editor: Бортовой самописец сервиса + ИИ-диагностика

AI Editor - веб-приложение для фиксации событий сервиса, сборки инцидентов из связанных событий и получения структурированной ИИ-диагностики: гипотеза причины, уверенность, следующие шаги и признак необходимости ручной проверки.

Проект закрывает сценарий "что-то сломалось": события приходят разрозненно, команде нужно быстро собрать картину, зафиксировать инцидент и понять, какие данные смотреть дальше.

## Возможности

- Приём и хранение событий уровня `info`, `warning`, `error`.
- Витрина событий с фильтрами по сервису и уровню.
- Группировка выбранных событий в инцидент.
- Просмотр последних инцидентов и связанных с ними событий.
- Запуск диагностики по событиям инцидента.
- Ответ диагностики в строгой структуре: гипотеза причины, уверенность, следующие шаги, `needs_review`.
- Ручная проверка при низкой уверенности или недостатке данных.
- Сохранение результатов диагностики в БД.
- Аудит команд сервиса, успешных запусков и ошибок валидации.
- Дашборд со сводкой по событиям, инцидентам, связям и приоритетам.

## Пользовательские сценарии

1. Пользователь добавляет события на странице "События" и видит их в общей витрине.
2. Пользователь выбирает несколько событий и создаёт из них инцидент.
3. Пользователь открывает инцидент, запускает диагностику и получает структурированный результат.
4. Если данных мало, система выставляет `needs_review=true` и предлагает, какие логи, метрики и уточнения собрать.

## Архитектура

Проект состоит из нескольких сервисов Docker Compose:

- `nginx` - отдаёт собранный React-фронтенд и проксирует `/api/*` в FastAPI.
- `app` - FastAPI-бэкенд.
- `db` - PostgreSQL.
- `pgadmin` - веб-интерфейс для БД.
- `registry` и `watchtower` - вспомогательные сервисы для инфраструктуры.

Основные каталоги:

```text
backend/          FastAPI API, модели БД, сервис ИИ-диагностики
frontend/         React + Vite интерфейс
nginx/            конфигурация nginx и собранная статика
tests_data/       тестовые события, инциденты и загрузчик фикстур
scripts/          вспомогательные скрипты
resume_project.md сверка реализации с ТЗ
```

## Веб-интерфейс

### События

Страница предназначена для просмотра потока событий и поиска проблемных мест.

Что есть:

- форма создания события;
- поля `level`, `service`, `time`, `message`;
- поле времени принимает формат `DD-MM-YYYY HH:MM:ss` и перед отправкой преобразуется в ISO;
- таблица последних событий;
- фильтры по уровню и сервису;
- выбор событий чекбоксами;
- кнопка "Создать инцидент из выбранных";
- открытие подробностей события;
- удаление события.

Колонки таблицы:

- дата создания / время события;
- уровень;
- сервис;
- сообщение;
- ID события;
- действия.

### Инциденты

Страница предназначена для сборки события в инцидент и фиксации проблемы.

Что есть:

- форма создания инцидента;
- ввод списка `event_id`;
- описание инцидента;
- приоритет 1-5;
- список последних 20 инцидентов;
- раскрытие инцидента с показом связанных событий;
- кнопка запуска диагностики.

При запуске диагностики фронтенд собирает `message` из связанных событий и вызывает `POST /api/ai/diagnose`.

### Диагностика

Страница показывает результат последнего запуска диагностики.

Что есть:

- блок "Гипотеза причины";
- блок "Уверенность";
- метка "требует проверки" при `needs_review=true`;
- список "Следующие шаги";
- блок "Каких данных не хватает";
- подсказка про логи, метрики, request/correlation ID, стеки ошибок и время.

### Дашборд

Дашборд - расширение сверх минимального ТЗ. Он показывает:

- общее количество событий;
- сколько событий связаны с инцидентом;
- сколько событий не связаны с инцидентом;
- распределение инцидентов по приоритетам;
- таблицу инцидентов со связанными событиями и статусом диагностики.

## API

Все публичные команды проекта доступны с префиксом `/api`.

### Healthcheck

```http
GET /api/health
```

Ответ:

```json
{ "status": "ok" }
```

### Добавить событие

```http
POST /api/events
```

Тело:

```json
{
  "service": "api-gateway",
  "level": "error",
  "message": "Timeout to external service",
  "ts": "2026-04-30T12:00:00Z"
}
```

`ts` может быть `null`. На фронтенде пользователь вводит время как `DD-MM-YYYY HH:MM:ss`, после чего оно преобразуется в ISO для API.

Ответ:

```json
{
  "status": "ok",
  "event_id": "uuid"
}
```

Ошибки:

- `422`, если `level` не входит в `info|warning|error`;
- `422`, если `message` пустой;
- ошибка валидации записывается в `audit_runs`.

### Посмотреть события

```http
GET /api/events
GET /api/events?service=api-gateway&level=error
```

Ответ - массив событий:

```json
[
  {
    "event_id": "uuid",
    "id": "uuid",
    "created_at": "2026-04-30T12:00:00+00:00",
    "ts": null,
    "service": "api-gateway",
    "level": "error",
    "message": "Timeout to external service"
  }
]
```

### Удалить событие

```http
DELETE /api/events/{event_id}
```

Ответ:

```json
{ "status": "ok" }
```

Если событие было связано с инцидентом, связь удаляется каскадно.

### Создать инцидент

```http
POST /api/incidents
```

Тело:

```json
{
  "title": "Ошибки оплаты",
  "event_ids": ["uuid-1", "uuid-2"],
  "priority": 2
}
```

`priority` - расширение проекта: значение от 1 до 5, по умолчанию `3`.

Ответ:

```json
{
  "status": "ok",
  "incident_id": "uuid"
}
```

Ошибки:

- `404`, если часть `event_ids` не найдена;
- `409`, если событие уже связано с другим инцидентом;
- `422`, если формат UUID неверный.

### Список инцидентов

```http
GET /api/incidents
```

Возвращает последние 20 инцидентов.

### Открыть инцидент

```http
GET /api/incidents/{incident_id}
```

Возвращает инцидент и связанные события.

### Последняя диагностика инцидента

```http
GET /api/incidents/{incident_id}/diagnosis/latest
```

Возвращает последнюю сохранённую диагностику для инцидента.

### ИИ-диагностика

```http
POST /api/ai/diagnose
```

Тело:

```json
{
  "title": "Ошибки оплаты",
  "messages": [
    "DB locked при записи платежа",
    "Timeout to external service payment-gateway"
  ],
  "incident_id": "uuid"
}
```

`incident_id` опционален. Если он передан, результат сохраняется в таблицу `diagnoses`.

Ответ:

```json
{
  "root_cause_hypothesis": "Вероятная проблема с доступностью БД или внешнего платежного сервиса.",
  "confidence": "medium",
  "next_steps": [
    "Проверить метрики latency и error rate.",
    "Собрать логи БД за интервал инцидента."
  ],
  "needs_review": true
}
```

Правила ручной проверки:

- если `confidence="low"`, проект принудительно выставляет `needs_review=true`;
- при недостатке данных первые шаги диагностики начинаются со сбора уточнений;
- если модель вернула невалидный JSON, в БД сохраняется сырой ответ, `needs_review=true`, `error="INVALID_JSON"`.

### Дашборд

```http
GET /api/admin/dashboard
```

Возвращает агрегаты по событиям, инцидентам и связям.

### Админ-данные

```http
GET /api/admin/incidents
GET /api/admin/audit-runs
POST /api/admin/ingest
```

Используется для админ-сводок, просмотра аудита и записи технических событий фронтенда.

## База данных

В ТЗ указан SQLite, но в проекте используется PostgreSQL. Схема создаётся автоматически при старте FastAPI через `init_schema()`.

Основные таблицы:

- `events` - события сервиса;
- `incidents` - инциденты;
- `incident_events` - связь инцидентов и событий;
- `diagnoses` - результаты диагностики;
- `audit_runs` - аудит команд и ошибок;
- `admin_data` - технические данные админ/фронтенд ingest.

### `events`

Поля:

- `id`;
- `created_at`;
- `service`;
- `level`;
- `message`;
- `ts`.

`level` ограничен значениями `info`, `warning`, `error`.

### `incidents`

Поля:

- `id`;
- `created_at`;
- `title`;
- `priority`.

`priority` - расширение проекта, диапазон 1-5.

### `incident_events`

Поля:

- `incident_id`;
- `event_id`.

Есть ограничение уникальности `event_id`: одно событие может входить только в один инцидент.

### `diagnoses`

Поля:

- `id`;
- `created_at`;
- `incident_id`;
- `diagnosis_json`;
- `needs_review`;
- `error`.

`diagnosis_json` хранит полный JSON-ответ диагностики текстом. При `INVALID_JSON` сохраняется сырой ответ модели и ошибка.

### `audit_runs`

Поля:

- `id`;
- `created_at`;
- `action`;
- `input`;
- `output`;
- `status`;
- `error`;
- `duration_ms`.

Аудит пишется для основных команд и для ошибок валидации FastAPI.

## ИИ-диагностика

Диагностика работает в двух режимах:

1. Если задан `OPENAI_API_KEY`, используется OpenAI-compatible API.
2. Если ключ не задан, используется локальная эвристика для демонстрации сценариев.

Настройки OpenAI берутся из переменных окружения:

- `OPENAI_API_KEY`;
- `OPENAI_BASE_URL`;
- `OPENAI_MODEL`;
- `OPENAI_TEMPERATURE`;
- `HTTPS_PROXY`;
- `HTTP_PROXY`.

Ответ модели ожидается строго в JSON-формате. Сервис валидирует структуру через Pydantic.

## Запуск через Docker Compose

### 1. Подготовить `.env`

В корне проекта должен быть `.env` с переменными для БД, pgAdmin и OpenAI. Минимально нужны:

```env
POSTGRES_USER=ai_editor
POSTGRES_PASSWORD=change_me
POSTGRES_DB=ai_editor

PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=change_me
PGADMIN_PORT=5050

HTTP_PORT=80

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.2
```

Не публикуйте `.env` и реальные ключи API.

### 2. Собрать фронтенд

Nginx отдаёт файлы из `nginx/html`, поэтому после изменений во фронтенде нужно запускать production-сборку:

```bash
cd frontend
npm install
npm run build
```

После сборки обновляется `nginx/html/index.html` и файлы в `nginx/html/assets`.

### 3. Запустить сервисы

```bash
docker compose up -d --build
```

После старта:

- приложение: `http://localhost` или порт из `HTTP_PORT`;
- Swagger: `http://localhost/docs`;
- ReDoc: `http://localhost/redoc`;
- pgAdmin: `http://localhost:5050` или порт из `PGADMIN_PORT`.

### 4. Проверить API

```bash
curl http://localhost/api/health
```

Ожидаемый ответ:

```json
{ "status": "ok" }
```

## Локальная разработка фронтенда

```bash
cd frontend
npm install
npm run dev
```

Для production-режима:

```bash
npm run build
```

Важно: если интерфейс в браузере не поменялся после правок, проверьте, что выполнен `npm run build`, и обновите страницу с жёстким сбросом кэша.

## Локальная разработка бэкенда

Бэкенд находится в `backend/` и использует FastAPI.

Зависимости:

```bash
pip install -r backend/requirements.txt
```

В Docker Compose бэкенд работает в контейнере `app` и подключается к PostgreSQL по имени сервиса `db`.

При изменении backend-кода, встроенного в образ, пересоберите и перезапустите контейнер:

```bash
docker compose build app
docker compose up -d app
```

## Тестовые данные

В каталоге `tests_data/` есть:

- `events.json` - события в формате "один JSON на строку";
- `incidents.json` - тестовый инцидент;
- `load_fixtures.py` - загрузчик фикстур в PostgreSQL.

Пример запуска из контейнера:

```bash
docker compose exec app python /app/tests_data/load_fixtures.py --purge-all-tables
```

Пример запуска без Docker из корня проекта:

```bash
PYTHONPATH=backend python tests_data/load_fixtures.py --purge-all-tables
```

В ТЗ ожидается файл `tests_data/events.jsonl` из 10 строк. В текущем проекте файл называется `events.json`, но по сути содержит NDJSON-строки и расширенный набор тестовых событий.

## Типовые проверки

Добавить событие:

```bash
curl -X POST http://localhost/api/events \
  -H 'Content-Type: application/json' \
  -d '{"service":"demo","level":"error","message":"DB locked","ts":null}'
```

Получить события:

```bash
curl 'http://localhost/api/events?service=demo&level=error'
```

Создать инцидент:

```bash
curl -X POST http://localhost/api/incidents \
  -H 'Content-Type: application/json' \
  -d '{"title":"Проблемы demo","event_ids":["EVENT_UUID"],"priority":3}'
```

Запустить диагностику:

```bash
curl -X POST http://localhost/api/ai/diagnose \
  -H 'Content-Type: application/json' \
  -d '{"title":"Проблемы demo","messages":["Запуск","ок"],"incident_id":"INCIDENT_UUID"}'
```

Посмотреть аудит:

```bash
curl 'http://localhost/api/admin/audit-runs?limit=20'
```

## Отличия от исходного ТЗ

- В ТЗ указан SQLite, в проекте используется PostgreSQL.
- Пути API имеют префикс `/api`: например, `/api/events` вместо `/events`.
- Таблица `incidents` расширена полем `priority`.
- Связь `incident_events` ограничивает событие одним инцидентом.
- Есть дополнительная вкладка "Дашборд".
- Тестовый файл называется `tests_data/events.json`, а не `tests_data/events.jsonl`, и содержит больше 10 событий.

## Известные ограничения

- Нет аутентификации и авторизации: API и админ-эндпоинты доступны без логина.
- Нет Alembic/Flyway-миграций: схема создаётся DDL-кодом при старте.
- Нет автоматических pytest/API-тестов и CI.
- Нет UI для полноценного просмотра `audit_runs`.
- `/docs`, `/redoc`, `/openapi.json` доступны через nginx; для production их лучше закрыть.

## Полезные файлы

- `resume_project.md` - детальная сверка реализации с ТЗ.
- `backend/routes/events.py` - API событий.
- `backend/routes/incidents.py` - API инцидентов.
- `backend/routes/ai.py` - API диагностики.
- `backend/services/diagnosis.py` - интеграция с OpenAI и эвристика.
- `frontend/src/pages/EventsPage.tsx` - страница событий.
- `frontend/src/pages/IncidentsPage.tsx` - страница инцидентов.
- `frontend/src/pages/DiagnosisPage.tsx` - страница диагностики.
- `frontend/src/pages/DashboardPage.tsx` - дашборд.
