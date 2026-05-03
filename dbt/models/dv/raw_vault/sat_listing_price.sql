{{ config(materialized='incremental') }}

{%- set source_model = "stg_dv_price_history" -%}
{%- set src_pk        = "HK_LISTING"           -%}
{%- set src_hashdiff  = "HD_LISTING_PRICE"     -%}
{%- set src_payload   = ["price_kzt", "status"] -%}
{%- set src_eff       = none                   -%}
{%- set src_ldts      = "LOAD_DATETIME"        -%}
{%- set src_source    = "RECORD_SOURCE"        -%}

{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff,
                   src_payload=src_payload, src_eff=src_eff,
                   src_ldts=src_ldts, src_source=src_source,
                   source_model=source_model) }}
