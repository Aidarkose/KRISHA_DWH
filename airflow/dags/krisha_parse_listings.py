"""DAG: krisha_parse_listings — raw.listings_raw → stg.listings."""
from __future__ import annotations

import sys
from datetime import datetime

from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

sys.path.append("/opt/airflow/scripts")

from listing_parser import parse_listing  # noqa: E402

CONN_ID = "krisha_pg"
BATCH = 500

UPSERT_SQL = """
INSERT INTO stg.listings (
    listing_id, category, deal_type, property_type,
    price_kzt, currency,
    rooms, area_total_m2, area_living_m2, area_kitchen_m2,
    floor, floors_total, building_type, build_year, ceiling_height_m,
    bathroom, furniture, renovation, balcony, parking,
    city_id, city_name, district_name, address_text, complex_name,
    lat, lon,
    description, description_hash,
    photos_count, photos_urls,
    seller_type, seller_name, posted_at, status, url,
    source_fetched_at, updated_at
) VALUES (
    %(listing_id)s, %(category)s, %(deal_type)s, %(property_type)s,
    %(price_kzt)s, %(currency)s,
    %(rooms)s, %(area_total_m2)s, %(area_living_m2)s, %(area_kitchen_m2)s,
    %(floor)s, %(floors_total)s, %(building_type)s, %(build_year)s, %(ceiling_height_m)s,
    %(bathroom)s, %(furniture)s, %(renovation)s, %(balcony)s, %(parking)s,
    %(city_id)s, %(city_name)s, %(district_name)s, %(address_text)s, %(complex_name)s,
    %(lat)s, %(lon)s,
    %(description)s, %(description_hash)s,
    %(photos_count)s, %(photos_urls)s,
    %(seller_type)s, %(seller_name)s, %(posted_at)s, %(status)s, %(url)s,
    %(source_fetched_at)s, now()
)
ON CONFLICT (listing_id) DO UPDATE SET
    category          = EXCLUDED.category,
    deal_type         = EXCLUDED.deal_type,
    property_type     = EXCLUDED.property_type,
    price_kzt         = EXCLUDED.price_kzt,
    currency          = EXCLUDED.currency,
    rooms             = EXCLUDED.rooms,
    area_total_m2     = EXCLUDED.area_total_m2,
    area_living_m2    = EXCLUDED.area_living_m2,
    area_kitchen_m2   = EXCLUDED.area_kitchen_m2,
    floor             = EXCLUDED.floor,
    floors_total      = EXCLUDED.floors_total,
    building_type     = EXCLUDED.building_type,
    build_year        = EXCLUDED.build_year,
    ceiling_height_m  = EXCLUDED.ceiling_height_m,
    bathroom          = EXCLUDED.bathroom,
    furniture         = EXCLUDED.furniture,
    renovation        = EXCLUDED.renovation,
    balcony           = EXCLUDED.balcony,
    parking           = EXCLUDED.parking,
    city_id           = EXCLUDED.city_id,
    city_name         = EXCLUDED.city_name,
    district_name     = EXCLUDED.district_name,
    address_text      = EXCLUDED.address_text,
    complex_name      = EXCLUDED.complex_name,
    lat               = EXCLUDED.lat,
    lon               = EXCLUDED.lon,
    description       = EXCLUDED.description,
    description_hash  = EXCLUDED.description_hash,
    photos_count      = EXCLUDED.photos_count,
    photos_urls       = EXCLUDED.photos_urls,
    seller_type       = EXCLUDED.seller_type,
    seller_name       = EXCLUDED.seller_name,
    posted_at         = EXCLUDED.posted_at,
    status            = EXCLUDED.status,
    url               = EXCLUDED.url,
    source_fetched_at = EXCLUDED.source_fetched_at,
    updated_at        = now()
"""


@dag(
    dag_id="krisha_parse_listings",
    description="Парсинг сырого HTML krisha.kz в нормализованную stg.listings.",
    start_date=datetime(2026, 4, 1),
    schedule="0 5 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["krisha", "transform", "stg"],
)
def krisha_parse_listings():

    @task
    def parse_unprocessed() -> dict[str, int]:
        hook = PostgresHook(postgres_conn_id=CONN_ID)
        conn = hook.get_conn()
        conn.autocommit = False

        parsed = 0
        errors = 0

        try:
            with conn.cursor() as cur:
                while True:
                    cur.execute(
                        """
                        SELECT id, listing_id, fetched_at, html
                        FROM raw.listings_raw
                        WHERE parsed_at IS NULL AND html IS NOT NULL
                        ORDER BY id
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                        """,
                        (BATCH,),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        break

                    success_ids: list[int] = []
                    error_updates: list[tuple[str, int]] = []

                    for raw_id, listing_id, fetched_at, html in rows:
                        try:
                            fields = parse_listing(html, listing_id)
                            params = {
                                "listing_id": fields.listing_id,
                                "category": fields.category,
                                "deal_type": fields.deal_type,
                                "property_type": fields.property_type,
                                "price_kzt": fields.price_kzt,
                                "currency": fields.currency,
                                "rooms": fields.rooms,
                                "area_total_m2": fields.area_total_m2,
                                "area_living_m2": fields.area_living_m2,
                                "area_kitchen_m2": fields.area_kitchen_m2,
                                "floor": fields.floor,
                                "floors_total": fields.floors_total,
                                "building_type": fields.building_type,
                                "build_year": fields.build_year,
                                "ceiling_height_m": fields.ceiling_height_m,
                                "bathroom": fields.bathroom,
                                "furniture": fields.furniture,
                                "renovation": fields.renovation,
                                "balcony": fields.balcony,
                                "parking": fields.parking,
                                "city_id": fields.city_id,
                                "city_name": fields.city_name,
                                "district_name": fields.district_name,
                                "address_text": fields.address_text,
                                "complex_name": fields.complex_name,
                                "lat": fields.lat,
                                "lon": fields.lon,
                                "description": fields.description,
                                "description_hash": fields.description_hash,
                                "photos_count": fields.photos_count,
                                "photos_urls": fields.photos_urls,
                                "seller_type": fields.seller_type,
                                "seller_name": fields.seller_name,
                                "posted_at": fields.posted_at,
                                "status": fields.status,
                                "url": fields.url,
                                "source_fetched_at": fetched_at,
                            }
                            cur.execute(UPSERT_SQL, params)
                            success_ids.append(raw_id)
                            parsed += 1
                        except Exception as exc:
                            error_updates.append((str(exc)[:500], raw_id))
                            errors += 1

                    if success_ids:
                        cur.execute(
                            "UPDATE raw.listings_raw SET parsed_at = now(), parse_error = NULL WHERE id = ANY(%s)",
                            (success_ids,),
                        )
                    if error_updates:
                        cur.executemany(
                            "UPDATE raw.listings_raw SET parsed_at = now(), parse_error = %s WHERE id = %s",
                            error_updates,
                        )
                    conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return {"parsed": parsed, "errors": errors}

    parse_unprocessed()


krisha_parse_listings()
