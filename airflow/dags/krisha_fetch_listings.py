"""DAG: krisha_fetch_listings — fetch HTML карточек с rate-limit → raw.listings_raw."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

sys.path.append("/opt/airflow/scripts")

from fetcher import Fetcher  # noqa: E402
from listing_parser import html_sha256  # noqa: E402

import logging

log = logging.getLogger(__name__)

CONN_ID = "krisha_pg"
DAILY_LIMIT = int(os.getenv("KRISHA_FETCH_DAILY_LIMIT", "5000"))
BATCH_SIZE = 100


@dag(
    dag_id="krisha_fetch_listings",
    description="Загрузка HTML карточек krisha.kz в raw.listings_raw с rate-limit.",
    start_date=datetime(2026, 4, 1),
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["krisha", "ingest", "raw"],
)
def krisha_fetch_listings():

    @task
    def select_targets(**context) -> list[int]:
        """Берём ID без свежего HTML (за последние 24 ч), приоритет — давно не обновлявшиеся.

        Лимит можно переопределить через dag_run conf:
            airflow dags trigger krisha_fetch_listings --conf '{"limit": 50}'
        """
        conf = (context.get("dag_run") and context["dag_run"].conf) or {}
        limit = int(conf.get("limit") or DAILY_LIMIT)
        sql = """
            SELECT d.listing_id
            FROM raw.discovered_ids d
            LEFT JOIN LATERAL (
                SELECT MAX(fetched_at) AS last_fetch
                FROM raw.listings_raw r
                WHERE r.listing_id = d.listing_id
            ) lr ON true
            WHERE lr.last_fetch IS NULL
               OR lr.last_fetch < now() - INTERVAL '24 hours'
            ORDER BY lr.last_fetch NULLS FIRST, d.last_seen_at DESC
            LIMIT %s
        """
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        rows = hook.get_records(sql, parameters=(limit,))
        return [int(r[0]) for r in rows]

    @task(pool="krisha_fetch")
    def fetch_and_store(listing_ids: list[int]) -> dict[str, int]:
        if not listing_ids:
            return {"requested": 0, "succeeded": 0, "failed": 0}

        fetcher = Fetcher()
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        conn = hook.get_conn()
        conn.autocommit = False

        succeeded = 0
        failed = 0

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO raw.fetch_runs (started_at, requested) VALUES (now(), %s) RETURNING id",
                    (len(listing_ids),),
                )
                run_id = cur.fetchone()[0]

                for i in range(0, len(listing_ids), BATCH_SIZE):
                    batch = listing_ids[i : i + BATCH_SIZE]
                    results = asyncio.run(fetcher.fetch_many(batch))
                    rows = []
                    for r in results:
                        if r.html and r.status == 200:
                            rows.append((r.listing_id, r.status, r.html, html_sha256(r.html)))
                            succeeded += 1
                        else:
                            log.warning(
                                "fetch failed listing_id=%s status=%s err=%s",
                                r.listing_id, r.status, r.error,
                            )
                            rows.append((r.listing_id, r.status, None, b"\x00" * 32))
                            failed += 1
                    cur.executemany(
                        """
                        INSERT INTO raw.listings_raw (listing_id, http_status, html, html_sha256)
                        VALUES (%s, %s, %s, %s)
                        """,
                        rows,
                    )
                    conn.commit()

                cur.execute(
                    """
                    UPDATE raw.fetch_runs
                       SET finished_at = now(), succeeded = %s, failed = %s
                     WHERE id = %s
                    """,
                    (succeeded, failed, run_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return {"requested": len(listing_ids), "succeeded": succeeded, "failed": failed}

    fetch_and_store(select_targets())


krisha_fetch_listings()
