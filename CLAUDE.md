# CLAUDE.md — KRISHA_DWH

Инструкции для Claude Code при работе с этим репозиторием. Цель —
быстро ориентироваться в стеке, не ломать конвенции и не нарушать
compliance с krisha.kz.

## Что это за проект

DWH над публичными данными krisha.kz (продажа/аренда квартир по Казахстану).
Источник — `sitemap.xml` + страницы `/a/show/{id}`, парсятся HTML-карточки.
Публичного API у krisha нет, поэтому соблюдается `robots.txt` и rate-limit.

Поток данных:

```
sitemap.xml ──► raw.discovered_ids
              │
              └─► raw.listings_raw (HTML + sha256)
                    │
                    └─► stg.listings (нормализованные текущие поля)
                          │
                          ├─► marts.dim_listing                  (статичные атрибуты, UPSERT)
                          └─► marts.fact_listing_price_history   (SCD2: price/status/desc_hash)
                                │
                                └─► marts_dbt.listings_current   (dbt view)
                                    marts_dbt.listing_price_events
                                       │
                                       └─► MetricFlow semantic layer
                                              │
                                              └─► FastAPI /query (порт 8090)
```

## Стек и версии

- **PostgreSQL 16** (контейнер `krisha_postgres`, порт хоста `5433`)
- **Airflow 3.0.2** на python 3.12 (`Dockerfile.airflow`), executor `LocalExecutor`,
  auth — `SimpleAuthManager` (всё на admin)
- **dbt-core 1.9.1 + dbt-postgres 1.9.0 + dbt-metricflow 0.8.2** (`Dockerfile.semantic`,
  + хостовый venv `~/.venvs/krisha-dbt` для VS Code Power User; см. ниже)
- **FastAPI 0.115 + uvicorn** для семантического API (порт хоста `8090`)
- **httpx[http2] 0.27**, **selectolax 0.3**, **lxml 5.3**, **tenacity 9** —
  fetcher + parser

## Структура (top level)

```
docker-compose.yml         postgres + airflow (apiserver/scheduler/dag-processor) + dbt + semantic-api
Dockerfile.airflow         Airflow image: + httpx, selectolax, lxml, tenacity
Dockerfile.semantic        Image для dbt + MetricFlow + FastAPI
env.example / .env         Креды (НЕ комитить .env)
scripts/init-db.sql        Создаёт пользователей krisha/airflow и БД (выполняется ОДИН раз при создании volume)
scripts/apply_sql.sh       Идемпотентно применяет sql/*.sql внутри krisha_postgres
sql/00..05                 raw / stg / marts таблицы и индексы
sql/examples/queries.sql   Аналитические запросы (raw SQL, без dbt)
airflow/dags/              4 DAG-а (см. ниже)
airflow/scripts/           fetcher.py, sitemap_parser.py, listing_parser.py + tests/
dbt/                       dbt-проект krisha_dwh + MetricFlow (sm_listings, sem_price_events, metrics.yml)
semantic_api/              FastAPI поверх mf CLI (mf_runner.py + main.py + example_client.py)
```

## DAG-и (Airflow)

| DAG ID                  | Cron     | Что делает                                                          |
|-------------------------|----------|---------------------------------------------------------------------|
| `krisha_discover_ids`   | `0 2 * * *` | sitemap → UPSERT `raw.discovered_ids` (только prodazha/arenda-kvartiry) |
| `krisha_fetch_listings` | `0 3 * * *` | Fetch HTML с rate-limit (RPS=2), pool `krisha_fetch` (4 слота)      |
| `krisha_parse_listings` | `0 5 * * *` | `parse_listing()` → UPSERT `stg.listings`, `FOR UPDATE SKIP LOCKED` |
| `krisha_build_marts`    | `0 6 * * *` | SCD2: закрыть изменённые версии, открыть новые, UPSERT `dim_listing` |

Conn ID: `krisha_pg` (объявлен через `AIRFLOW_CONN_KRISHA_PG` в compose).

`krisha_fetch_listings` принимает `--conf '{"limit": 50}'` для уменьшения порции
на ручном triggere.

## Семантический слой (dbt + MetricFlow)

- **dbt schema** для построенных моделей — `marts_dbt`
  (custom schema из `dbt_project.yml`: `+schema: dbt` + дефолт `marts`).
- **Источники** (`models/sources.yml`) — таблицы `marts.dim_listing`,
  `marts.fact_listing_price_history`, `stg.listings`.
- **Модели** (`models/marts/`):
  - `listings_current` — JOIN dim + открытая версия SCD2 + расчётный
    `price_per_m2_kzt`.
  - `listing_price_events` — каждая версия SCD2 + `LAG(price_kzt)` дельта.
- **Семантические модели** (`models/semantic/`):
  - `sem_listings.yml` — entity `listing` (primary), measures count/sum/avg/max/min/percentile-median.
  - `sem_price_events.yml` — entity `listing` (foreign), measures по событиям.
- **Метрики** (`metrics.yml`):
  `listings_count`, `avg_price`, `median_price`, `max_price`, `avg_price_per_m2`
  (ratio), `price_decreases`, `price_increases`, `net_price_movements` (derived).

Перед `mf` командами всегда нужен свежий manifest — `dbt parse` (FastAPI делает
его на старте автоматически; CLI — вручную).

## Команды

### Поднять всё с нуля

```bash
cd /home/daurena2609/KRISHA_DWH
cp env.example .env                  # при необходимости поправить пароли
docker compose build
docker compose up -d
./scripts/apply_sql.sh               # raw/stg/marts таблицы и индексы
docker exec -it krisha_dbt dbt build # marts_dbt views
```

### Тесты парсера

```bash
docker exec -it krisha_airflow_scheduler bash -lc \
  "cd /opt/airflow/scripts && python -m pytest tests/ -v"
```

### dbt / MetricFlow

```bash
docker exec -it krisha_dbt dbt parse
docker exec -it krisha_dbt dbt build           # views + tests
docker exec -it krisha_dbt mf list metrics
docker exec -it krisha_dbt mf query \
  --metrics avg_price_per_m2,listings_count \
  --group-by listing__city_name \
  --order-by '-listings_count' --limit 10
```

### dbt с хоста (VS Code Power User, dbt-core)

На хосте Ubuntu 20.04 системный Python — 3.8, а dbt-core 1.9 требует ≥ 3.9.
Поэтому развёрнут отдельный venv с Python 3.12 (через `uv`) — без `sudo`.
Этот venv используется и в командной строке хоста, и расширением VS Code
**Power User for dbt Core** (`innoverio.vscode-dbt-power-user`).

```bash
# 0) Однократно (если ещё не сделано):
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.12
~/.local/bin/uv venv ~/.venvs/krisha-dbt --python 3.12
~/.local/bin/uv pip install --python ~/.venvs/krisha-dbt/bin/python \
    'dbt-core==1.9.1' 'dbt-postgres==1.9.0' 'dbt-metricflow==0.8.2'

# 1) Замена dbt-fusion на dbt-core в PATH (`~/.local/bin/dbt`):
mv ~/.local/bin/dbt ~/.local/bin/dbt-fusion        # backup, не удаляем
ln -sf ~/.venvs/krisha-dbt/bin/dbt ~/.local/bin/dbt
ln -sf ~/.venvs/krisha-dbt/bin/mf  ~/.local/bin/mf

# 2) Прогон с хоста (profiles.yml внутри ./dbt сам подбирает дефолты
# localhost:5433/krisha_dwh/krisha — никаких env vars не нужно):
cd ~/KRISHA_DWH/dbt
dbt deps
dbt debug                # должно показать "Connection test: [OK connection ok]"
dbt parse                # генерит target/manifest.json + semantic_manifest.json
dbt docs generate        # генерит target/catalog.json (нужен для OM lineage)
mf list metrics
```

VS Code Power User расширение настроено через `KRISHA_DWH/.vscode/settings.json`:
интерпретатор и `dbtPythonPathOverride` указывают на venv. После открытия проекта
расширение автоматически:
- запускает `dbt parse` → подсветка зависимостей и предпросмотр компилированного SQL,
- даёт `Run model`/`Run model + downstream`/`Test model` через UI,
- использует `~/KRISHA_DWH/dbt/profiles.yml` (поле `profilesDirOverride`).

### Семантическое API

```bash
curl -s http://localhost:8090/health
curl -s http://localhost:8090/metrics | jq
curl -s -X POST http://localhost:8090/query \
  -H 'Content-Type: application/json' \
  -d '{"metrics":["avg_price_per_m2","listings_count"],
       "group_by":["listing__city_name"],
       "where":["{{ Dimension(\"listing__deal_type\") }} = '\''sale'\''"],
       "order_by":["-listings_count"],"limit":10}' | jq

# Swagger UI: http://localhost:8090/docs
# После правок YAML семантического слоя:
curl -s -X POST http://localhost:8090/parse
```

### Проверка БД

```bash
docker exec -it krisha_postgres psql -U krisha -d krisha_dwh -c '\dn'
docker exec -it krisha_postgres psql -U krisha -d krisha_dwh -c '\dt raw.*'
docker exec -it krisha_postgres psql -U krisha -d krisha_dwh \
  -c 'SELECT count(*) FROM marts.dim_listing;'
```

### Lineage в OpenMetadata (OMEGA-3)

KRISHA_DWH каталогизирован в стеке OMEGA-3 (`~/OMEGA-3`, OpenMetadata 1.12.5).
Конфиги ingestion: `~/OMEGA-3/ingestion/krisha_postgres_metadata.yaml`,
`krisha_dbt_lineage.yaml`, `krisha_postgres_lineage.yaml`,
`krisha_postgres_profiler.yaml`, `krisha_postgres_autoclass.yaml`.

OMEGA-3 airflow подключается к krisha postgres по `host.docker.internal:5433`,
а каталог `~/KRISHA_DWH/dbt` примонтирован read-only в `/opt/airflow/krisha_dbt`
(см. `~/OMEGA-3/docker-compose.yml`). Чтобы lineage был свежим, после правок
моделей нужно пересоздать manifest+catalog с хоста (см. блок выше: `dbt parse`
+ `dbt docs generate`) — OMEGA-3 их сразу увидит через bind-mount.

Ручной запуск ingestion:

```bash
docker exec omega3-airflow-apiserver python3 \
  /opt/airflow/scripts/run_om_ingestion.py \
  -c /opt/airflow/ingestion/krisha_postgres_metadata.yaml

docker exec omega3-airflow-apiserver python3 \
  /opt/airflow/scripts/run_dbt_ingestion.py \
  -c /opt/airflow/ingestion/krisha_dbt_lineage.yaml
```

В Airflow OMEGA-3 это же запускается DAG'ом `krisha_om_ingestion_dag`
(каждый день в 07:30 UTC, по умолчанию paused).

Открыть результат: http://localhost:8585 → Explore → Databases →
`krisha_dwh` (Postgres service) → схемы `raw / stg / marts / marts_dbt /
marts_dv` → у каждой таблицы вкладка **Lineage** показывает граф.

## Конвенции, которые надо соблюдать

- **WSL2 + bind-mounts.** После правки файлов в `airflow/`, `dbt/`,
  `semantic_api/` и `.env` используй `docker compose down <svc> && docker
  compose up -d <svc>`, не `restart` — bind-mount часто не подхватывает
  изменения через `restart` в WSL2.
- **Compliance.** Не запрашивать `/ajax/`, `/comments`, `/captcha`,
  `/a/show-map/`, `/signin?backUrl=`. RPS ≤ 2 (`KRISHA_RATE_LIMIT_RPS`).
  User-Agent должен идентифицировать проект и контакт. На 429/5xx —
  экспоненциальный бэкофф (уже реализован в `Fetcher`).
- **Идемпотентность.** Все DAG-и должны переживать повторный запуск.
  В `discover` и `parse` — `INSERT ... ON CONFLICT DO UPDATE`,
  в `parse` — `FOR UPDATE SKIP LOCKED` для параллельной безопасности.
- **SCD2 семантика.** Открытая версия = `valid_to IS NULL`. Изменения
  определяются через `IS DISTINCT FROM` по `(price_kzt, status,
  description_hash)`. Не трогать closed-rows ретроактивно.
- **Naming в MetricFlow.** Измерения адресуются как `entity__dimension`,
  например `listing__city_name`, `metric_time__month`. В `where` —
  jinja-нотация: `{{ Dimension('listing__deal_type') }} = 'sale'`.
- **dbt schema.** dbt-модели лежат в `marts_dbt`, чтобы не конфликтовать
  с raw SQL слоем `marts`. Не материализовать поверх существующих
  таблиц `marts.*` — они owned by Airflow DAG.
- **Расширение парсера.** При добавлении нового поля: (1) изменить
  `ListingFields` + парсинг в `listing_parser.py`, (2) добавить колонку в
  `sql/03_stg_tables.sql`, (3) расширить `UPSERT_SQL` в
  `krisha_parse_listings.py`, (4) при необходимости — в `dim_listing`
  и `dbt/models/marts/listings_current.sql`, и в semantic_model. Тест
  на новой фикстуре обязателен.

## Подводные камни

- `scripts/init-db.sql` запускается postgres-ом ТОЛЬКО при первой
  инициализации volume `krisha_pg_data`. Если меняешь пароли в `.env`
  на уже поднятом стенде — креды postgres придётся менять руками
  через `ALTER USER`, либо снести volume (`docker volume rm
  krisha_dwh_krisha_pg_data`) и потерять все данные.
- В `init-db.sql` пароли захардкожены (`krisha_secret_2026`,
  `airflow_secret_2026`) — должны совпадать с `.env`. Если меняешь
  в одном месте — меняй в обоих.
- `lat`/`lon` в `dim_listing` часто NULL: krisha рендерит карту
  через AJAX, который запрещён robots.txt.
- Парсер ориентирован на CSS-классы krisha **апрель 2026**
  (`.offer__price`, `.offer__info-item`, `.gallery__small-list` и т.д.).
  При смене вёрстки обновлять `listing_parser.py` и фикстуру
  `airflow/scripts/tests/fixtures/sample_listing.html`.
- `posted_at` сейчас всегда NULL — локализованный парсинг русских дат
  ("обновлено 28 апр 2026") не реализован.
- `mf` CLI требует свежий manifest. Если semantic API возвращает
  ошибки про unknown metric/dimension — `POST /parse` или
  `dbt parse` в контейнере dbt.
- Cloudflare-защита может появиться при росте RPS на krisha. Снижать
  `KRISHA_RATE_LIMIT_RPS` в `.env` и пересоздавать airflow-сервисы.

## Чего не делать

- Не комитить `.env` (в `.gitignore`).
- Не вызывать `docker compose down -v` без подтверждения — это сносит
  `krisha_pg_data` со всеми накопленными raw HTML и SCD2.
- Не переименовывать роль `krisha` или БД `krisha_dwh` без обновления
  `init-db.sql`, `.env`, `dbt/profiles.yml` и Airflow conn URI.
- Не материализовать dbt-модели в схему `marts` — конфликт с
  `04_marts_tables.sql` и DAG-ом `krisha_build_marts`.
- Не выключать `--quiet` в `dbt parse` внутри `mf_runner.py` без причины
  — лишний stdout ломает парсинг ответа.
- Не использовать `--no-verify` для git-хуков и не bypass-ить
  rate-limit "временно для теста" — есть отдельный `KRISHA_FETCH_DAILY_LIMIT`.
