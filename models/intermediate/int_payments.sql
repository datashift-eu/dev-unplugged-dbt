WITH payments AS (
    SELECT * FROM {{ ref('stg_payments') }}
),

mapping AS (
    SELECT * FROM {{ ref('payment_method_mapping') }}
)

SELECT
    p.order_id,
    m.payment_method_name,
    m.processing_fee_pct,
    SUM(p.amount_dollars)   AS total_amount,
    COUNT(*)                AS payment_count
FROM payments AS p
LEFT JOIN mapping AS m
    ON p.payment_method = m.payment_method
GROUP BY p.order_id, m.payment_method_name, m.processing_fee_pct
