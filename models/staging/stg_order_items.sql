SELECT
    id              AS order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    discount_pct,
    line_total
FROM {{ source('jaffle_shop', 'raw_order_items') }}
