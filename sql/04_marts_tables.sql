-- marts слой: SCD2 история и денормализованная dim для BI

CREATE TABLE IF NOT EXISTS marts.fact_listing_price_history (
    listing_id          BIGINT         NOT NULL,
    price_kzt           NUMERIC(14,2),
    status              TEXT,
    description_hash    BYTEA,
    valid_from          TIMESTAMPTZ    NOT NULL,
    valid_to            TIMESTAMPTZ,
    PRIMARY KEY (listing_id, valid_from)
);

CREATE TABLE IF NOT EXISTS marts.dim_listing (
    listing_id          BIGINT         PRIMARY KEY,
    category            TEXT,
    deal_type           TEXT,
    property_type       TEXT,
    rooms               SMALLINT,
    area_total_m2       NUMERIC(8,2),
    area_living_m2      NUMERIC(8,2),
    area_kitchen_m2     NUMERIC(8,2),
    floor               SMALLINT,
    floors_total        SMALLINT,
    building_type       TEXT,
    build_year          SMALLINT,
    ceiling_height_m    NUMERIC(3,2),
    bathroom            TEXT,
    furniture           TEXT,
    renovation          TEXT,
    balcony             TEXT,
    parking             TEXT,
    city_id             INT,
    city_name           TEXT,
    district_name       TEXT,
    address_text        TEXT,
    complex_name        TEXT,
    lat                 NUMERIC(9,6),
    lon                 NUMERIC(9,6),
    photos_count        INT,
    seller_type         TEXT,
    posted_at           TIMESTAMPTZ,
    url                 TEXT,
    first_seen_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    last_updated_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW marts.v_listings_current AS
SELECT
    d.*,
    h.price_kzt,
    h.status,
    h.description_hash,
    h.valid_from AS price_since
FROM marts.dim_listing d
LEFT JOIN marts.fact_listing_price_history h
       ON h.listing_id = d.listing_id
      AND h.valid_to IS NULL;
