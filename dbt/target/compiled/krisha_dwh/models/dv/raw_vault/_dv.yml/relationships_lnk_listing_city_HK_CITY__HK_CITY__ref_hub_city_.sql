
    
    

with child as (
    select HK_CITY as from_field
    from "krisha_dwh"."marts_dv"."lnk_listing_city"
    where HK_CITY is not null
),

parent as (
    select HK_CITY as to_field
    from "krisha_dwh"."marts_dv"."hub_city"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


