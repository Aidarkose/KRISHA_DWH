-- raw слой: списки ID из sitemap и сырой HTML карточек

CREATE TABLE IF NOT EXISTS raw.discovered_ids (
    listing_id      BIGINT       PRIMARY KEY,
    category        TEXT         NOT NULL,
    sitemap_url     TEXT         NOT NULL,
    discovered_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.listings_raw (
    id              BIGSERIAL    PRIMARY KEY,
    listing_id      BIGINT       NOT NULL,
    fetched_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    http_status     INT          NOT NULL,
    html            TEXT,
    html_sha256     BYTEA        NOT NULL,
    parsed_at       TIMESTAMPTZ,
    parse_error     TEXT
);

CREATE TABLE IF NOT EXISTS raw.fetch_runs (
    id              BIGSERIAL    PRIMARY KEY,
    started_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    requested       INT          NOT NULL DEFAULT 0,
    succeeded       INT          NOT NULL DEFAULT 0,
    failed          INT          NOT NULL DEFAULT 0,
    notes           TEXT
);
