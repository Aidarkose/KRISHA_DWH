"""DAG: krisha_discover_ids — обход sitemap.xml → raw.discovered_ids."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

sys.path.append("/opt/airflow/scripts")

from sitemap_parser import (  # noqa: E402
    fetch_sitemap_index,
    iter_listings_in_sitemap,
)

CONN_ID = "krisha_pg"
TARGET_CATEGORIES = ("prodazha-kvartiry", "arenda-kvartiry")


@dag(
    dag_id="krisha_discover_ids",
    description="Обход sitemap.xml krisha.kz и UPSERT обнаруженных ID в raw.discovered_ids.",
    start_date=datetime(2026, 4, 1),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["krisha", "ingest", "raw"],
)
def krisha_discover_ids():

    @task
    def fetch_index() -> list[str]:
        urls = fetch_sitemap_index()
        if not urls:
            raise RuntimeError("Sitemap-индекс пуст: проверь доступность krisha.kz/sitemap.xml")
        return urls

    @task
    def upsert_ids(sitemap_urls: list[str]) -> dict[str, int]:
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        conn = hook.get_conn()
        conn.autocommit = False
        total = 0
        try:
            with conn.cursor() as cur:
                for url in sitemap_urls:
                    rows: list[tuple[int, str, str]] = []
                    for rec in iter_listings_in_sitemap(url, TARGET_CATEGORIES):
                        rows.append((rec.listing_id, rec.category, rec.sitemap_url))
                    if not rows:
                        continue
                    cur.executemany(
                        """
                        INSERT INTO raw.discovered_ids (listing_id, category, sitemap_url, discovered_at, last_seen_at)
                        VALUES (%s, %s, %s, now(), now())
                        ON CONFLICT (listing_id) DO UPDATE
                            SET last_seen_at = now(),
                                category = EXCLUDED.category,
                                sitemap_url = EXCLUDED.sitemap_url
                        """,
                        rows,
                    )
                    total += len(rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return {"upserted": total}

    upsert_ids(fetch_index())


krisha_discover_ids()
