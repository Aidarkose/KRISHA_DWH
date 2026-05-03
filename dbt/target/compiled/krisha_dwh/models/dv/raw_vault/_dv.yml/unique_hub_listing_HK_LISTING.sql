
    
    

select
    HK_LISTING as unique_field,
    count(*) as n_records

from "krisha_dwh"."marts_dv"."hub_listing"
where HK_LISTING is not null
group by HK_LISTING
having count(*) > 1


