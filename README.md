<<<<<<< HEAD
# KRISHA_DWH
=======
# KRISHA_DWH

DWH для данных krisha.kz (продажа и аренда квартир по всему Казахстану) на PostgreSQL 16 + Airflow 3.0.2.

## Архитектура

- **Источник** — публичные `sitemap.xml` и страницы `/a/show/{id}` krisha.kz (публичного API нет, парсим HTML с соблюдением robots.txt и rate-limit ≤ 2 req/s).
- **Слои БД** в одной БД `krisha_dwh`:
  - `raw` — обнаруженные ID + сырой HTML карточек
  - `stg` — нормализованные текущие данные (последняя успешная парсинг-версия)
  - `marts` — `dim_listing` (статичные атрибуты) + `fact_listing_price_history` (SCD2 история цены/статуса) + view `v_listings_current`
- **Оркестрация** — четыре DAG-а в Airflow 3.0.2:
  - `krisha_discover_ids` — обход sitemap (02:00)
  - `krisha_fetch_listings` — fetch HTML (03:00)
  - `krisha_parse_listings` — парсинг → stg (05:00)
  - `krisha_build_marts` — SCD2 → marts (06:00)

## Структура

```
docker-compose.yml         postgres + airflow (apiserver / scheduler / dag-processor) + dbt + semantic-api
Dockerfile.airflow         кастомный образ Airflow с httpx, selectolax, lxml, tenacity
Dockerfile.semantic        образ с dbt-postgres + dbt-metricflow + FastAPI
env.example                образец переменных окружения
scripts/init-db.sql        пользователи и БД (krisha_dwh, airflow_db)
scripts/apply_sql.sh       идемпотентное применение sql/*.sql
sql/00..05                 расширения, схемы, таблицы, индексы
sql/examples/queries.sql   примеры аналитических запросов
airflow/dags/              4 DAG-а
airflow/scripts/           fetcher / sitemap_parser / listing_parser + tests
dbt/                       dbt-проект + MetricFlow semantic_models + metrics
semantic_api/              FastAPI поверх MetricFlow CLI
```

## Запуск

```bash
cd /home/daurena2609/KRISHA_DWH

# 1. Скопировать env-файл и при желании поправить пароли
cp env.example .env

# 2. Собрать образ Airflow и поднять стек
docker compose build
docker compose up -d

# 3. Дождаться, пока postgres станет healthy и airflow-init завершится:
docker compose ps

# 4. Применить SQL-схемы (raw / stg / marts)
./scripts/apply_sql.sh

# 5. Проверить структуру БД
docker exec -it krisha_postgres psql -U krisha -d krisha_dwh -c '\dn'
docker exec -it krisha_postgres psql -U krisha -d krisha_dwh -c '\dt raw.*'
```

Airflow UI: http://localhost:8081 (admin / admin по умолчанию).

## Smoke-test

```bash
# Активировать все 4 DAG-а в UI и руками триггерить krisha_discover_ids
# Затем убедиться:
docker exec -it krisha_postgres psql -U krisha -d krisha_dwh -c \
  "SELECT count(*) FROM raw.discovered_ids;"
```

Для первого прогона `krisha_fetch_listings` стоит уменьшить лимит:

```bash
# в .env временно поставить
KRISHA_FETCH_DAILY_LIMIT=200
docker compose down airflow-scheduler airflow-apiserver airflow-dag-processor
docker compose up -d airflow-scheduler airflow-apiserver airflow-dag-processor
```

(в WSL2 после правок env / bind-mounted файлов используем `down + up`, не `restart`).

## Юнит-тесты парсера

```bash
docker exec -it krisha_airflow_scheduler bash -lc \
  "cd /opt/airflow/scripts && python -m pytest tests/ -v"
```

## Compliance

- Соблюдаем `robots.txt`: `/ajax/`, `/comments`, `/captcha`, `/a/show-map/`, `/signin?backUrl=` — не запрашиваем.
- `User-Agent: KRISHA_DWH/1.0 (data engineering, contact: dauren.aidarkhanov@gmail.com)`.
- Rate-limit 2 req/s, экспоненциальный бэкофф на 429/5xx.
- Данные используются только для аналитики, не перепродаются.

## Семантический слой (dbt + MetricFlow)

Поверх `marts.*` поднят dbt-проект с MetricFlow semantic layer и FastAPI-обёрткой.

```bash
# 1. собрать dbt-views и протестировать
docker exec -it krisha_dbt dbt build

# 2. убедиться, что MetricFlow видит метрики
docker exec -it krisha_dbt mf list metrics

# 3. API доступен на http://localhost:8090 (Swagger: /docs)
curl http://localhost:8090/health
```

### Пример обращения к API

Топ-10 городов по средней цене за м² (только активные продажи):

```bash
curl -s -X POST http://localhost:8090/query \
  -H 'Content-Type: application/json' \
  -d '{
    "metrics": ["avg_price_per_m2", "listings_count"],
    "group_by": ["listing__city_name"],
    "where": ["{{ Dimension(\"listing__deal_type\") }} = '\''sale'\''"],
    "order_by": ["-listings_count"],
    "limit": 10
  }' | jq
```

Ожидаемый ответ:

```json
{
  "rows": [
    {"listing__city_name": "Алматы", "listings_count": "31420", "avg_price_per_m2": "682500.00"},
    {"listing__city_name": "Астана", "listings_count": "24117", "avg_price_per_m2": "611200.00"},
    ...
  ],
  "row_count": 10,
  "sql": null
}
```

Полный python-пример: `semantic_api/example_client.py`.
Подробности про метрики и semantic_models — в `dbt/README.md`.

## Известные ограничения

- Координаты в HTML карточки могут отсутствовать (krisha рендерит карту через AJAX, который запрещён robots.txt). Поля `lat`/`lon` могут быть NULL.
- Парсер ориентирован на CSS-классы Apr 2026; если krisha поменяет вёрстку, надо обновить `airflow/scripts/listing_parser.py` и фикстуру в тестах.
- Cloudflare-защита может появиться при росте RPS — тогда снизить `KRISHA_RATE_LIMIT_RPS` в `.env`.
>>>>>>> Initial commit
