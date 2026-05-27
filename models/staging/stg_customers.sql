SELECT
    id                          AS customer_id,
    first_name,
    last_name,
    LOWER(email)                AS email,
    UPPER(TRIM(country))        AS country,
    CAST(created_at AS DATE)    AS created_date
FROM {{ source('jaffle_shop', 'raw_customers') }}
