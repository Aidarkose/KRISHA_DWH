# dbt + MetricFlow для KRISHA_DWH

Проект `krisha_dwh` создаёт два view в схеме `marts_dbt` поверх существующих
таблиц `marts.dim_listing` и `marts.fact_listing_price_history`, и определяет
семантический слой MetricFlow.

## Структура

```
dbt/
├── dbt_project.yml          # имя проекта, profile, materializations
├── profiles.yml             # подключение к postgres (через env_var)
├── models/
│   ├── sources.yml          # источники = существующие marts.*
│   ├── marts/
│   │   ├── listings_current.sql        # view: dim + последняя версия SCD2
│   │   ├── listing_price_events.sql    # view: каждый шаг SCD2 как событие
│   │   └── _marts.yml                  # документация и базовые тесты
│   └── semantic/
│       ├── sem_listings.yml            # semantic_model: listings
│       ├── sem_price_events.yml        # semantic_model: price_events
│       └── metrics.yml                 # 8 метрик: simple / ratio / derived
```

## Запуск (внутри контейнера `krisha_dbt`)

```bash
docker exec -it krisha_dbt dbt deps
docker exec -it krisha_dbt dbt build      # run + test, создаёт schema marts_dbt
docker exec -it krisha_dbt mf list metrics
docker exec -it krisha_dbt mf query \
  --metrics avg_price_per_m2,listings_count \
  --group-by listing__city_name \
  --order-by '-listings_count' \
  --limit 10
```

## Метрики

| Имя                   | Тип       | Что считает                                           |
|-----------------------|-----------|-------------------------------------------------------|
| `listings_count`      | simple    | COUNT активных объявлений                             |
| `avg_price`           | simple    | AVG(price) по активным                                |
| `median_price`        | simple    | PERCENTILE_CONT(0.5) WITHIN GROUP BY price            |
| `max_price`           | simple    | MAX(price) по активным                                |
| `avg_price_per_m2`    | ratio     | SUM(price)/SUM(area) по активным sale                 |
| `price_decreases`     | simple    | Кол-во SCD2-событий с price_delta < 0                 |
| `price_increases`     | simple    | Кол-во SCD2-событий с price_delta > 0                 |
| `net_price_movements` | derived   | `price_decreases − price_increases`                   |

## Как это устроено

1. dbt создаёт два view-модели (`listings_current`, `listing_price_events`).
2. В YAML определены `semantic_models` с entities/dimensions/measures.
3. `metrics.yml` собирает из measures финальные метрики
   (включая `ratio` и `derived`).
4. `mf query` (или `POST /query` API) переводит запрос в SQL и шлёт в Postgres.
