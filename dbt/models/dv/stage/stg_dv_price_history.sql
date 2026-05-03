{%- set yaml_metadata -%}
source_model:
    stg: 'listings'
derived_columns:
    LOAD_DATETIME: "source_fetched_at"
    RECORD_SOURCE: "!stg.listings"
hashed_columns:
    HK_LISTING:
        - "listing_id"
    HD_LISTING_PRICE:
        is_hashdiff: true
        columns:
            - "price_kzt"
            - "status"
{%- endset -%}

{%- set metadata_dict = fromyaml(yaml_metadata) -%}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
