
    
    

with child as (
    select HK_LISTING as from_field
    from "krisha_dwh"."marts_dv"."lnk_listing_city"
    where HK_LISTING is not null
),

parent as (
    select HK_LISTING as to_field
    from "krisha_dwh"."marts_dv"."hub_listing"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


