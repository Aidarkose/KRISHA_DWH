{{ config(materialized='incremental') }}

{%- set source_model = "stg_dv_listings" -%}
{%- set src_pk        = "HK_LISTING_CITY"        -%}
{%- set src_fk        = ["HK_LISTING", "HK_CITY"] -%}
{%- set src_ldts      = "LOAD_DATETIME"  -%}
{%- set src_source    = "RECORD_SOURCE"  -%}

{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,
                    src_source=src_source, source_model=source_model) }}
