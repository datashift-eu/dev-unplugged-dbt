SELECT
    id                          AS order_id,
    customer_id,
    amount,
    status,
    CAST(ordered_at AS DATE)    AS ordered_date
FROM {{ source('jaffle_shop', 'raw_orders') }}
