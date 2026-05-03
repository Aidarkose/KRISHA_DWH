{{ config(materialized='incremental') }}

{%- set source_model = "stg_dv_listings" -%}
{%- set src_pk        = "HK_LISTING"      -%}
{%- set src_hashdiff  = "HD_LISTING_ATTRS" -%}
{%- set src_payload   = [
    "category", "deal_type", "property_type", "rooms",
    "area_total_m2", "area_living_m2", "area_kitchen_m2",
    "floor", "floors_total", "building_type", "build_year",
    "ceiling_height_m", "bathroom", "furniture", "renovation",
    "balcony", "parking", "complex_name", "seller_type",
    "district_name", "description_hash"
] -%}
{%- set src_eff       = none             -%}
{%- set src_ldts      = "LOAD_DATETIME"  -%}
{%- set src_source    = "RECORD_SOURCE"  -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff,
                   src_payload=src_payload, src_eff=src_eff,
                   src_ldts=src_ldts, src_source=src_source,
                   source_model=source_model) }}
