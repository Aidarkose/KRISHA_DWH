{{ config(materialized='view') }}

WITH attrs_latest AS (
    SELECT *
    FROM (
        SELECT
            sa.*,
            ROW_NUMBER() OVER (PARTITION BY sa.hk_listing
                               ORDER BY sa.load_datetime DESC) AS rn
        FROM {{ ref('sat_listing_attributes') }} sa
    ) t
    WHERE rn = 1
),
price_latest AS (
    SELECT *
    FROM (
        SELECT
            sp.hk_listing,
            sp.price_kzt,
            sp.status,
            sp.load_datetime AS price_since,
            ROW_NUMBER() OVER (PARTITION BY sp.hk_listing
                               ORDER BY sp.load_datetime DESC) AS rn
        FROM {{ ref('sat_listing_price') }} sp
    ) t
    WHERE rn = 1
)
SELECT
    hl.listing_id,
    a.category,
    a.deal_type,
    a.property_type,
    a.rooms,
    a.area_total_m2,
    a.area_living_m2,
    a.area_kitchen_m2,
    a.floor,
    a.floors_total,
    a.building_type,
    a.build_year,
    a.bathroom,
    a.furniture,
    a.renovation,
    a.balcony,
    a.parking,
    a.complex_name,
    a.seller_type,
    a.district_name,
    hc.city_name,
    hl.load_datetime AS first_seen_at,
    p.price_kzt,
    p.status,
    p.price_since,
    NULL::timestamptz AS posted_at,
    CASE
        WHEN a.area_total_m2 > 0 THEN p.price_kzt / a.area_total_m2
    END AS price_per_m2_kzt
FROM {{ ref('hub_listing') }} hl
LEFT JOIN attrs_latest a ON a.hk_listing = hl.hk_listing
LEFT JOIN price_latest p ON p.hk_listing = hl.hk_listing
LEFT JOIN {{ ref('lnk_listing_city') }} l ON l.hk_listing = hl.hk_listing
LEFT JOIN {{ ref('hub_city') }} hc ON hc.hk_city = l.hk_city
