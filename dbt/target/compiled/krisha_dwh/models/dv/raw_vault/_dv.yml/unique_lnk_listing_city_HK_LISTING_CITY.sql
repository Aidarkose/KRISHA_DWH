
    
    

select
    HK_LISTING_CITY as unique_field,
    count(*) as n_records

from "krisha_dwh"."marts_dv"."lnk_listing_city"
where HK_LISTING_CITY is not null
group by HK_LISTING_CITY
having count(*) > 1


