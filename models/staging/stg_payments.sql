SELECT
    id                              AS payment_id,
    order_id,
    payment_method,
    ROUND(amount / 100.0, 2)        AS amount_dollars
FROM {{ source('jaffle_shop', 'raw_payments') }}
