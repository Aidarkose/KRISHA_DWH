{%- set yaml_metadata -%}
source_model:
    stg: 'listings'
derived_columns:
    LOAD_DATETIME: "source_fetched_at"
    RECORD_SOURCE: "!stg.listings"
hashed_columns:
    HK_LISTING:
        - "listing_id"
    HK_CITY:
        - "city_name"
    HK_LISTING_CITY:
        - "listing_id"
        - "city_name"
    HD_LISTING_ATTRS:
        is_hashdiff: true
        columns:
            - "category"
            - "deal_type"
            - "property_type"
            - "rooms"
            - "area_total_m2"
            - "area_living_m2"
            - "area_kitchen_m2"
            - "floor"
            - "floors_total"
            - "building_type"
            - "build_year"
            - "ceiling_height_m"
            - "bathroom"
            - "furniture"
            - "renovation"
            - "balcony"
            - "parking"
            - "complex_name"
            - "seller_type"
            - "district_name"
            - "description_hash"
{%- endset -%}

{%- set metadata_dict = fromyaml(yaml_metadata) -%}

{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=metadata_dict['derived_columns'],
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
