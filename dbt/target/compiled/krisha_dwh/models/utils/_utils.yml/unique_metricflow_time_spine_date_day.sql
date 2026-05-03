
    
    

select
    date_day as unique_field,
    count(*) as n_records

from "krisha_dwh"."marts"."metricflow_time_spine"
where date_day is not null
group by date_day
having count(*) > 1


