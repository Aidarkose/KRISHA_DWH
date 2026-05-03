
    
    

select
    HK_CITY as unique_field,
    count(*) as n_records

from "krisha_dwh"."marts_dv"."hub_city"
where HK_CITY is not null
group by HK_CITY
having count(*) > 1


