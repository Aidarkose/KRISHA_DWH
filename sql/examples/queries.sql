-- Примеры аналитических запросов к KRISHA_DWH

-- Текущая медианная цена по городам (продажа)
SELECT
    city_name,
    COUNT(*) AS active_listings,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_kzt) AS median_price_kzt,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_kzt / NULLIF(area_total_m2, 0)) AS median_price_per_m2
FROM marts.v_listings_current
WHERE deal_type = 'sale'
  AND status = 'active'
  AND price_kzt > 0
  AND area_total_m2 > 0
GROUP BY city_name
ORDER BY active_listings DESC;

-- История изменения цены конкретного объявления
SELECT
    listing_id,
    price_kzt,
    status,
    valid_from,
    COALESCE(valid_to, now()) AS valid_to
FROM marts.fact_listing_price_history
WHERE listing_id = 700123456
ORDER BY valid_from;

-- Объявления, у которых цена снизилась за последние 7 дней
WITH changes AS (
    SELECT
        listing_id,
        price_kzt AS old_price,
        LEAD(price_kzt) OVER (PARTITION BY listing_id ORDER BY valid_from) AS new_price,
        valid_from
    FROM marts.fact_listing_price_history
)
SELECT c.*, d.city_name, d.address_text
FROM changes c
JOIN marts.dim_listing d USING (listing_id)
WHERE c.new_price < c.old_price
  AND c.valid_from > now() - INTERVAL '7 days'
ORDER BY (c.old_price - c.new_price) DESC
LIMIT 50;

-- Топ-10 районов по средней цене за квадрат (продажа квартир)
SELECT
    city_name,
    district_name,
    COUNT(*) AS listings,
    ROUND(AVG(price_kzt / NULLIF(area_total_m2, 0))) AS avg_price_per_m2
FROM marts.v_listings_current
WHERE deal_type = 'sale'
  AND status = 'active'
  AND area_total_m2 > 10
  AND price_kzt > 0
GROUP BY city_name, district_name
HAVING COUNT(*) >= 20
ORDER BY avg_price_per_m2 DESC
LIMIT 10;
