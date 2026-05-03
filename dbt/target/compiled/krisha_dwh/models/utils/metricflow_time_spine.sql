

SELECT (DATE '2020-01-01' + (n || ' day')::interval)::date AS date_day
FROM generate_series(0, (DATE '2030-12-31' - DATE '2020-01-01')) AS n