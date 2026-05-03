"""DAG: krisha_build_marts — оркестрирует dbt-сборку DV → marts.

После krisha_parse_listings (stg.listings) запускает dbt из airflow-контейнера:
  1) dbt build --select dv     — Hub/Link/Sat поверх stg.listings (AutomateDV)
  2) dbt build --select path:models/marts   — view-слой listings_current и listing_price_events поверх DV

Старая SCD2-логика на чистом SQL удалена: SCD2 теперь обеспечивает sat_listing_price
через hashdiff в AutomateDV.
"""
from __future__ import annotations

import os
from datetime import datetime

from airflow.decorators import dag
from airflow.providers.standard.operators.bash import BashOperator

# /opt/dbt — bind-mount из ./dbt (см. docker-compose.yml).
DBT_DIR = "/opt/dbt"

# Креды для profiles.yml. Airflow конн КRISHA_PG → разбираем в env vars.
DBT_ENV = (
    "export KRISHA_PG_HOST=postgres "
    "&& export KRISHA_PG_PORT=5432 "
    f"&& export KRISHA_DB={os.environ.get('KRISHA_DB','krisha_dwh')} "
    f"&& export KRISHA_DB_USER={os.environ.get('KRISHA_DB_USER','krisha')} "
    f"&& export KRISHA_DB_PASSWORD={os.environ.get('KRISHA_DB_PASSWORD','')} "
)


def _dbt(select: str) -> str:
    return (
        f"set -e && {DBT_ENV} "
        f"&& cd {DBT_DIR} "
        f"&& dbt build --select {select} --profiles-dir {DBT_DIR} "
        f"--target-path /tmp/dbt_target --log-path /tmp/dbt_logs"
    )


@dag(
    dag_id="krisha_build_marts",
    description="dbt build: stg.listings → DV (Hub/Link/Sat AutomateDV) → marts_dbt views.",
    start_date=datetime(2026, 4, 1),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["krisha", "transform", "dbt", "dv", "marts"],
)
def krisha_build_marts():
    # dbt deps НЕ нужен в этом DAG: пакеты установлены контейнером krisha_dbt_dv
    # в общую папку /opt/dbt/dbt_packages/ через bind-mount. Тут только build.
    build_dv = BashOperator(
        task_id="dbt_build_dv",
        bash_command=_dbt("dv"),
    )

    build_marts = BashOperator(
        task_id="dbt_build_marts",
        bash_command=_dbt("path:models/marts"),
    )

    build_dv >> build_marts


krisha_build_marts()
