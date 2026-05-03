{{ config(materialized='view') }}

WITH price_versions AS (
    SELECT
        sp.hk_listing,
        sp.price_kzt,
        sp.status,
        sp.load_datetime AS valid_from,
        LEAD(sp.load_datetime) OVER (PARTITION BY sp.hk_listing
                                     ORDER BY sp.load_datetime) AS valid_to,
        LAG(sp.price_kzt)    OVER (PARTITION BY sp.hk_listing
                                     ORDER BY sp.load_datetime) AS prev_price_kzt
    FROM {{ ref('sat_listing_price') }} sp
),
attrs_latest AS (
    SELECT *
    FROM (
        SELECT
            sa.*,
            ROW_NUMBER() OVER (PARTITION BY sa.hk_listing
                               ORDER BY sa.load_datetime DESC) AS rn
        FROM {{ ref('sat_listing_attributes') }} sa
    ) t
    WHERE rn = 1
)
SELECT
    hl.listing_id,
    pv.price_kzt,
    pv.status,
    pv.valid_from,
    pv.valid_to,
    pv.prev_price_kzt,
    pv.price_kzt - pv.prev_price_kzt AS price_delta_kzt,
    a.deal_type,
    a.property_type,
    a.rooms,
    a.area_total_m2,
    a.district_name,
    a.complex_name,
    hc.city_name
FROM price_versions pv
JOIN {{ ref('hub_listing') }} hl ON hl.hk_listing = pv.hk_listing
LEFT JOIN attrs_latest a ON a.hk_listing = pv.hk_listing
LEFT JOIN {{ ref('lnk_listing_city') }} l ON l.hk_listing = pv.hk_listing
LEFT JOIN {{ ref('hub_city') }} hc ON hc.hk_city = l.hk_city
