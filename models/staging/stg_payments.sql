WITH source AS (
    SELECT
        id              AS payment_id,
        order_id,
        payment_method,
        amount
    FROM {{ source('jaffle_shop', 'raw_payments') }}
)

SELECT
    payment_id,
    order_id,
    payment_method,
    {{ cents_to_dollars('amount') }}                            AS amount_dollars,
    {{ generate_surrogate_key(['order_id', 'payment_id']) }}    AS payment_key
FROM source
