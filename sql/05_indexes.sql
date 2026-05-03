-- Индексы для производительности

-- raw
CREATE INDEX IF NOT EXISTS idx_listings_raw_listing_id_fetched
    ON raw.listings_raw (listing_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_raw_unparsed
    ON raw.listings_raw (parsed_at) WHERE parsed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_discovered_ids_last_seen
    ON raw.discovered_ids (last_seen_at);

-- stg
CREATE INDEX IF NOT EXISTS idx_stg_listings_city ON stg.listings (city_id);
CREATE INDEX IF NOT EXISTS idx_stg_listings_deal_type ON stg.listings (deal_type);
CREATE INDEX IF NOT EXISTS idx_stg_listings_status ON stg.listings (status);

-- marts
CREATE INDEX IF NOT EXISTS idx_fact_price_listing_open
    ON marts.fact_listing_price_history (listing_id) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_fact_price_valid_from
    ON marts.fact_listing_price_history (valid_from);
CREATE INDEX IF NOT EXISTS idx_dim_listing_city ON marts.dim_listing (city_id);
CREATE INDEX IF NOT EXISTS idx_dim_listing_deal_type ON marts.dim_listing (deal_type);
