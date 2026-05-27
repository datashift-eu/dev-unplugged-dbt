WITH source AS (
    SELECT
        id                          AS order_id,
        customer_id,
        amount,
        TRIM(status)                AS status,
        CAST(ordered_at AS DATE)    AS ordered_date
    FROM {{ source('jaffle_shop', 'raw_orders') }}
),

customers AS (
    SELECT customer_id FROM {{ ref('stg_customers') }}
)

SELECT s.*
FROM source AS s
INNER JOIN customers AS c USING (customer_id)
